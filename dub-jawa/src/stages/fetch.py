"""Stage 1: Fetch MP4 + SRT.

3 mode input:
  1. URL saja          -> yt-dlp download video + subtitle
  2. URL + local SRT   -> yt-dlp download video saja, subtitle dari file lokal
                          (berguna kalau subtitle downsub.com lebih bersih dari yt-dlp)
  3. local SRT saja    -> skip download video, cuma proses SRT
                          (mode testing untuk stage 2+)

Output :
  - work/source_video.mp4                       (jika URL diberikan)
  - work/source_video.<lang>.srt                 (selalu, dari yt-dlp atau lokal)
  - work/reports/stage1_report.md
  - work/info.json

Catatan ringan:
  - Format dipilih "best mp4" supaya pasti kompatibel dengan editor user.
  - Subtitle auto-detected via detect.py (filename pattern + content analysis).
  - YouTube kadang minta sign-in (bot detection). Set cookies_from_browser di config.json.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional

import yt_dlp
import pysrt

from src.stages.detect import detect_language


# Urutan preferensi bahasa subtitle (yang pertama ketemu dipakai saat download dari yt-dlp)
SUBTITLE_PREF = ["zh-Hans", "zh", "zh-Hans-original", "en", "id", "ms"]


@dataclass
class FetchResult:
    video_path: str
    srt_path: str
    subtitle_lang: str
    title: str
    duration_sec: int
    uploader: str
    original_url: str
    available_subs: list[str]


def _human_duration(seconds: int) -> str:
    """10000 -> '2h 46m 40s'"""
    if not seconds:
        return "0s"
    td = timedelta(seconds=seconds)
    days = td.days
    hours, rem = divmod(td.seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _pick_best_srt(work_dir: Path) -> Optional[Path]:
    """Pilih SRT terbaik berdasarkan preferensi bahasa."""
    srt_files = sorted(work_dir.glob("source_video*.srt"))
    if not srt_files:
        return None
    # langcode biasanya muncul di nama file: source_video.zh-Hans.srt
    for pref in SUBTITLE_PREF:
        for srt in srt_files:
            if pref in srt.name:
                return srt
    # fallback: pilih yang pertama
    return srt_files[0]


def _extract_lang_code(srt_path: Path) -> str:
    """source_video.zh-Hans.srt -> 'zh-Hans'."""
    name = srt_path.stem  # 'source_video.zh-Hans'
    parts = name.split(".", 1)
    if len(parts) == 2:
        return parts[1]
    return "unknown"


def _format_report(result: FetchResult, srt_source: str = "yt-dlp") -> str:
    """Generate laporan markdown stage 1.

    Args:
        result: FetchResult
        srt_source: 'yt-dlp' / 'local' - dari mana SRT berasal
    """
    has_video = bool(result.video_path) and not result.video_path.startswith("(")
    video_section = f"""## Video Info
- **Title**: {result.title}
- **Uploader**: {result.uploader}
- **Duration**: {_human_duration(result.duration_sec)} ({result.duration_sec}s)
- **Source URL**: {result.original_url}""" if has_video else """## Video Info
- (video tidak di-download - mode SRT-only untuk testing)"""
    status_video = "[x] Video downloaded" if has_video else "[ ] Video skipped (SRT-only mode)"
    return f"""# Stage 1: Fetch Report

{video_section}

## Output Files
- Video: `{result.video_path}`
- Subtitle: `{result.srt_path}`
- Subtitle language: `{result.subtitle_lang}` (source: {srt_source})
- Available subtitles: {", ".join(result.available_subs) or "n/a"}

## Status
- {status_video}
- [x] Subtitle loaded
- [x] Metadata saved to `work/info.json`

## Next step
User review: apakah subtitle yang dipilih sudah benar? Jika ada bahasa lain yang lebih sesuai, jalankan ulang dengan flag manual.

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 2 (Translate).
"""


def fetch_video(
    yt_url: str,
    work_dir: Path,
    progress_callback: Optional[Callable[[dict], None]] = None,
    cookies_from_browser: Optional[str] = None,
    metadata_only: bool = False,
    local_srt_path: Optional[Path] = None,
) -> FetchResult:
    """Fetch video + subtitle dari YouTube.

    Mode:
      1. URL saja                              -> yt-dlp download video + subtitle
      2. URL + local_srt_path                   -> yt-dlp download video saja, SRT dari file lokal
      3. local_srt_path only (yt_url='')        -> SRT-only mode (skip video download)

    Args:
        yt_url: URL YouTube lengkap. Boleh kosong jika local_srt_path diberikan.
        work_dir: folder kerja (akan dibuat jika belum ada).
        progress_callback: callable(dict) untuk update progress ke TUI.
        cookies_from_browser: 'chrome' / 'firefox' / 'edge' / None.
            Set kalau YouTube minta sign-in (bot detection).
        metadata_only: True = skip video download, cuma ambil info video (mode yt-dlp).
        local_srt_path: Path ke SRT lokal. Kalau diberikan, override subtitle dari yt-dlp.

    Returns:
        FetchResult dengan path file dan metadata.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "reports").mkdir(exist_ok=True)

    # --- Mode 3: SRT-only (no URL) ---
    if local_srt_path and not yt_url:
        return _load_srt_only(local_srt_path, work_dir)

    # --- Mode 1 & 2: ada URL, download video via yt-dlp ---
    use_local_srt = local_srt_path is not None

    ydl_opts: dict = {
        "outtmpl": str(work_dir / "source_video.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "writeinfojson": False,
        "quiet": True,
        "no_warnings": True,
        "noprogress": False,
        "concurrent_fragments": 4,
    }

    # subtitle dari yt-dlp hanya kalau user tidak kasih local SRT
    if not use_local_srt:
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        ydl_opts["subtitleslangs"] = SUBTITLE_PREF + ["all"]
        ydl_opts["subtitlesformat"] = "srt"

    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

    if metadata_only:
        ydl_opts["skip_download"] = True
        ydl_opts["writesubtitles"] = False
        ydl_opts["writeautomaticsub"] = False

    if progress_callback:
        def _hook(d: dict) -> None:
            try:
                progress_callback(d)
            except Exception:  # TUI error jangan sampai break download
                pass
        ydl_opts["progress_hooks"] = [_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(yt_url, download=not metadata_only)

    if metadata_only:
        return FetchResult(
            video_path="(not downloaded - metadata only)",
            srt_path="(not downloaded - metadata only)",
            subtitle_lang="n/a",
            title=info.get("title", "(unknown)"),
            duration_sec=info.get("duration", 0) or 0,
            uploader=info.get("uploader", "(unknown)"),
            original_url=yt_url,
            available_subs=sorted(
                set(
                    list((info.get("subtitles") or {}).keys())
                    + list((info.get("automatic_captions") or {}).keys())
                )
            ),
        )

    # cari video file
    video_path: Optional[Path] = None
    for ext in (".mp4", ".mkv", ".webm"):
        candidate = work_dir / f"source_video{ext}"
        if candidate.exists():
            video_path = candidate
            break
    if video_path is None:
        # fallback: file apa pun yang jadi hasil merge
        candidates = sorted(work_dir.glob("source_video.*"))
        candidates = [c for c in candidates if c.suffix not in (".srt",)]
        if not candidates:
            raise FileNotFoundError("Video file tidak ditemukan setelah download")
        video_path = candidates[0]

    # --- Tentukan SRT ---
    srt_source = "yt-dlp"
    if use_local_srt:
        # pakai SRT lokal, copy ke work_dir dengan nama konsisten
        srt_info = detect_language(local_srt_path)
        lang_code = srt_info["language"]
        target_srt = work_dir / f"source_video.{lang_code}.srt"
        shutil.copy2(local_srt_path, target_srt)
        srt_path = target_srt
        subtitle_lang = lang_code
        srt_source = f"local ({srt_info['source']})"
    else:
        srt_path = _pick_best_srt(work_dir)
        if srt_path is None:
            raise FileNotFoundError(
                "Subtitle SRT tidak terdownload. Coba ulang atau pakai local SRT via local_srt_path."
            )
        subtitle_lang = _extract_lang_code(srt_path)

    # available subs untuk laporan
    available_subs = []
    for srt in sorted(work_dir.glob("source_video*.srt")):
        lang = _extract_lang_code(srt)
        if lang not in available_subs:
            available_subs.append(lang)

    result = FetchResult(
        video_path=str(video_path),
        srt_path=str(srt_path),
        subtitle_lang=subtitle_lang,
        title=info.get("title", "(unknown title)"),
        duration_sec=info.get("duration", 0) or 0,
        uploader=info.get("uploader", "(unknown)"),
        original_url=yt_url,
        available_subs=available_subs,
    )

    # simpan info.json untuk stage berikutnya
    info_path = work_dir / "info.json"
    info_path.write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # simpan laporan
    report_path = work_dir / "reports" / "stage1_report.md"
    report_path.write_text(_format_report(result, srt_source=srt_source), encoding="utf-8")

    return result


def _load_srt_only(local_srt_path: Path, work_dir: Path) -> FetchResult:
    """Mode SRT-only: tidak download video, cuma proses subtitle.

    Berguna untuk:
      - testing pipeline stage 2+ tanpa download video besar
      - kasus user sudah punya video sendiri & subtitle downsub.com
    """
    if not local_srt_path.exists():
        raise FileNotFoundError(f"SRT tidak ditemukan: {local_srt_path}")

    srt_info = detect_language(local_srt_path)
    lang_code = srt_info["language"]

    # copy ke work_dir dengan nama konsisten
    target_srt = work_dir / f"source_video.{lang_code}.srt"
    shutil.copy2(local_srt_path, target_srt)

    # ambil title dari nama file (kasih label biar enak di laporan)
    title = local_srt_path.stem
    # truncate title panjang
    if len(title) > 100:
        title = title[:97] + "..."

    result = FetchResult(
        video_path="(skipped - SRT only mode)",
        srt_path=str(target_srt),
        subtitle_lang=lang_code,
        title=title,
        duration_sec=srt_info["duration_sec"],
        uploader="(local file)",
        original_url="(local file)",
        available_subs=[lang_code],
    )

    # simpan info.json
    info_path = work_dir / "info.json"
    info_path.write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # simpan laporan
    report_path = work_dir / "reports" / "stage1_report.md"
    report_path.write_text(
        _format_report(result, srt_source=f"local ({srt_info['source']})")
        + f"\n## SRT Detection Detail\n- Filename match: `{srt_info['filename_match']}`\n- Subtitle count: {srt_info['subtitle_count']}\n- Encoding used: `{srt_info['encoding_used']}`\n",
        encoding="utf-8",
    )

    return result


if __name__ == "__main__":
    # Test cepat dari CLI
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fetch.py <youtube_url> [work_dir]")
        print("  python fetch.py --srt <local_srt_path> [work_dir]")
        sys.exit(1)
    args = sys.argv[1:]
    wdir = Path("work")
    if args[0] == "--srt":
        if len(args) < 2:
            print("Error: --srt butuh path SRT")
            sys.exit(1)
        srt_path = Path(args[1])
        if len(args) > 2:
            wdir = Path(args[2])
        print(f"Loading SRT: {srt_path}")
        r = fetch_video("", wdir, local_srt_path=srt_path)
    else:
        url = args[0]
        if len(args) > 1:
            wdir = Path(args[1])
        print(f"Fetching {url} ...")
        r = fetch_video(url, wdir, progress_callback=lambda d: print(".", end="", flush=True))
    print()
    print(f"Title: {r.title}")
    print(f"Duration: {_human_duration(r.duration_sec)}")
    print(f"Video: {r.video_path}")
    print(f"SRT:   {r.srt_path} ({r.subtitle_lang})")

"""Stage 1: Fetch MP4 + SRT dari YouTube via yt-dlp.

Input  : URL YouTube (bisa durasi panjang/pendek, multi-bahasa)
Output :
  - work/source_video.mp4
  - work/source_video.<lang>.srt   (subtitle asli dari YouTube)
  - work/reports/stage1_report.md  (laporan + info video)
  - work/info.json                 (metadata yang diperlukan stage berikutnya)

Catatan ringan:
  - Format dipilih "best mp4" supaya pasti kompatibel dengan editor user.
  - Subtitle dipilih dalam urutan preferensi (zh-Hans > zh > en > id > ms).
  - Jika video durasi panjang, fetch bisa makan waktu lama; TUI menampilkan progress.
  - YouTube kadang minta sign-in (bot detection). Set cookies_from_browser di config.json.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


# Urutan preferensi bahasa subtitle (yang pertama ketemu dipakai)
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


def _format_report(result: FetchResult) -> str:
    """Generate laporan markdown stage 1."""
    return f"""# Stage 1: Fetch Report

## Video Info
- **Title**: {result.title}
- **Uploader**: {result.uploader}
- **Duration**: {_human_duration(result.duration_sec)} ({result.duration_sec}s)
- **Source URL**: {result.original_url}

## Output Files
- Video: `{result.video_path}`
- Subtitle: `{result.srt_path}`
- Subtitle language: `{result.subtitle_lang}`
- Available subtitles: {", ".join(result.available_subs) or "n/a"}

## Status
- [x] Video downloaded
- [x] Subtitle downloaded
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
) -> FetchResult:
    """Fetch video + subtitle dari YouTube.

    Args:
        yt_url: URL YouTube lengkap.
        work_dir: folder kerja (akan dibuat jika belum ada).
        progress_callback: callable(dict) untuk update progress ke TUI.
        cookies_from_browser: 'chrome' / 'firefox' / 'edge' / None.
            Set kalau YouTube minta sign-in (bot detection).
        metadata_only: True = skip download, cuma ambil info video.

    Returns:
        FetchResult dengan path file dan metadata.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "reports").mkdir(exist_ok=True)

    ydl_opts: dict = {
        "outtmpl": str(work_dir / "source_video.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "writeinfojson": False,
        "writesubtitles": True,
        "writeautomaticsub": True,  # auto-generated subs (Chinese video biasanya punya auto zh-Hans)
        "subtitleslangs": SUBTITLE_PREF + ["all"],
        "subtitlesformat": "srt",
        "quiet": True,
        "no_warnings": True,
        "noprogress": False,
        "concurrent_fragments": 4,
    }

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

    # cari SRT
    srt_path = _pick_best_srt(work_dir)
    if srt_path is None:
        raise FileNotFoundError(
            "Subtitle SRT tidak terdownload. Coba ulang atau pakai video lain."
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
    report_path.write_text(_format_report(result), encoding="utf-8")

    return result


if __name__ == "__main__":
    # Test cepat dari CLI
    import sys
    if len(sys.argv) < 2:
        print("Usage: python fetch.py <youtube_url> [work_dir]")
        sys.exit(1)
    url = sys.argv[1]
    wdir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("work")
    print(f"Fetching {url} ...")
    r = fetch_video(url, wdir, progress_callback=lambda d: print(".", end="", flush=True))
    print()
    print(f"Title: {r.title}")
    print(f"Duration: {_human_duration(r.duration_sec)}")
    print(f"Video: {r.video_path}")
    print(f"SRT: {r.srt_path} ({r.subtitle_lang})")

"""Stage 4: Split SRT jadi versi ngoko + krama (dictionary-only).

Input  : work/grammar_fixed.srt        (hasil stage 3)
         kamus_jawa.json                (ngoko_to_krama mapping)
Output : output/ngoko.srt              (krama words diganti ngoko)
         output/krama.srt              (ngoko words diganti krama)
         work/reports/stage4_report.md

Strategi dictionary-only (no LLM):
  - ngoko_to_krama mapping di kamus_jawa.json: {"aku": "kula", "mangan": "nedha", ...}
  - Versi krama: scan text, ganti setiap kata ngoko dengan krama equivalent.
  - Versi ngoko: bangun reverse map (krama_to_ngoko), ganti setiap kata krama dengan ngoko.
  - Case preservation: kalau kata asli di-kapital (mis. "Kula" di awal kalimat),
    replacement juga di-kapital ("Aku").
  - Word boundary regex supaya tidak partial-match ("kula" tidak match "kulawarga").
  - Kata yang tidak ada di kamus dibiarkan apa adanya di kedua versi.

Limitasi (yang user harus tau):
  - LLM output bisa saja punya kata ngoko di versi krama dan sebaliknya,
    kamus gak bisa tangkap semua (terutama imbuhan, dwilingga, dll).
  - Untuk kualitas tinggi, bisa upgrade ke LLM-based split di versi mendatang
    (tapi sekarang dictionary-only dulu sesuai request user).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

import pysrt


@dataclass
class SplitResult:
    srt_in_path: str
    ngoko_out_path: str
    krama_out_path: str
    total_subs: int
    ngoko_substitutions: int       # total kata diganti ke ngoko
    krama_substitutions: int       # total kata diganti ke krama
    subs_with_ngoko_changes: int
    subs_with_krama_changes: int
    sample_diffs: list[dict]       # [{i, original, ngoko, krama}, ...]


def _load_kamus(kamus_path: Path) -> tuple[dict, dict]:
    """Load kamus_jawa.json. Return (ngoko_to_krama, krama_to_ngoko)."""
    if not kamus_path.exists():
        return {}, {}
    data = json.loads(kamus_path.read_text(encoding="utf-8"))
    ngoko_to_krama = data.get("ngoko_to_krama", {})
    # build reverse map: krama -> ngoko
    # kalau ada collision (2 ngoko -> 1 krama), ambil yang pertama
    krama_to_ngoko: dict[str, str] = {}
    for ngoko, krama in ngoko_to_krama.items():
        if krama not in krama_to_ngoko:
            krama_to_ngoko[krama] = ngoko
    return ngoko_to_krama, krama_to_ngoko


def _substitute_with_case(text: str, mapping: dict) -> tuple[str, int]:
    """Substitusi kata dengan case preservation.

    Kalau kata asli di-kapital (mis. "Kula"), replacement juga di-kapital ("Aku").
    Word boundary pakai r"\\b" supaya tidak partial-match.
    """
    count_total = 0
    for src, tgt in mapping.items():
        if not src or not tgt or src == tgt:
            continue
        pattern = r"\b" + re.escape(src) + r"\b"
        def _replace(match, target=tgt):
            word = match.group(0)
            # preserve case
            if word[:1].isupper():
                return target[:1].upper() + target[1:]
            return target
        text, count = re.subn(pattern, _replace, text, flags=re.IGNORECASE)
        count_total += count
    return text, count_total


def split_text(text: str, ngoko_to_krama: dict, krama_to_ngoko: dict) -> tuple[str, str, dict]:
    """Untuk satu baris text, return (ngoko_version, krama_version, stats)."""
    # Versi krama: ganti ngoko words dengan krama
    krama_text, krama_subs = _substitute_with_case(text, ngoko_to_krama)
    # Versi ngoko: ganti krama words dengan ngoko
    ngoko_text, ngoko_subs = _substitute_with_case(text, krama_to_ngoko)
    return ngoko_text, krama_text, {
        "ngoko_subs": ngoko_subs,
        "krama_subs": krama_subs,
    }


def split_levels(
    work_dir: Path,
    output_dir: Path,
    kamus_path: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> SplitResult:
    """Split SRT dari work/grammar_fixed.srt -> output/ngoko.srt + output/krama.srt.

    Args:
        work_dir: folder kerja.
        output_dir: folder output (akan dibuat jika belum ada).
        kamus_path: path ke kamus_jawa.json.
        log: callback untuk TUI log.

    Returns:
        SplitResult dengan stats.
    """
    if log is None:
        log = lambda msg: None

    # cari input SRT - chain resolution:
    #   1. work/grammar_fixed.srt        (output stage 3, jika stage 3 dijalankan)
    #   2. work/translated.srt            (output stage 2, jika stage 3 di-skip)
    #   3. work/source_video.<lang>.srt   (output stage 1, jika stage 2 juga di-skip)
    srt_in_path = work_dir / "grammar_fixed.srt"
    if not srt_in_path.exists():
        srt_in_path = work_dir / "translated.srt"
    if not srt_in_path.exists():
        candidates = sorted(work_dir.glob("source_video.*.srt"))
        if not candidates:
            raise FileNotFoundError(
                f"Tidak ada SRT input di {work_dir}. "
                "Jalankan stage 1 (fetch) dulu."
            )
        srt_in_path = candidates[0]

    # cari kamus
    if kamus_path is None:
        kamus_path = work_dir.parent / "kamus_jawa.json"
    if not kamus_path.exists():
        raise FileNotFoundError(f"Kamus tidak ditemukan: {kamus_path}")

    ngoko_to_krama, krama_to_ngoko = _load_kamus(kamus_path)
    log(f"[+] Kamus loaded: {kamus_path}")
    log(f"    ngoko_to_krama entries: {len(ngoko_to_krama)}")
    log(f"    krama_to_ngoko entries: {len(krama_to_ngoko)}")

    # parse SRT
    log(f"[+] Loading SRT: {srt_in_path}")
    subs = pysrt.open(str(srt_in_path), encoding="utf-8")
    total_subs = len(subs)
    log(f"[+] Total subtitles: {total_subs}")

    # split tiap sub
    output_dir.mkdir(parents=True, exist_ok=True)
    ngoko_subs = pysrt.SubRipFile()
    krama_subs = pysrt.SubRipFile()
    total_ngoko_subs = 0
    total_krama_subs = 0
    subs_with_ngoko_changes = 0
    subs_with_krama_changes = 0
    sample_diffs: list[dict] = []

    for sub in subs:
        original = sub.text
        ngoko_text, krama_text, stats = split_text(original, ngoko_to_krama, krama_to_ngoko)

        if stats["ngoko_subs"] > 0:
            subs_with_ngoko_changes += 1
            total_ngoko_subs += stats["ngoko_subs"]
        if stats["krama_subs"] > 0:
            subs_with_krama_changes += 1
            total_krama_subs += stats["krama_subs"]

        # simpan sample: 5 pertama yang punya perubahan (di salah satu versi)
        if (stats["ngoko_subs"] > 0 or stats["krama_subs"] > 0) and len(sample_diffs) < 5:
            sample_diffs.append({
                "i": sub.index,
                "original": original,
                "ngoko": ngoko_text,
                "krama": krama_text,
            })

        ngoko_sub = pysrt.SubRipItem(
            index=sub.index, start=sub.start, end=sub.end, text=ngoko_text
        )
        krama_sub = pysrt.SubRipItem(
            index=sub.index, start=sub.start, end=sub.end, text=krama_text
        )
        ngoko_subs.append(ngoko_sub)
        krama_subs.append(krama_sub)

    # save
    ngoko_out_path = output_dir / "ngoko.srt"
    krama_out_path = output_dir / "krama.srt"
    ngoko_subs.save(str(ngoko_out_path), encoding="utf-8")
    krama_subs.save(str(krama_out_path), encoding="utf-8")
    log(f"[+] Saved: {ngoko_out_path}")
    log(f"[+] Saved: {krama_out_path}")

    result = SplitResult(
        srt_in_path=str(srt_in_path),
        ngoko_out_path=str(ngoko_out_path),
        krama_out_path=str(krama_out_path),
        total_subs=total_subs,
        ngoko_substitutions=total_ngoko_subs,
        krama_substitutions=total_krama_subs,
        subs_with_ngoko_changes=subs_with_ngoko_changes,
        subs_with_krama_changes=subs_with_krama_changes,
        sample_diffs=sample_diffs,
    )

    # simpan state
    state_path = work_dir / "state" / "stage4.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # simpan laporan
    report_path = work_dir / "reports" / "stage4_report.md"
    report_path.write_text(_format_report(result), encoding="utf-8")
    log(f"[+] Report: {report_path}")

    return result


def _format_report(result: SplitResult) -> str:
    """Generate markdown report untuk stage 4."""
    sample_md = ""
    for s in result.sample_diffs:
        sample_md += (
            f"  - **#{s['i']}**\n"
            f"    - Original: `{s['original']}`\n"
            f"    - Ngoko:    `{s['ngoko']}`\n"
            f"    - Krama:    `{s['krama']}`\n"
        )

    return f"""# Stage 4: Split ngoko/krama Report

## Summary
- **Total subtitles**: {result.total_subs}
- **Ngoko substitutions**: {result.ngoko_substitutions} (di {result.subs_with_ngoko_changes} subs)
- **Krama substitutions**: {result.krama_substitutions} (di {result.subs_with_krama_changes} subs)

## Files
- Input: `{result.srt_in_path}`
- Output ngoko: `{result.ngoko_out_path}`
- Output krama: `{result.krama_out_path}`

## Sample Diffs (first 5 with changes)
{sample_md}

## Limitasi dictionary-only
- Hanya kata yang ada di `kamus_jawa.json["ngoko_to_krama"]` yang bisa di-substitusi.
- Kata dengan imbuhan, dwilingga, atau bentuk elision tidak ditangkap.
- Untuk kualitas tinggi, bisa upgrade ke LLM-based split (Tahap 5+).

## Next step
User review: cek sample di atas. Kalau substitusi terlalu sedikit, edit `kamus_jawa.json`
tambah lebih banyak entry ngoko<->krama. Kalau sudah OK, lanjut ke Stage 5 (TTS).

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 5 (TTS - edge-tts Dimas/Siti).
"""


if __name__ == "__main__":
    import sys
    wdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("work")
    odir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output")
    r = split_levels(wdir, odir, log=lambda m: print(m))
    print(f"\n=== DONE ===")
    print(f"Total: {r.total_subs}")
    print(f"Ngoko subs: {r.ngoko_substitutions} (di {r.subs_with_ngoko_changes} subs)")
    print(f"Krama subs: {r.krama_substitutions} (di {r.subs_with_krama_changes} subs)")
    print(f"Ngoko out: {r.ngoko_out_path}")
    print(f"Krama out: {r.krama_out_path}")

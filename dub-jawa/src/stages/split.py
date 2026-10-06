"""Stage 4: Split SRT jadi versi ngoko + krama (dictionary-only, FAST combined regex).

Kamus values bisa BAKU (with ê, à, etc.) — output SRT di-strip accent untuk TTS.
"""
from __future__ import annotations
import json, re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional
import pysrt


def _strip_accents(s: str) -> str:
    """Strip diacritics dari string (comprehensive, pakai unicodedata)."""
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# Legacy _ACCENT_MAP — keep for backward compat, but use _strip_accents everywhere
_ACCENT_MAP = str.maketrans({})


@dataclass
class SplitResult:
    srt_in_path: str
    ngoko_out_path: str
    krama_out_path: str
    total_subs: int
    ngoko_substitutions: int
    krama_substitutions: int
    subs_with_ngoko_changes: int
    subs_with_krama_changes: int
    sample_diffs: list[dict]


def _load_kamus(kamus_path: Path) -> tuple[dict, dict]:
    if not kamus_path.exists():
        return {}, {}
    data = json.loads(kamus_path.read_text(encoding="utf-8"))
    raw_n2k = data.get("ngoko_to_krama", {})
    n2k = {}
    for n, k in raw_n2k.items():
        if n.startswith("_") or not n or not k or n == k:
            continue
        # Strip accent dari krama value sebelum simpan ke lookup
        # (output juga akan di-strip, so consistent)
        n2k[_strip_accents(n.lower())] = _strip_accents(k.lower())
    k2n = {}
    for ngoko, krama in n2k.items():
        if krama not in k2n:
            k2n[krama] = ngoko
    return n2k, k2n


def _build_combined_pattern(mapping: dict):
    """Build 1 compiled regex + lookup dict. Returns (pattern, lookup)."""
    if not mapping:
        return None, {}
    keywords = sorted(mapping.keys(), key=len, reverse=True)
    escaped = [re.escape(k) for k in keywords]
    combined = r"\b(?:" + "|".join(escaped) + r")\b"
    pattern = re.compile(combined, re.IGNORECASE)
    lookup = {k.lower(): v for k, v in mapping.items()}
    return pattern, lookup


def _substitute(text: str, pattern, lookup: dict) -> tuple[str, int]:
    """Substitusi pakai pre-built pattern. 1 pass, O(N).
    
    Output di-strip accent (baku → normalized) untuk TTS-friendly SRT.
    """
    if pattern is None:
        return text, 0
    count = [0]
    def _replace(match):
        word = match.group(0)
        # Normalize input word (strip accent) before lookup
        word_norm = _strip_accents(word.lower())
        target = lookup.get(word_norm)
        if target is None:
            return word
        count[0] += 1
        # Target sudah di-strip accent di _load_kamus
        if word[:1].isupper():
            return target[:1].upper() + target[1:]
        return target
    new_text = pattern.sub(_replace, text)
    # Final defensive accent strip on entire output
    new_text = _strip_accents(new_text)
    return new_text, count[0]


def split_levels(
    work_dir: Path,
    output_dir: Path,
    kamus_path: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> SplitResult:
    if log is None:
        log = lambda msg: None

    # Chain resolution untuk input SRT
    srt_in_path = work_dir / "grammar_fixed.srt"
    if not srt_in_path.exists():
        srt_in_path = work_dir / "translated.srt"
    if not srt_in_path.exists():
        candidates = sorted(work_dir.glob("source_video*.srt"))
        if not candidates:
            raise FileNotFoundError(f"Tidak ada SRT input di {work_dir}")
        srt_in_path = candidates[0]

    if kamus_path is None:
        kamus_path = work_dir.parent / "kamus_jawa.json"
    if not kamus_path.exists():
        raise FileNotFoundError(f"Kamus tidak ditemukan: {kamus_path}")

    n2k, k2n = _load_kamus(kamus_path)
    log(f"[+] Kamus: {len(n2k)} n2k, {len(k2n)} k2n")

    # Build patterns SEKALI (bukan per-subtitle)
    log(f"[+] Building combined regex patterns...")
    pat_n2k, lk_n2k = _build_combined_pattern(n2k)
    pat_k2n, lk_k2n = _build_combined_pattern(k2n)
    log(f"[+] Patterns built")

    log(f"[+] Loading SRT: {srt_in_path}")
    subs = pysrt.open(str(srt_in_path), encoding="utf-8")
    total_subs = len(subs)
    log(f"[+] Total subtitles: {total_subs}")

    output_dir.mkdir(parents=True, exist_ok=True)
    ngoko_subs = pysrt.SubRipFile()
    krama_subs = pysrt.SubRipFile()
    total_ngoko = 0
    total_krama = 0
    subs_with_ngoko = 0
    subs_with_krama = 0
    sample_diffs = []

    for sub in subs:
        original = sub.text
        # Krama: ngoko -> krama (forward map)
        krama_text, krama_count = _substitute(original, pat_n2k, lk_n2k)
        # Ngoko: krama -> ngoko (reverse map)
        ngoko_text, ngoko_count = _substitute(original, pat_k2n, lk_k2n)

        if ngoko_count > 0:
            subs_with_ngoko += 1
            total_ngoko += ngoko_count
        if krama_count > 0:
            subs_with_krama += 1
            total_krama += krama_count
        if (ngoko_count > 0 or krama_count > 0) and len(sample_diffs) < 5:
            sample_diffs.append({
                "i": sub.index,
                "original": original,
                "ngoko": ngoko_text,
                "krama": krama_text,
            })

        ngoko_subs.append(pysrt.SubRipItem(index=sub.index, start=sub.start, end=sub.end, text=ngoko_text))
        krama_subs.append(pysrt.SubRipItem(index=sub.index, start=sub.start, end=sub.end, text=krama_text))

    ngoko_out = output_dir / "ngoko.srt"
    krama_out = output_dir / "krama.srt"
    ngoko_subs.save(str(ngoko_out), encoding="utf-8")
    krama_subs.save(str(krama_out), encoding="utf-8")
    log(f"[+] Saved: {ngoko_out}")
    log(f"[+] Saved: {krama_out}")

    result = SplitResult(
        srt_in_path=str(srt_in_path),
        ngoko_out_path=str(ngoko_out),
        krama_out_path=str(krama_out),
        total_subs=total_subs,
        ngoko_substitutions=total_ngoko,
        krama_substitutions=total_krama,
        subs_with_ngoko_changes=subs_with_ngoko,
        subs_with_krama_changes=subs_with_krama,
        sample_diffs=sample_diffs,
    )

    # Save state + report
    state_dir = work_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "stage4.json").write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report_path = work_dir / "reports" / "stage4_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    sample_md = ""
    for s in sample_diffs:
        sample_md += f"  - **#{s['i']}**\n    - Original: `{s['original']}`\n    - Ngoko: `{s['ngoko']}`\n    - Krama: `{s['krama']}`\n"
    report_path.write_text(
        f"# Stage 4: Split Report\n\n## Summary\n- Total: {total_subs}\n- Ngoko subs: {total_ngoko} (di {subs_with_ngoko} subs)\n- Krama subs: {total_krama} (di {subs_with_krama} subs)\n\n## Files\n- Input: `{result.srt_in_path}`\n- Ngoko: `{result.ngoko_out_path}`\n- Krama: `{result.krama_out_path}`\n\n## Sample Diffs\n{sample_md}\n",
        encoding="utf-8",
    )
    log(f"[+] Report: {report_path}")
    return result

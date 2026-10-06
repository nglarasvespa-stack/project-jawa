"""Stage 3: Grammar fix - typo, tanda baca, kapitalisasi.

Input  : work/translated.srt          (hasil stage 2)
         kamus_jawa.json              (typo_corrections + punctuation_rules)
Output : work/grammar_fixed.srt
         work/reports/stage3_report.md (diff perubahan, stats)

Aturan fix:
  1. Whitespace: kolaps banyak spasi jadi 1, strip awal/akhir.
  2. Typo: substitusi kata dari kamus_jawa.json["typo_corrections"].
           (mis. "yang"->"kang", "udah"->"wis", "ga"->"ora", "gak"->"ora")
           Pakai word boundary regex supaya tidak partial-match.
  3. Tanda baca akhir: kalau tidak ada . ? !, tambahkan.
     - Kalimat tanya (mengandung kata "apa", "ngendi", "sapa", "pira", dst.) -> ?
     - Kalimat biasa -> .
  4. Kapitalisasi: huruf pertama jadi kapital.
  5. Tag [untranslated] dari stage 2 tetap dipertahankan (tidak diubah).

Ringan, no LLM call. Hanya regex + kamus JSON.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

import pysrt


# Kata tanya Jawa untuk deteksi kalimat tanya
QUESTION_WORDS = {
    "apa", "apaan", "ngendi", "pundi", "sapa", "sinten", "kapan", "kapepen",
    "pira", "pinten", "kepira", "kepinten", "ngapah", "nunjuk", "ya",
    "apa", "ke", "keng", "iya", "oh", "iya", "piye", "pripun",
}


@dataclass
class GrammarResult:
    srt_in_path: str
    srt_out_path: str
    total_subs: int
    subs_with_changes: int
    total_typos_fixed: int
    total_punct_added: int
    total_capitalized: int
    total_whitespace_stripped: int
    sample_diffs: list[dict]  # [{i, before, after}, ...]


def _load_kamus(kamus_path: Path) -> dict:
    """Load kamus_jawa.json. Return dict dengan keys:
    typo_corrections, punctuation_rules, question_words (jika ada).
    """
    if not kamus_path.exists():
        return {"typo_corrections": {}, "punctuation_rules": {}}
    data = json.loads(kamus_path.read_text(encoding="utf-8"))
    return {
        "typo_corrections": data.get("typo_corrections", {}),
        "punctuation_rules": data.get("punctuation_rules", {}),
    }


def _fix_whitespace(text: str) -> tuple[str, bool]:
    """Kolaps whitespace berlebihan."""
    new = re.sub(r"\s+", " ", text).strip()
    return new, new != text


def _fix_typos(text: str, typo_corrections: dict) -> tuple[str, int]:
    """Substitusi kata dari kamus. Pakai COMBINED regex pattern (1 pass, bukan loop per-entry).
    
    Jauh lebih cepat: O(N) per subtitle, bukan O(N*M).
    Multi-word entries (dengan spasi) diproses duluan supaya tidak konflik.
    """
    if not typo_corrections:
        return text, 0
    # Sort: multi-word dulu (lebih panjang), lalu single-word terpanjang
    sorted_entries = sorted(
        typo_corrections.items(),
        key=lambda kv: (-(len(kv[0].split()) if " " in kv[0] else 0), -len(kv[0]))
    )
    # Build 1 combined pattern
    escaped = [re.escape(k) for k, _ in sorted_entries]
    combined = r"\b(?:" + "|".join(escaped) + r")\b"
    pattern = re.compile(combined, re.IGNORECASE)
    # Build lookup (lowercase)
    lookup = {k.lower(): v for k, v in typo_corrections.items()}
    # Strip accent for matching
    accent_map = str.maketrans({
        'e': 'e', 'e': 'e', 'e': 'e', 'e': 'e',
        'a': 'a', 'a': 'a', 'a': 'a',
        'i': 'i', 'i': 'i', 'i': 'i',
        'o': 'o', 'o': 'o', 'o': 'o',
        'u': 'u', 'u': 'u', 'u': 'u',
        'n': 'n',
    })
    count = [0]
    def _replace(match):
        word = match.group(0)
        normalized = word.lower()
        target = lookup.get(normalized)
        if target is None:
            return word
        count[0] += 1
        if word[:1].isupper():
            return target[:1].upper() + target[1:]
        return target
    new_text = pattern.sub(_replace, text)
    return new_text, count[0]


def _is_question(text: str) -> bool:
    """Deteksi kalimat tanya dari konten kata."""
    if not text:
        return False
    # ambil kata pertama lowercase
    words_lower = text.lower().split()
    if not words_lower:
        return False
    # cek ada kata tanya di kalimat
    for w in words_lower:
        # buang tanda baca di akhir kata
        w_clean = re.sub(r"[^\w]", "", w)
        if w_clean in QUESTION_WORDS:
            return True
    return False


def _fix_punctuation(text: str, punct_rules: dict) -> tuple[str, bool]:
    """Tambah tanda baca akhir kalau belum ada."""
    if not text:
        return text, False
    
    # JANGAN modifikasi baris yang ditandai [untranslated]
    if text.startswith("[untranslated]"):
        return text, False
    
    last_char = text[-1]
    if last_char in ".?!":
        return text, False
    
    # cek tipe kalimat
    if _is_question(text):
        return text + "?", True
    if last_char in ",;:":
        # strip trailing comma, add period
        return text.rstrip(",;:") + ".", True
    # default: tambah titik
    return text + ".", True


def _capitalize_first(text: str) -> tuple[str, bool]:
    """Kapitalisasi huruf pertama."""
    if not text or text.startswith("[untranslated]"):
        return text, False
    if text[0].islower():
        return text[0].upper() + text[1:], True
    return text, False


def fix_text(text: str, typo_corrections: dict, punct_rules: dict) -> tuple[str, dict]:
    """Fix satu baris text. Return (fixed_text, stats_dict)."""
    original = text
    stats = {
        "typos_fixed": 0,
        "punct_added": False,
        "capitalized": False,
        "whitespace_stripped": False,
    }

    # 1. whitespace
    text, ws_changed = _fix_whitespace(text)
    stats["whitespace_stripped"] = ws_changed

    # 2. typo
    text, typo_count = _fix_typos(text, typo_corrections)
    stats["typos_fixed"] = typo_count

    # 3. punctuation
    text, punct_added = _fix_punctuation(text, punct_rules)
    stats["punct_added"] = punct_added

    # 4. capitalize
    text, cap = _capitalize_first(text)
    stats["capitalized"] = cap

    changed = text != original
    return text, {**stats, "changed": changed}


def fix_grammar(
    work_dir: Path,
    kamus_path: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> GrammarResult:
    """Fix grammar SRT dari work/translated.srt -> work/grammar_fixed.srt.

    Args:
        work_dir: folder kerja.
        kamus_path: path ke kamus_jawa.json. Default: <project_root>/kamus_jawa.json
        log: callback untuk TUI log.

    Returns:
        GrammarResult dengan stats.
    """
    if log is None:
        log = lambda msg: None

    # cari input SRT - chain resolution:
    #   1. work/translated.srt          (output stage 2, jika stage 2 dijalankan)
    #   2. work/source_video.<lang>.srt  (output stage 1, jika stage 2 di-skip)
    srt_in_path = work_dir / "translated.srt"
    if not srt_in_path.exists():
        # fallback ke source SRT (kasus user sudah punya SRT Jawa dari downsub)
        candidates = sorted(work_dir.glob("source_video.*.srt"))
        if not candidates:
            raise FileNotFoundError(
                f"{srt_in_path} tidak ada, dan tidak ada source_video.*.srt di {work_dir}. "
                "Jalankan stage 1 (fetch) dulu."
            )
        srt_in_path = candidates[0]

    # cari kamus
    if kamus_path is None:
        # default: 2 level up dari work_dir = project root
        kamus_path = work_dir.parent / "kamus_jawa.json"
    if not kamus_path.exists():
        log(f"[!] Kamus tidak ditemukan di {kamus_path}, pakai typo_corrections kosong.")
        kamus_data = {"typo_corrections": {}, "punctuation_rules": {}}
    else:
        kamus_data = _load_kamus(kamus_path)
        log(f"[+] Kamus loaded: {kamus_path}")
        log(f"    typo_corrections: {len(kamus_data['typo_corrections'])} entries")

    typo_corrections = kamus_data["typo_corrections"]
    punct_rules = kamus_data["punctuation_rules"]

    # parse SRT
    log(f"[+] Loading SRT: {srt_in_path}")
    subs = pysrt.open(str(srt_in_path), encoding="utf-8")
    total_subs = len(subs)
    log(f"[+] Total subtitles: {total_subs}")

    # fix tiap sub
    out_subs = pysrt.SubRipFile()
    subs_with_changes = 0
    total_typos = 0
    total_punct = 0
    total_cap = 0
    total_ws = 0
    sample_diffs: list[dict] = []
    # ambil sample: 5 pertama yang changed + 5 terakhir yang changed
    changed_count = 0

    for sub in subs:
        original_text = sub.text
        fixed_text, stats = fix_text(original_text, typo_corrections, punct_rules)

        if stats["changed"]:
            subs_with_changes += 1
            total_typos += stats["typos_fixed"]
            if stats["punct_added"]:
                total_punct += 1
            if stats["capitalized"]:
                total_cap += 1
            if stats["whitespace_stripped"]:
                total_ws += 1

            # simpan sample: 5 pertama yang changed
            if len(sample_diffs) < 5:
                sample_diffs.append({
                    "i": sub.index,
                    "before": original_text,
                    "after": fixed_text,
                })
            changed_count += 1
            # simpan juga 5 terakhir (rotate buffer)
            if changed_count > 5:
                if len(sample_diffs) >= 10:
                    sample_diffs.pop(5)  # buang yang ke-6 (index 5)
                sample_diffs.append({
                    "i": sub.index,
                    "before": original_text,
                    "after": fixed_text,
                })

        new_sub = pysrt.SubRipItem(
            index=sub.index,
            start=sub.start,
            end=sub.end,
            text=fixed_text,
        )
        out_subs.append(new_sub)

    srt_out_path = work_dir / "grammar_fixed.srt"
    out_subs.save(str(srt_out_path), encoding="utf-8")
    log(f"[+] Saved: {srt_out_path}")

    result = GrammarResult(
        srt_in_path=str(srt_in_path),
        srt_out_path=str(srt_out_path),
        total_subs=total_subs,
        subs_with_changes=subs_with_changes,
        total_typos_fixed=total_typos,
        total_punct_added=total_punct,
        total_capitalized=total_cap,
        total_whitespace_stripped=total_ws,
        sample_diffs=sample_diffs[:10],
    )

    # simpan state
    state_path = work_dir / "state" / "stage3.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # simpan laporan
    report_path = work_dir / "reports" / "stage3_report.md"
    report_path.write_text(_format_report(result), encoding="utf-8")
    log(f"[+] Report: {report_path}")

    return result


def _format_report(result: GrammarResult) -> str:
    """Generate markdown report untuk stage 3."""
    sample_md = ""
    for s in result.sample_diffs:
        sample_md += (
            f"  - **#{s['i']}**\n"
            f"    - Before: `{s['before']}`\n"
            f"    - After:  `{s['after']}`\n"
        )

    change_rate = (
        result.subs_with_changes / result.total_subs * 100
        if result.total_subs > 0
        else 0
    )

    return f"""# Stage 3: Grammar Fix Report

## Summary
- **Total subtitles**: {result.total_subs}
- **Subs with changes**: {result.subs_with_changes} ({change_rate:.1f}%)
- **Total typos fixed**: {result.total_typos_fixed}
- **Punctuation added**: {result.total_punct_added}
- **Capitalized**: {result.total_capitalized}
- **Whitespace stripped**: {result.total_whitespace_stripped}

## Files
- Input: `{result.srt_in_path}`
- Output: `{result.srt_out_path}`

## Sample Diffs (first 5 + last 5 changed)
{sample_md}

## Next step
User review: periksa sample di atas. Kalau substitusi typo salah (mis. "yang" diganti
"kang" padahal "yang" memang Jawa yang benar), edit `kamus_jawa.json` di bagian
`typo_corrections` dan jalankan ulang.

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 4 (Split ngoko/krama).
"""


if __name__ == "__main__":
    import sys
    wdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("work")
    r = fix_grammar(wdir, log=lambda m: print(m))
    print(f"\n=== DONE ===")
    print(f"Total: {r.total_subs}, changed: {r.subs_with_changes}, typos: {r.total_typos_fixed}")

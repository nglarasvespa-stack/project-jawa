"""Stage 1.5: Auto-detect bahasa source dari SRT.

Strategi (urutan):
  1. Pattern matching di nama file (paling akurat untuk file downsub.com):
     "[Chinese (Traditional)] ..." -> "zh-Hant"
     "[Chinese (Simplified)] ..." -> "zh-Hans"
     "[English] ..."                -> "en"
     "[Indonesian] ..."             -> "id"
     dst.
  2. Content-based: cek range Unicode karakter:
     - Hiragana/Katakana -> Japanese (ja)
     - Hangul            -> Korean (ko)
     - CJK Unified Ideographs -> Chinese (zh); bedakan simplified/Hant pakai karakter khas
     - Latin              -> pakai langdetect
  3. Fallback: "unknown"
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pysrt

# Pattern nama file -> kode bahasa ISO
# (downsub.com biasanya pakai format "[Language (Dialect)]")
FILENAME_PATTERNS = [
    (re.compile(r"\[Chinese\s*\(\s*Traditional[^]]*\]\s*", re.I), "zh-Hant"),
    (re.compile(r"\[Chinese\s*\(\s*Simplified[^]]*\]\s*", re.I), "zh-Hans"),
    (re.compile(r"\[Chinese[^]]*\]", re.I), "zh"),
    (re.compile(r"\[English[^]]*\]", re.I), "en"),
    (re.compile(r"\[Javanese[^]]*\]", re.I), "jv"),
    (re.compile(r"\[Indonesian[^]]*\]", re.I), "id"),
    (re.compile(r"\[Malay[^]]*\]", re.I), "ms"),
    (re.compile(r"\[Japanese[^]]*\]", re.I), "ja"),
    (re.compile(r"\[Korean[^]]*\]", re.I), "ko"),
    (re.compile(r"\[Spanish[^]]*\]", re.I), "es"),
    (re.compile(r"\[French[^]]*\]", re.I), "fr"),
    (re.compile(r"\[German[^]]*\]", re.I), "de"),
    (re.compile(r"\[Portuguese[^]]*\]", re.I), "pt"),
    (re.compile(r"\[Arabic[^]]*\]", re.I), "ar"),
    (re.compile(r"\[Thai[^]]*\]", re.I), "th"),
    (re.compile(r"\[Vietnamese[^]]*\]", re.I), "vi"),
    (re.compile(r"\[Tagalog[^]]*\]", re.I), "tl"),
    (re.compile(r"\[Russian[^]]*\]", re.I), "ru"),
]


# Karakter khas untuk membedakan zh-Hans vs zh-Hant
# (simplified memiliki stroke yang lebih sederhana)
HANT_ONLY_CHARS = set("國來學這還現後識體發關長間問業義術東機電車說們個們對給幾來開時書過現見話兒萬從來過裡這樣進道")
HANS_ONLY_CHARS = set("国来学这还现后识体发关长间问业义术东机电车说们个们对给几来开时书过现见话儿万从来过里这样进道")


def _check_filename(filename: str) -> Optional[str]:
    """Cek apakah nama file mengandung label bahasa."""
    for pattern, lang in FILENAME_PATTERNS:
        if pattern.search(filename):
            return lang
    return None


def _check_content(text: str) -> Optional[str]:
    """Deteksi dari konten SRT."""
    #ambil sampel 100 subtitle pertama supaya cepat
    sample = text[:5000]
    if not sample.strip():
        return None

    # cek Hiragana/Katakana -> Japanese
    hiragana = sum(1 for c in sample if "\u3040" <= c <= "\u309f")
    katakana = sum(1 for c in sample if "\u30a0" <= c <= "\u30ff")
    if hiragana + katakana > 10:
        return "ja"

    # cek Hangul -> Korean
    hangul = sum(1 for c in sample if "\uac00" <= c <= "\ud7af")
    if hangul > 10:
        return "ko"

    # cek CJK -> Chinese
    cjk = sum(1 for c in sample if "\u4e00" <= c <= "\u9fff")
    if cjk > 30:
        # bedakan simplified vs traditional
        hant_hits = sum(1 for c in sample if c in HANT_ONLY_CHARS)
        hans_hits = sum(1 for c in sample if c in HANS_ONLY_CHARS)
        if hant_hits > hans_hits:
            return "zh-Hant"
        if hans_hits > hant_hits:
            return "zh-Hans"
        return "zh"

    # Latin -> pakai langdetect
    try:
        from langdetect import detect as _ld_detect
        # gabungkan beberapa baris supaya detect lebih stabil
        sample_for_ld = " ".join(text.split()[:500])
        if len(sample_for_ld) > 20:
            return _ld_detect(sample_for_ld)
    except Exception:
        pass

    return None


def detect_language(srt_path: Path) -> dict:
    """Deteksi bahasa SRT.

    Returns:
        dict with keys:
        - language: kode ISO 639-1 (mis. 'zh-Hant', 'en', 'id', 'unknown')
        - source: 'filename' / 'content' / 'unknown'
        - filename_match: label yang ketemu di filename (untuk debug)
        - subtitle_count: jumlah baris SRT
        - duration_sec: durasi total (last sub end)
        - encoding_used: encoding yang dipakai pysrt untuk parse
    """
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT tidak ditemukan: {srt_path}")

    # 1. filename
    lang_from_filename = _check_filename(srt_path.name)

    # 2. content
    srt_text = ""
    encoding_used = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            subs = pysrt.open(str(srt_path), encoding=enc)
            encoding_used = enc
            # gabungkan text semua subs (cukup 200 pertama untuk deteksi)
            srt_text = "\n".join(s.text for s in subs[:200])
            sub_count = len(subs)
            duration_sec = 0
            if subs:
                last_end = subs[-1].end
                duration_sec = (
                    last_end.hours * 3600
                    + last_end.minutes * 60
                    + last_end.seconds
                    + last_end.milliseconds / 1000
                )
            break
        except Exception:
            continue
    else:
        raise ValueError(f"Tidak bisa parse SRT dengan encoding yang umum: {srt_path}")

    lang_from_content = _check_content(srt_text)

    # pilih hasil: filename menang (paling reliable untuk file downsub.com)
    if lang_from_filename:
        language = lang_from_filename
        source = "filename"
    elif lang_from_content:
        language = lang_from_content
        source = "content"
    else:
        language = "unknown"
        source = "unknown"

    return {
        "language": language,
        "source": source,
        "filename_match": lang_from_filename or "(no match)",
        "subtitle_count": sub_count,
        "duration_sec": int(duration_sec),
        "encoding_used": encoding_used,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python detect.py <srt_path>")
        sys.exit(1)
    result = detect_language(Path(sys.argv[1]))
    for k, v in result.items():
        print(f"  {k}: {v}")

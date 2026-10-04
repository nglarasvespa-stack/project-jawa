"""Extract ngoko<->krama pairs - improved dengan pattern matching lebih luas.

Pattern yang di-handle:
  1. "Krama of X." (murni)
  2. "Krama of X ("english")" atau "Krama of X (latin)"
  3. "Krama inggil of X."
  4. "Krama madya of X."
  5. "alternative spelling of Y, krama of X." / "krama of X" di posisi tengah
  6. "Krama of X (carakan: ꦏꦿꦩ)" - skip non-latin
  7. "dated spelling of Y, krama of X."
"""
import json
import re
from pathlib import Path
from collections import defaultdict

INPUT = Path("/tmp/kaikki-jv.jsonl")
OUTPUT = Path("/home/z/my-project/dub-jawa/kamus_jawa.json")

# Patterns yang lebih komprehensif
KRAMA_OF_RE = re.compile(
    r"\b(krama(?:\s+(?:inggil|madya))?)\s+of\s+"
    r"([a-zA-Zêèé'àâîôû]+(?:[\s-][a-zA-Zêèé'àâîôû]+)*)",
    re.IGNORECASE,
)

# Pattern untuk "krama of X" di tengah (bukan awal)
KRAMA_OF_MID_RE = re.compile(
    r"krama(?:\s+(inggil|madya))?\s+of\s+"
    r"([a-zA-Zêèé'àâîôû]+(?:[\s-][a-zA-Zêèé'àâîôû]+)*)",
    re.IGNORECASE,
)

# Latin-only check
LATIN_RE = re.compile(r"^[a-zA-Zêèé'àâîôû _\-]+$")


def is_latin_word(w: str) -> bool:
    if not w or len(w) < 1:
        return False
    if any("\ua980" <= c <= "\ua9df" for c in w):
        return False
    return bool(LATIN_RE.match(w))


def normalize_word(w: str) -> str:
    return w.strip().lower().replace(" ", "_")


def clean_paren(s: str) -> str:
    """Buang bagian dalam tanda kurung."""
    return re.sub(r"\([^)]*\)", "", s).strip()


def extract_pairs():
    ngoko_to_krama = {}  # ngoko -> krama
    ngoko_to_krama_inggil = {}
    ngoko_to_krama_madya = {}
    stats = defaultdict(int)
    raw_extractions = []

    with INPUT.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            word = d.get("word", "")
            if not is_latin_word(word):
                continue
            word_norm = normalize_word(word)

            # Strategy A: forms dengan tag krama (word = ngoko, form = krama)
            for form_obj in d.get("forms", []):
                tags = form_obj.get("tags", [])
                form_text = form_obj.get("form", "")
                if not is_latin_word(form_text):
                    continue
                form_norm = normalize_word(form_text)
                if not form_norm or form_norm == word_norm:
                    continue
                if "krama-inggil" in tags or "krama_inggil" in tags:
                    if word_norm not in ngoko_to_krama_inggil:
                        ngoko_to_krama_inggil[word_norm] = form_norm
                        stats["forms_krama_inggil"] += 1
                        raw_extractions.append(("forms_krama_inggil", word, form_text, form_text))
                elif "krama" in tags:
                    if word_norm not in ngoko_to_krama:
                        ngoko_to_krama[word_norm] = form_norm
                        stats["forms_krama"] += 1
                        raw_extractions.append(("forms_krama", word, form_text, form_text))

            # Strategy B: glosses dengan pattern "Krama of X"
            for sense in d.get("senses", []):
                for g in sense.get("glosses", []):
                    g_clean = clean_paren(g)
                    # cari semua match di gloss
                    for m in KRAMA_OF_RE.finditer(g_clean):
                        level = (m.group(1) or "krama").lower().replace(" ", "_")
                        src_ngoko = m.group(2).strip().rstrip(".,;:")
                        if not is_latin_word(src_ngoko):
                            continue
                        src_ngoko_norm = normalize_word(src_ngoko)
                        if not src_ngoko_norm or src_ngoko_norm == word_norm:
                            continue
                        if level == "krama_inggil":
                            if src_ngoko_norm not in ngoko_to_krama_inggil:
                                ngoko_to_krama_inggil[src_ngoko_norm] = word_norm
                                stats["gloss_krama_inggil"] += 1
                                raw_extractions.append(("gloss_krama_inggil", src_ngoko, word, g))
                        elif level == "krama_madya":
                            if src_ngoko_norm not in ngoko_to_krama_madya:
                                ngoko_to_krama_madya[src_ngoko_norm] = word_norm
                                stats["gloss_krama_madya"] += 1
                                raw_extractions.append(("gloss_krama_madya", src_ngoko, word, g))
                        else:  # "krama"
                            if src_ngoko_norm not in ngoko_to_krama:
                                ngoko_to_krama[src_ngoko_norm] = word_norm
                                stats["gloss_krama"] += 1
                                raw_extractions.append(("gloss_krama", src_ngoko, word, g))

    return ngoko_to_krama, ngoko_to_krama_inggil, ngoko_to_krama_madya, stats, raw_extractions


def load_existing_kamus_clean():
    """Load kamus lama, clean entries yang ngoko==krama atau non-latin."""
    if not OUTPUT.exists():
        return {}, {}, {}
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    existing_n2k = {}
    for k, v in data.get("ngoko_to_krama", {}).items():
        if k.startswith("_") or not is_latin_word(k):
            continue
        if not is_latin_word(v):
            continue
        kn = normalize_word(k)
        vn = normalize_word(v)
        if kn == vn:
            continue  # buang entries yang ngoko == krama
        existing_n2k[kn] = vn
    existing_n2ki = {}
    for k, v in data.get("ngoko_to_krama_inggil", {}).items():
        if k.startswith("_") or not is_latin_word(k) or not is_latin_word(v):
            continue
        kn = normalize_word(k)
        vn = normalize_word(v)
        if kn == vn:
            continue
        existing_n2ki[kn] = vn
    return existing_n2k, existing_n2ki, data.get("typo_corrections", {})


def main():
    print("[+] Extracting...")
    n2k, n2ki, n2km, stats, raw = extract_pairs()

    print(f"\n=== Extraction Stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\n  Unique ngoko->krama: {len(n2k)}")
    print(f"  Unique ngoko->krama_inggil: {len(n2ki)}")
    print(f"  Unique ngoko->krama_madya: {len(n2km)}")

    # Sample raw extractions
    print(f"\n=== Sample raw extractions (15 from gloss) ===")
    gloss_only = [r for r in raw if r[0].startswith("gloss")]
    for r in gloss_only[:15]:
        print(f"  {r[0]:25} ngoko={r[1]:20} krama={r[2]:20} | gloss={r[3][:80]!r}")

    # Merge dengan existing (existing menang)
    existing_n2k, existing_n2ki, typo = load_existing_kamus_clean()
    print(f"\n[+] Existing (cleaned): {len(existing_n2k)} n2k, {len(existing_n2ki)} n2ki")

    merged_n2k = dict(n2k)
    merged_n2k.update(existing_n2k)
    merged_n2ki = dict(n2ki)
    merged_n2ki.update(existing_n2ki)

    print(f"[+] Merged: {len(merged_n2k)} n2k, {len(merged_n2ki)} n2ki, {len(n2km)} n2km")

    final = {
        "meta": {
            "version": "0.3.0",
            "note": "Kamus dari Wiktionary Javanese (kaikki.org, CC BY-SA) + manual entries.",
            "sources": [
                "https://kaikki.org/dictionary/Javanese/ (Wiktionary Javanese, CC BY-SA)",
                "Manual curation (~430 entries, mungkin masih banyak noise)"
            ],
            "schema": "ngoko_to_krama: forward map (ngoko -> krama)",
            "last_updated": "2026-10-04"
        },
        "ngoko_to_krama": merged_n2k,
        "ngoko_to_krama_inggil": merged_n2ki,
        "ngoko_to_krama_madya": n2km,
        "punctuation_rules": {
            "sentence_endings": ["?", "!", "."],
            "open_quote": "\u201c",
            "close_quote": "\u201d",
            "comma_pause_ms": 200,
            "sentence_pause_ms": 500
        },
        "typo_corrections": typo
    }

    OUTPUT.write_text(
        json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[+] Saved: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")

    # Save debug
    debug = Path("/home/z/my-project/scripts/jv_kamus_extracted_v2.json")
    debug.write_text(
        json.dumps({
            "ngoko_to_krama_extracted": n2k,
            "ngoko_to_krama_inggil_extracted": n2ki,
            "ngoko_to_krama_madya_extracted": n2km,
            "stats": dict(stats),
            "raw_samples": raw[:50],
        }, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"[+] Debug: {debug}")


if __name__ == "__main__":
    main()

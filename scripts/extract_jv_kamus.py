"""Extract ngoko<->krama pairs dari Wiktionary Javanese JSONL (kaikki.org).

Strategi:
  1. Forms dengan tag "krama": word = ngoko, form = krama
     (e.g., {"word": "mangan", "form": "nedha", "tags": ["krama"]})
  2. Glosses dengan pattern "Krama of X" or "Krama inggil of X":
     word = krama, X = ngoko
     (e.g., {"word": "pisang", "gloss": "Krama of gedhang"})
  3. Filter: hanya lowercase latin script, skip Javanese script (ꦏꦫ꧈)
  4. Deduplicate, save ke kamus_jawa.json
"""
import json
import re
from pathlib import Path
from collections import defaultdict

INPUT = Path("/tmp/kaikki-jv.jsonl")
OUTPUT = Path("/home/z/my-project/dub-jawa/kamus_jawa.json")

# Pattern "Krama of X" atau "Krama inggil of X" atau "Krama Inggil of X"
KRAMA_OF_PATTERN = re.compile(
    r"^\s*(krama(?:\s+inggil)?)\s+of\s+([a-zA-Zéèê]+(?:[-\s][a-zA-Zéèê]+)*)\.?\s*$",
    re.IGNORECASE,
)


def is_latin_word(w: str) -> bool:
    """Cek apakah word hanya berisi latin alphabet + sedikit tanda."""
    if not w or len(w) < 1:
        return False
    # Reject Javanese script (\uA980-\uA9DF)
    if any("\ua980" <= c <= "\ua9df" for c in w):
        return False
    # Accept only latin letters + space + dash
    return all(c.isalpha() or c in " -" for c in w)


def normalize_word(w: str) -> str:
    """Bersihkan word: strip, lowercase tapi preserve dash."""
    return w.strip().lower().replace(" ", "_")


def extract_pairs():
    """Extract dari JSONL. Return dict ngoko -> krama."""
    ngoko_to_krama = {}      # ngoko -> krama
    ngoko_to_krama_inggil = {}  # ngoko -> krama inggil
    # Reverse untuk cross-check
    krama_to_ngoko = {}
    stats = defaultdict(int)

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

            # Strategy 1: forms dengan tag krama
            forms = d.get("forms", [])
            for form_obj in forms:
                tags = form_obj.get("tags", [])
                form_text = form_obj.get("form", "")
                if not is_latin_word(form_text):
                    continue
                if "krama-inggil" in tags or "krama_inggil" in tags:
                    ngoko_norm = normalize_word(word)
                    krama_inggil_norm = normalize_word(form_text)
                    if ngoko_norm and krama_inggil_norm and ngoko_norm != krama_inggil_norm:
                        ngoko_to_krama_inggil[ngoko_norm] = krama_inggil_norm
                        stats["forms_krama_inggil"] += 1
                elif "krama" in tags:
                    ngoko_norm = normalize_word(word)
                    krama_norm = normalize_word(form_text)
                    if ngoko_norm and krama_norm and ngoko_norm != krama_norm:
                        # hanya simpan kalau belum ada (first wins)
                        if ngoko_norm not in ngoko_to_krama:
                            ngoko_to_krama[ngoko_norm] = krama_norm
                            stats["forms_krama"] += 1

            # Strategy 2: glosses dengan "Krama of X" pattern
            senses = d.get("senses", [])
            for sense in senses:
                glosses = sense.get("glosses", [])
                for g in glosses:
                    m = KRAMA_OF_PATTERN.match(g.strip())
                    if not m:
                        continue
                    level = m.group(1).lower().replace(" ", "_")  # "krama" / "krama_inggil"
                    src_ngoko_raw = m.group(2).strip()
                    if not is_latin_word(src_ngoko_raw):
                        continue
                    # word (current entry) = krama, src_ngoko_raw = ngoko
                    krama_norm = normalize_word(word)
                    ngoko_norm = normalize_word(src_ngoko_raw)
                    if not krama_norm or not ngoko_norm or krama_norm == ngoko_norm:
                        continue
                    if level == "krama_inggil":
                        if ngoko_norm not in ngoko_to_krama_inggil:
                            ngoko_to_krama_inggil[ngoko_norm] = krama_norm
                            stats["gloss_krama_inggil"] += 1
                    else:  # "krama"
                        if ngoko_norm not in ngoko_to_krama:
                            ngoko_to_krama[ngoko_norm] = krama_norm
                            stats["gloss_krama"] += 1

    return ngoko_to_krama, ngoko_to_krama_inggil, stats


def load_existing_kamus():
    """Load kamus lama (yang sudah ditulis 430 entries) supaya bisa merge."""
    if not OUTPUT.exists():
        return {}
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    existing = data.get("ngoko_to_krama", {})
    # Filter out comment keys
    return {k: v for k, v in existing.items() if not k.startswith("_")}


def main():
    print("[+] Extracting ngoko<->krama pairs dari Wiktionary Javanese...")
    ngoko_to_krama_extracted, ngoko_to_krama_inggil_extracted, stats = extract_pairs()

    print(f"\n=== Extraction Stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\n  Unique ngoko->krama: {len(ngoko_to_krama_extracted)}")
    print(f"  Unique ngoko->krama_inggil: {len(ngoko_to_krama_inggil_extracted)}")

    # Merge dengan kamus lama (yang user/saya tulis manual)
    existing = load_existing_kamus()
    print(f"\n[+] Existing kamus entries (manual): {len(existing)}")

    # Merge: existing menang (lebih curated), extracted sebagai tambahan
    merged = dict(ngoko_to_krama_extracted)
    merged.update(existing)  # existing override
    print(f"[+] Merged total: {len(merged)}")

    # Sample
    print(f"\n=== Sample merged (20 first) ===")
    for i, (n, k) in enumerate(sorted(merged.items())[:20]):
        print(f"  {n} -> {k}")

    # Build final kamus structure
    final = {
        "meta": {
            "version": "0.3.0",
            "note": "Kamus dari Wiktionary Javanese (kaikki.org) + manual entries. Total ribuan mappings.",
            "sources": [
                "Wiktionary Javanese (https://kaikki.org/dictionary/Javanese/) - CC BY-SA",
                "Manual curation (430 entries)"
            ],
            "last_updated": "2026-10-04",
            "schema": "ngoko_to_krama: forward map (ngoko -> krama)"
        },
        "ngoko_to_krama": merged,
        "ngoko_to_krama_inggil": ngoko_to_krama_inggil_extracted,
        "punctuation_rules": {
            "sentence_endings": ["?", "!", "."],
            "ellipsis": "...",
            "open_quote": "\u201c",
            "close_quote": "\u201d",
            "comma_pause_ms": 200,
            "sentence_pause_ms": 500
        },
        "typo_corrections": {
            "yang": "kang",
            "udah": "wis",
            "ga": "ora",
            "gak": "ora",
            "nggak": "ora",
            "enggak": "ora",
            "ngapain": "apa",
            "kayak": "kados",
            "kalo": "menawi",
            "kalau": "menawi",
            "bisa": "saged",
            "udh": "wis",
            "gw": "kula",
            "gue": "kula",
            "gua": "kula",
            "lo": "panjenengan",
            "lu": "panjenengan",
            "loe": "panjenengan",
            "trus": "lajeng",
            "terus": "lajeng",
            "smua": "sedaya",
            "semua": "sedaya",
            "blm": "dereng",
            "belum": "dereng",
            "lg": "saweg",
            "lagi": "saweg",
            "spt": "kados",
            "seperti": "kados",
            "krn": "amargi",
            "karna": "amargi",
            "karena": "amargi",
            "tp": "nanging",
            "tapi": "nanging",
            "ato": "utawi",
            "atau": "utawi"
        }
    }

    OUTPUT.write_text(
        json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[+] Saved to: {OUTPUT}")
    print(f"[+] File size: {OUTPUT.stat().st_size} bytes")

    # Also save raw extraction for debug
    debug_path = Path("/home/z/my-project/scripts/jv_kamus_extracted.json")
    debug_path.write_text(
        json.dumps({
            "ngoko_to_krama": ngoko_to_krama_extracted,
            "ngoko_to_krama_inggil": ngoko_to_krama_inggil_extracted,
            "stats": dict(stats),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"[+] Debug extraction: {debug_path}")


if __name__ == "__main__":
    main()

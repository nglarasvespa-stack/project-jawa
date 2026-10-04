"""Analyze deeper: cari semua entries yang mention 'krama' dalam bentuk apa pun,
lihat semua kemungkinan format yang mungkin terlewat."""
import json
from pathlib import Path
from collections import Counter

INPUT = Path("/tmp/kaikki-jv.jsonl")

krama_entries = []
ngoko_entries = []
all_glosses_with_krama = []

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
        # cek semua senses
        for sense in d.get("senses", []):
            for g in sense.get("glosses", []):
                g_low = g.lower()
                if "krama" in g_low:
                    all_glosses_with_krama.append({
                        "word": word,
                        "gloss": g,
                        "pos": d.get("pos", "")
                    })
                    break

print(f"Total glosses mentioning 'krama': {len(all_glosses_with_krama)}")
print(f"\n=== Sample 30 ===")
for s in all_glosses_with_krama[:30]:
    print(f"  word={s['word']!r:30} pos={s['pos']:10} gloss={s['gloss']!r}")

print(f"\n=== Pattern analysis ===")
patterns = Counter()
for s in all_glosses_with_krama:
    g = s['gloss'].lower()
    if g.startswith("krama of"):
        patterns["Krama of X"] += 1
    elif g.startswith("krama inggil of"):
        patterns["Krama inggil of X"] += 1
    elif "ngoko" in g and "krama" in g:
        patterns["mentions_both_ngoko_krama"] += 1
    elif "krama form" in g:
        patterns["krama form"] += 1
    elif "krama register" in g or "krama level" in g:
        patterns["krama register/level"] += 1
    elif "krama version" in g:
        patterns["krama version"] += 1
    elif "informal" in g and "krama" in g:
        patterns["informal + krama"] += 1
    else:
        patterns[f"other"] += 1
        if patterns["other"] <= 30:
            print(f"  OTHER: {s}")
for p, c in patterns.most_common():
    print(f"  {p}: {c}")

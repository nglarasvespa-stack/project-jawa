"""Analyze kaikki.org Javanese JSONL untuk cari info ngoko/krama."""
import json
from collections import Counter
from pathlib import Path

input_file = Path("/tmp/kaikki-jv.jsonl")

total = 0
pos_counter = Counter()
entries_with_forms = 0
entries_with_synonyms = 0
entries_with_krama_tag = 0
entries_with_ngoko_tag = 0
sample_krama = []
sample_ngoko = []
sample_forms = []

with input_file.open() as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        pos = d.get("pos", "(none)")
        pos_counter[pos] += 1
        word = d.get("word", "")

        forms = d.get("forms", [])
        if forms:
            entries_with_forms += 1
            for form in forms:
                tags = form.get("tags", [])
                form_text = form.get("form", "")
                if "krama" in tags or "krama-inggil" in tags:
                    entries_with_krama_tag += 1
                    if len(sample_krama) < 15:
                        sample_krama.append({"word": word, "form": form_text, "tags": tags, "pos": pos})
                if "ngoko" in tags:
                    entries_with_ngoko_tag += 1
                    if len(sample_ngoko) < 15:
                        sample_ngoko.append({"word": word, "form": form_text, "tags": tags, "pos": pos})
                if len(sample_forms) < 10:
                    sample_forms.append({"word": word, "form": form_text, "tags": tags})

        senses = d.get("senses", [])
        for sense in senses:
            glosses = sense.get("glosses", [])
            for g in glosses:
                g_low = g.lower()
                if "krama" in g_low and len(sample_krama) < 30:
                    entries_with_krama_tag += 1
                    sample_krama.append({"word": word, "gloss": g, "pos": pos})
                    break
            for g in glosses:
                g_low = g.lower()
                if "ngoko" in g_low and len(sample_ngoko) < 30:
                    entries_with_ngoko_tag += 1
                    sample_ngoko.append({"word": word, "gloss": g, "pos": pos})
                    break

        related = d.get("related", []) + d.get("synonyms", [])
        if related:
            entries_with_synonyms += 1

print(f"=== Stats ===")
print(f"Total entries: {total}")
print(f"\nPOS distribution:")
for pos, count in pos_counter.most_common(15):
    print(f"  {pos}: {count}")
print(f"\nEntries with forms: {entries_with_forms}")
print(f"Entries with synonyms/related: {entries_with_synonyms}")
print(f"Entries mentioning 'krama': {entries_with_krama_tag}")
print(f"Entries mentioning 'ngoko': {entries_with_ngoko_tag}")
print(f"\n=== Sample entries with krama ===")
for s in sample_krama[:15]:
    print(f"  {s}")
print(f"\n=== Sample entries with ngoko ===")
for s in sample_ngoko[:15]:
    print(f"  {s}")
print(f"\n=== Sample forms ===")
for s in sample_forms[:10]:
    print(f"  {s}")

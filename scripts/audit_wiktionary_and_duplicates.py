#!/usr/bin/env python3
"""Audit:
1. Cari entries dengan source mengandung 'id-wiktionary' (multi-source merged)
2. Cek duplikat berdasarkan kombinasi (indonesian, ngoko, krama)
"""
import os, json, requests
from collections import Counter, defaultdict

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}

def fetch_all(filter_url, batch=1000):
    """Paginated fetch."""
    rows = []
    offset = 0
    while True:
        sep = '&' if '?' in filter_url else '?'
        url = f"{filter_url}{sep}offset={offset}&limit={batch}"
        r = requests.get(url, headers=H)
        r.raise_for_status()
        page = r.json()
        if not page: break
        rows.extend(page)
        if len(page) < batch: break
        offset += batch
    return rows

# 1. Cari entries dengan source mengandung 'id-wiktionary' (any position)
print("=== Entries dengan source mengandung 'id-wiktionary' (multi-source merged) ===")
# Use ilike with URL-encoded %
url = f"{URL}/rest/v1/kamus_draft?select=id,indonesian,ngoko,krama,source&source=ilike.*id-wiktionary*"
entries_with_wt = fetch_all(url)
print(f"Total: {len(entries_with_wt):,}")

# Breakdown per source value
source_counts = Counter(e['source'] for e in entries_with_wt)
print(f"\nSource value breakdown (yang mengandung 'id-wiktionary'):")
for s, c in source_counts.most_common(10):
    print(f"  {c:5,}  {s!r}")

# Sample
print(f"\nSample 10 (merged source):")
for e in entries_with_wt[:10]:
    print(f"  id={e.get('indonesian')!r:25s}  ngoko={e.get('ngoko')!r:25s}  krama={e.get('krama')!r:20s}  source={e['source']!r}")

# 2. Audit duplikat — fetch SEMUA entries
print(f"\n\n=== AUDIT DUPLIKAT ===")
print("Fetch semua kamus_draft (64k entries, mungkin butuh ~60 detik)...")
all_entries = fetch_all(f"{URL}/rest/v1/kamus_draft?select=id,indonesian,ngoko,krama,source")
print(f"Total fetched: {len(all_entries):,}")

# Group by (indonesian, ngoko, krama) — cari yang sama persis
dup_key = defaultdict(list)
for e in all_entries:
    key = (e.get('indonesian'), e.get('ngoko'), e.get('krama'))
    dup_key[key].append(e)

dups = {k: v for k, v in dup_key.items() if len(v) > 1}
total_dup_groups = len(dups)
total_dup_entries = sum(len(v) for v in dups.values())
print(f"\nDuplikat exact (indonesian+ngoko+krama sama persis):")
print(f"  Groups: {total_dup_groups:,}")
print(f"  Total duplicate entries: {total_dup_entries:,}")

# Sample 15 duplikat groups
print(f"\nSample 15 duplikat groups:")
for i, (key, entries) in enumerate(list(dups.items())[:15]):
    idn, ngoko, krama = key
    print(f"\n  [{i+1}] id={idn!r} ngoko={ngoko!r} krama={krama!r} ({len(entries)} duplikat):")
    for e in entries[:3]:
        print(f"      row id={e['id']} source={e['source']!r}")
    if len(entries) > 3:
        print(f"      ... dan {len(entries)-3} lainnya")

# Group by ngoko only (cek kalau satu ngoko punya banyak indonesian)
ngoko_groups = defaultdict(list)
for e in all_entries:
    if e.get('ngoko'):
        ngoko_groups[e['ngoko'].lower()].append(e)
ngoko_dups = {k: v for k, v in ngoko_groups.items() if len(v) > 1}
print(f"\n\n=== Ngoko yang punya beberapa entries ( Indonesian beda) ===")
print(f"  Total ngoko unik: {len(ngoko_groups):,}")
print(f"  Ngoko dengan >1 entry: {len(ngoko_dups):,}")
print(f"  Total entries di grup ini: {sum(len(v) for v in ngoko_dups.values()):,}")

# Sample
print(f"\nSample 10 ngoko dengan multiple Indonesian:")
sorted_ngoko = sorted(ngoko_dups.items(), key=lambda x: -len(x[1]))[:10]
for ngoko, entries in sorted_ngoko:
    print(f"  ngoko={ngoko!r} ({len(entries)} entries):")
    for e in entries[:5]:
        print(f"    id={e.get('indonesian')!r}  krama={e.get('krama')!r}  source={e['source']!r}")

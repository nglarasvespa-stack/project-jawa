#!/usr/bin/env python3
"""Rebuild kamus-draft-jawa.json — MERGE synonym groups by ngoko.

Berdasarkan audit:
- 5,349 ngoko dengan multiple Indonesian entries (12,895 total) = synonym groups
- 3,643 exact duplicates (id+ngoko+krama sama, source beda)

Strategy:
1. Fetch semua Lengkap entries
2. Group by ngoko (case-insensitive)
3. Untuk tiap group:
   - id: union dari semua indonesian + id_synonyms (comma-separated, dedup)
   - ngoko: union dari ngoko + dasanama (dedup)
   - krama: union dari krama + krama_inggil (dedup, MERGED)
4. Output 1 entry per ngoko group
"""
import os, json, requests
from collections import defaultdict

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}

OUT_PATH = '/home/z/my-project/download/kamus-draft-jawa.json'


def fetch_paginated(url_base, batch=1000):
    rows = []
    offset = 0
    while True:
        sep = '&' if '?' in url_base else '?'
        url = f"{url_base}{sep}offset={offset}&limit={batch}"
        r = requests.get(url, headers=H)
        r.raise_for_status()
        page = r.json()
        if not page: break
        rows.extend(page)
        if len(page) < batch: break
        offset += batch
    return rows


def dedup_join(items):
    seen = set()
    result = []
    for item in items:
        if not item: continue
        item = item.strip()
        if not item: continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return ', '.join(result) if result else None


def split_csv(s):
    if not s: return []
    return [x.strip() for x in s.split(',') if x.strip()]


def main():
    print("Fetching Lengkap entries dari kamus_draft...")
    entries = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=indonesian,ngoko,krama,krama_inggil,dasanama,id_synonyms,keterangan,source&"
        f"indonesian=not.is.null&ngoko=neq.&krama=not.is.null"
    )
    print(f"  Fetched: {len(entries):,} Lengkap entries (before merge)")

    # Group by indonesian (case-insensitive) — entries dengan same Indonesian = same concept
    groups = defaultdict(list)
    for e in entries:
        id_key = (e.get('indonesian') or '').strip().lower()
        if id_key:
            groups[id_key].append(e)
    print(f"  Unique Indonesian (id) groups: {len(groups):,}")

    # Build merged entries
    output = []
    multi_indonesian_groups = 0
    for ngoko_key, group_entries in groups.items():
        # Collect all indonesian + id_synonyms
        id_items = []
        for e in group_entries:
            if e.get('indonesian'):
                id_items.append(e['indonesian'])
            id_items.extend(split_csv(e.get('id_synonyms')))
        id_str = dedup_join(id_items)

        # Collect all ngoko + dasanama
        ngoko_items = []
        for e in group_entries:
            if e.get('ngoko'):
                ngoko_items.append(e['ngoko'])
            ngoko_items.extend(split_csv(e.get('dasanama')))
        ngoko_str = dedup_join(ngoko_items)

        # Collect all krama + krama_inggil (MERGED)
        krama_items = []
        for e in group_entries:
            if e.get('krama'):
                krama_items.append(e['krama'])
            if e.get('krama_inggil'):
                krama_items.append(e['krama_inggil'])
        krama_str = dedup_join(krama_items)

        # Skip kalau ada field kosong
        if not id_str or not ngoko_str or not krama_str:
            continue

        entry = {
            'id': id_str,
            'ngoko': ngoko_str,
            'krama': krama_str,
        }
        # Concat keterangan dari semua entries (unique)
        keterbangan_items = []
        for e in group_entries:
            if e.get('keterangan'):
                k = e['keterangan'].strip()
                if k and k not in keterbangan_items:
                    keterbangan_items.append(k)
        if keterbangan_items:
            entry['keterangan'] = ' | '.join(keterbangan_items)

        output.append(entry)

        if ',' in id_str or len(group_entries) > 1:
            multi_indonesian_groups += 1

    # Sort by id alphabetically
    output.sort(key=lambda x: x['id'].lower())

    print(f"\nMerged entries: {len(output):,}")
    print(f"  Groups with multiple Indonesian merged: {multi_indonesian_groups:,}")
    print(f"  Reduction: {len(entries) - len(output):,} entries merged away")

    # Save
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '2.0',
            'description': 'Kamus Jawa clean dengan sinonim per field. Entries di-MERGE by ngoko (synonym groups). krama_inggil di-merge ke krama.',
            'format': 'id, ngoko, krama (comma-separated sinonim per field)',
            'total_entries': len(output),
            'source': 'Supabase kamus_draft (Lengkap entries, merged by ngoko)',
            'merge_strategy': 'Group by ngoko (case-insensitive). Union all indonesian + id_synonyms → id. Union all ngoko + dasanama → ngoko. Union all krama + krama_inggil → krama.',
        },
        'entries': output,
    }

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved to {OUT_PATH}")
    print(f"  File size: {os.path.getsize(OUT_PATH):,} bytes")

    # Sample merged entries
    print(f"\n=== Sample 10 entries (after merge) ===")
    for e in output[:10]:
        print(f"  id={e['id']!r}")
        print(f"    ngoko={e['ngoko']!r}")
        print(f"    krama={e['krama']!r}")
        if e.get('keterangan'):
            print(f"    keterangan={e['keterangan'][:100]!r}...")
        print()

    # Find specific example: 'ada' (should be merged from 4 entries)
    print(f"=== Sample: 'ada' group (should be 1 merged entry) ===")
    for e in output:
        if e['id'].lower().startswith('ada'):
            print(f"  id={e['id']!r}")
            print(f"    ngoko={e['ngoko']!r}")
            print(f"    krama={e['krama']!r}")
            break


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Lookup Indonesian untuk 40,632 entries tanpa id.

Source EKSTERNAL (bukan AI halusinasi):
1. id_wiktionary_jv_id.json — 1,943 jv→id pairs
2. kamus_api_extracted.json — 2,978 id→ngoko (reverse: ngoko→id)
3. sastra_dict.csv — 11,310 rows (reverse: javanese→indonesian)
4. kamus_draft sendiri — entries dengan id+ngoko (build jv→id map)

Strategy:
1. Build reverse lookup: lowercase_jv_word → Indonesian
2. Fetch 40,632 entries dari kamus_draft (indonesian is null, ngoko not empty)
3. For each, look up ngoko word in reverse lookup
4. Bulk UPDATE kamus_draft SET indonesian = found_value
"""
import os, json, csv, requests, re
from collections import defaultdict

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}

# Source file paths (check both locations)
DATA_DIRS = [
    '/home/z/my-project/dub-jawa/data',
    '/tmp/my-project/dub-jawa/data',
]


def find_file(name):
    for d in DATA_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


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


def normalize(s):
    """Normalize untuk matching: lowercase, strip, remove accents."""
    if not s: return ''
    s = s.strip().lower()
    # Remove accents untuk fuzzy matching
    s = s.replace('é', 'e').replace('è', 'e').replace('ê', 'e')
    s = s.replace('É', 'e').replace('È', 'e').replace('Ê', 'e')
    s = s.replace('á', 'a').replace('à', 'a')
    s = s.replace('ñ', 'n').replace('ç', 'c')
    return s


def main():
    # === STEP 1: Build reverse lookup ===
    print("=" * 60)
    print("STEP 1: Build reverse lookup (jv word → Indonesian)")
    print("=" * 60)
    
    # Direct lookup: lowercase jv → set of Indonesian words
    direct_lookup = defaultdict(set)
    # Normalized lookup: normalized jv → set of Indonesian words (for accent-insensitive matching)
    norm_lookup = defaultdict(set)
    
    # Source 1: id_wiktionary_jv_id.json
    p = find_file('id_wiktionary_jv_id.json')
    if p:
        print(f"\nSource 1: {p}")
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        entries = d.get('entries', [])
        for e in entries:
            jv = (e.get('jv') or '').strip()
            idn = (e.get('id') or '').strip()
            if jv and idn:
                direct_lookup[jv.lower()].add(idn)
                norm_lookup[normalize(jv)].add(idn)
        print(f"  {len(entries):,} entries → {len(direct_lookup):,} unique jv keys")
    
    # Source 2: kamus_api_extracted.json (reverse id_to_ngomo)
    p = find_file('kamus_api_extracted.json')
    if p:
        print(f"\nSource 2: {p}")
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        id_to_ngoko = d.get('id_to_ngoko', {})
        for idn, ngoko in id_to_ngoko.items():
            if idn and ngoko:
                # Reverse: ngoko → indonesian
                direct_lookup[ngoko.lower()].add(idn)
                norm_lookup[normalize(ngoko)].add(idn)
        print(f"  {len(id_to_ngoko):,} id→ngoko pairs (reversed)")
    
    # Source 3: sastra_dict.csv (reverse)
    p = find_file('sastra_dict.csv')
    if p:
        print(f"\nSource 3: {p}")
        with open(p, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                idn = (row.get('Indonesia') or '').strip()
                jvn = (row.get('Javanese') or '').strip()
                if idn and jvn:
                    # Javanese might have multiple words separated by ;
                    for jv_part in jvn.split(';'):
                        jv_part = jv_part.strip()
                        if jv_part:
                            direct_lookup[jv_part.lower()].add(idn)
                            norm_lookup[normalize(jv_part)].add(idn)
                    count += 1
        print(f"  {count:,} rows processed")
    
    # Source 4: kamus_draft sendiri (entries dengan id+ngoko)
    print(f"\nSource 4: kamus_draft entries dengan id+ngoko (internal)")
    existing = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=indonesian,ngoko&"
        f"indonesian=not.is.null&ngoko=neq.&limit=10000"
    )
    count = 0
    for e in existing:
        idn = (e.get('indonesian') or '').strip()
        ngoko = (e.get('ngoko') or '').strip()
        if idn and ngoko:
            direct_lookup[ngoko.lower()].add(idn)
            norm_lookup[normalize(ngoko)].add(idn)
            count += 1
    print(f"  {count:,} entries with id+ngoko → added to lookup")
    
    print(f"\n  Total direct lookup keys: {len(direct_lookup):,}")
    print(f"  Total normalized lookup keys: {len(norm_lookup):,}")
    
    # === STEP 2: Fetch entries without Indonesian ===
    print("\n" + "=" * 60)
    print("STEP 2: Fetch entries tanpa Indonesian (40,632)")
    print("=" * 60)
    
    no_id = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=id,ngoko,indonesian&"
        f"or=(indonesian.is.null)&ngoko=neq."
    )
    print(f"  Fetched: {len(no_id):,} entries without Indonesian")
    
    # === STEP 3: Look up Indonesian for each ===
    print("\n" + "=" * 60)
    print("STEP 3: Lookup Indonesian untuk tiap entry")
    print("=" * 60)
    
    to_update = []  # (row_id, indonesian, method)
    method_counts = defaultdict(int)
    
    for e in no_id:
        row_id = e['id']
        ngoko = (e.get('ngoko') or '').strip()
        ngoko_lower = ngoko.lower()
        ngoko_norm = normalize(ngoko)
        
        # Try exact match first
        if ngoko_lower in direct_lookup:
            idns = direct_lookup[ngoko_lower]
            if len(idns) == 1:
                idn = list(idns)[0]
                to_update.append((row_id, idn, 'direct_exact'))
                method_counts['direct_exact'] += 1
                continue
            elif len(idns) > 1:
                # Multiple Indonesian words for same jv word — pick first
                idn = sorted(idns)[0]
                to_update.append((row_id, idn, 'direct_exact_multi'))
                method_counts['direct_exact_multi'] += 1
                continue
        
        # Try normalized match (accent-insensitive)
        if ngoko_norm in norm_lookup:
            idns = norm_lookup[ngoko_norm]
            if len(idns) == 1:
                idn = list(idns)[0]
                to_update.append((row_id, idn, 'normalized'))
                method_counts['normalized'] += 1
                continue
            elif len(idns) > 1:
                idn = sorted(idns)[0]
                to_update.append((row_id, idn, 'normalized_multi'))
                method_counts['normalized_multi'] += 1
                continue
        
        method_counts['NO_MATCH'] += 1
    
    print(f"\n=== Results ===")
    for m, c in sorted(method_counts.items(), key=lambda x: -x[1]):
        print(f"  {m}: {c:,}")
    print(f"  TOTAL to update: {len(to_update):,}")
    
    if not to_update:
        print("\nTidak ada yang bisa di-update.")
        return
    
    # === STEP 4: Bulk UPDATE ===
    print(f"\n" + "=" * 60)
    print(f"STEP 4: UPDATE {len(to_update):,} entries di kamus_draft")
    print("=" * 60)
    
    BATCH = 100
    total_updated = 0
    for i in range(0, len(to_update), BATCH):
        chunk = to_update[i:i+BATCH]
        for row_id, idn, method in chunk:
            r = requests.patch(
                f"{URL}/rest/v1/kamus_draft?id=eq.{row_id}",
                headers=H,
                json={'indonesian': idn},
            )
            if r.status_code in (200, 204):
                total_updated += 1
            else:
                print(f"    ERROR row {row_id}: {r.status_code} {r.text[:200]}")
        if (i + BATCH) % 1000 < BATCH:
            print(f"  [{total_updated:,}/{len(to_update):,}] updated")
    
    print(f"\n✓ Done. {total_updated:,} entries updated dengan Indonesian dari external kamus.")


if __name__ == '__main__':
    main()

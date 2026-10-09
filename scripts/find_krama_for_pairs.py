#!/usr/bin/env python3
"""Cari krama untuk 19,976 entries dengan id+ngoko (krama null).

Method:
1. Build lookup dari kamus_draft Lengkap entries (id+ngoko+krama all filled)
   - Key: (indonesian_lower, ngoko_lower) → krama
   - Also: indonesian_lower → krama (fallback — copy krama dari entry Lengkap dengan same Indonesian)
2. Build lookup dari jvwiktionary_ngoko_krama.json (2,336 pairs)
   - Key: ngoko_lower → (krama, krama_inggil)
3. For each Netral entry (id+ngoko, krama null):
   a. Try (indonesian_lower, ngoko_lower) lookup from Lengkap
   b. If not found, try ngoko_lower lookup from jvwiktionary
   c. If not found, try indonesian_lower lookup from Lengkap (any krama for same Indonesian)
4. Bulk UPDATE kamus_draft SET krama = X WHERE id = Y
"""
import os, json, requests
from collections import defaultdict

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}

NGOKO_KRAMA_PATH = '/home/z/my-project/dub-jawa/jvwiktionary_ngoko_krama.json'


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


def main():
    # Step 1: Fetch Lengkap entries (id+ngoko+krama all filled) — build lookup
    print("Step 1: Fetch Lengkap entries dari kamus_draft...")
    lengkap = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=id,indonesian,ngoko,krama,krama_inggil&"
        f"indonesian=not.is.null&ngoko=neq.&krama=not.is.null"
    )
    print(f"  {len(lengkap):,} Lengkap entries")
    
    # Build lookup 1: (indonesian_lower, ngoko_lower) → (krama, krama_inggil)
    lookup_id_ngoko = {}
    # Build lookup 2: indonesian_lower → [(krama, krama_inggil), ...]  (any krama for same Indonesian)
    lookup_id_only = defaultdict(list)
    
    for e in lengkap:
        idn = (e.get('indonesian') or '').strip().lower()
        ngoko = (e.get('ngoko') or '').strip().lower()
        krama = e.get('krama')
        inggil = e.get('krama_inggil')
        
        if idn and ngoko and krama:
            key = (idn, ngoko)
            if key not in lookup_id_ngoko:
                lookup_id_ngoko[key] = (krama, inggil)
        if idn and krama:
            lookup_id_only[idn].append((krama, inggil, ngoko))
    
    print(f"  Lookup (id, ngoko) → krama: {len(lookup_id_ngoko):,}")
    print(f"  Lookup id → krama: {len(lookup_id_only):,}")
    
    # Step 2: Load jvwiktionary ngoko-krama pairs
    print("\nStep 2: Load jvwiktionary ngoko-krama pairs...")
    with open(NGOKO_KRAMA_PATH, encoding='utf-8') as f:
        jv_pairs = json.load(f)['pairs']
    
    # Build lookup 3: ngoko_lower → (krama, krama_inggil)
    lookup_ngoko = {}
    for p in jv_pairs:
        key = p['ngoko'].lower().strip()
        if key and key not in lookup_ngoko:
            lookup_ngoko[key] = (p['krama'], p.get('krama_inggil'))
    print(f"  Lookup ngoko → krama: {len(lookup_ngoko):,}")
    
    # Step 3: Fetch Netral entries (id+ngoko, krama null)
    print("\nStep 3: Fetch Netral entries (id+ngoko, krama null)...")
    netral = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=id,indonesian,ngoko,krama&"
        f"indonesian=not.is.null&ngoko=neq.&or=(krama.is.null)"
    )
    print(f"  {len(netral):,} Netral entries")
    
    # Step 4: For each Netral entry, try to find krama
    print("\nStep 4: Cari krama untuk tiap Netral entry...")
    
    to_update = []  # list of (row_id, krama, krama_inggil, method)
    method_counts = defaultdict(int)
    
    for e in netral:
        row_id = e['id']
        idn = (e.get('indonesian') or '').strip().lower()
        ngoko = (e.get('ngoko') or '').strip().lower()
        
        # Method 1: (id, ngoko) → krama (exact match with Lengkap)
        key = (idn, ngoko)
        if key in lookup_id_ngoko:
            krama, inggil = lookup_id_ngoko[key]
            to_update.append((row_id, krama, inggil, 'lengkap_match_id_ngoko'))
            method_counts['lengkap_match_id_ngoko'] += 1
            continue
        
        # Method 2: ngoko → krama (from jvwiktionary)
        if ngoko in lookup_ngoko:
            krama, inggil = lookup_ngoko[ngoko]
            to_update.append((row_id, krama, inggil, 'jvwiktionary_ngoko'))
            method_counts['jvwiktionary_ngoko'] += 1
            continue
        
        # Method 3: id → krama (any Lengkap with same Indonesian) — fallback
        # Only use if there's exactly 1 krama option (to avoid ambiguity)
        if idn in lookup_id_only:
            options = lookup_id_only[idn]
            unique_kramas = set(o[0].lower() for o in options if o[0])
            if len(unique_kramas) == 1:
                # Only one krama option, safe to use
                krama, inggil, source_ngoko = options[0]
                to_update.append((row_id, krama, inggil, f'lengkap_match_id_only (ngoko was {source_ngoko})'))
                method_counts['lengkap_match_id_only'] += 1
                continue
        
        method_counts['NO_MATCH'] += 1
    
    print(f"\n=== Results ===")
    for m, c in method_counts.items():
        print(f"  {m}: {c:,}")
    print(f"  TOTAL to update: {len(to_update):,}")
    
    if not to_update:
        print("\nTidak ada yang bisa di-update.")
        return
    
    # Step 5: Bulk UPDATE kamus_draft
    print(f"\nStep 5: UPDATE {len(to_update):,} entries di kamus_draft...")
    BATCH = 100
    total_updated = 0
    for i in range(0, len(to_update), BATCH):
        chunk = to_update[i:i+BATCH]
        for row_id, krama, inggil, method in chunk:
            update_payload = {'krama': krama}
            if inggil:
                update_payload['krama_inggil'] = inggil
            r = requests.patch(
                f"{URL}/rest/v1/kamus_draft?id=eq.{row_id}",
                headers=H,
                json=update_payload,
            )
            if r.status_code not in (200, 204):
                print(f"    ERROR row {row_id}: {r.status_code} {r.text[:200]}")
                continue
            total_updated += 1
        print(f"  [{total_updated:,}/{len(to_update):,}] updated")
    
    print(f"\n✓ Done. {total_updated:,} entries updated dengan krama.")


if __name__ == '__main__':
    main()

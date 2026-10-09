#!/usr/bin/env python3
"""Cross-reference:
- Lengkap entries (id+ngoko+krama) — 2,917
- Netral entries (id+ngoko, krama null) — 18,904

Cari:
1. DUPLIKAT: Netral dengan (id, ngoko) SAMA PERSIS dengan Lengkap → krama bisa di-fill
2. SINONIM by ngoko: Banyak entries (Lengkap + Netral) dengan ngoko sama tapi id beda
3. SINONIM by id: Banyak entries (Lengkap + Netral) dengan id sama tapi ngoko beda
"""
import os, json, requests
from collections import defaultdict, Counter

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}

OUT_PATH = '/home/z/my-project/download/cross-reference-report.json'


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
    print("Fetching Lengkap + Netral entries dari kamus_draft...")
    
    # Lengkap: id+ngoko+krama all filled
    lengkap = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=id,indonesian,ngoko,krama,krama_inggil,source&"
        f"indonesian=not.is.null&ngoko=neq.&krama=not.is.null"
    )
    print(f"  Lengkap entries: {len(lengkap):,}")
    
    # Netral: id+ngoko filled, krama null
    netral = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=id,indonesian,ngoko,krama,krama_inggil,source&"
        f"indonesian=not.is.null&ngoko=neq.&or=(krama.is.null)"
    )
    print(f"  Netral entries (id+ngoko): {len(netral):,}")
    
    # === CROSS-REFERENCE 1: DUPLIKAT (Netral punya (id, ngoko) sama dengan Lengkap) ===
    print("\n=== CROSS-REFERENCE 1: DUPLIKAT ===")
    # Build lookup: (id_lower, ngoko_lower) → (krama, krama_inggil, row_id) from Lengkap
    lengkap_lookup = {}
    for e in lengkap:
        idn = (e.get('indonesian') or '').strip().lower()
        ngoko = (e.get('ngoko') or '').strip().lower()
        krama = e.get('krama')
        inggil = e.get('krama_inggil')
        if idn and ngoko and krama:
            key = (idn, ngoko)
            if key not in lengkap_lookup:
                lengkap_lookup[key] = (krama, inggil, e['id'])
    
    print(f"  Lengkap lookup (id, ngoko) → krama: {len(lengkap_lookup):,}")
    
    # Find Netral entries that match
    duplicates = []
    for e in netral:
        idn = (e.get('indonesian') or '').strip().lower()
        ngoko = (e.get('ngoko') or '').strip().lower()
        key = (idn, ngoko)
        if key in lengkap_lookup:
            krama, inggil, lengkap_row_id = lengkap_lookup[key]
            duplicates.append({
                'netral_row_id': e['id'],
                'lengkap_row_id': lengkap_row_id,
                'id': e.get('indonesian'),
                'ngoko': e.get('ngoko'),
                'krama_to_fill': krama,
                'krama_inggil_to_fill': inggil,
            })
    
    print(f"  Duplicates found: {len(duplicates):,} (Netral yang (id, ngoko) = Lengkap)")
    
    # Bulk UPDATE: fill krama for these duplicates
    if duplicates:
        print(f"  Updating {len(duplicates):,} Netral entries dengan krama...")
        BATCH = 100
        updated = 0
        for i in range(0, len(duplicates), BATCH):
            chunk = duplicates[i:i+BATCH]
            for d in chunk:
                payload = {'krama': d['krama_to_fill']}
                if d.get('krama_inggil_to_fill'):
                    payload['krama_inggil'] = d['krama_inggil_to_fill']
                r = requests.patch(
                    f"{URL}/rest/v1/kamus_draft?id=eq.{d['netral_row_id']}",
                    headers={**H, 'Prefer': 'return=minimal'},
                    json=payload,
                )
                if r.status_code in (200, 204):
                    updated += 1
                else:
                    print(f"    ERROR row {d['netral_row_id']}: {r.status_code} {r.text[:200]}")
            if (i + BATCH) % 500 < BATCH:
                print(f"  [{updated:,}/{len(duplicates):,}] updated")
        print(f"  ✓ Updated {updated:,} duplicates dengan krama dari Lengkap")
    
    # === CROSS-REFERENCE 2: SINONIM BY NGOKO ===
    # Multiple entries (Lengkap + Netral) dengan ngoko sama tapi id beda
    print("\n=== CROSS-REFERENCE 2: SINONIM BY NGOKO ===")
    # Group ALL entries (Lengkap + Netral) by ngoko
    all_entries = lengkap + netral
    ngoko_groups = defaultdict(list)
    for e in all_entries:
        ngoko = (e.get('ngoko') or '').strip().lower()
        if ngoko:
            ngoko_groups[ngoko].append(e)
    
    multi_ngoko = {k: v for k, v in ngoko_groups.items() if len(v) > 1}
    print(f"  Total unique ngoko: {len(ngoko_groups):,}")
    print(f"  Ngoko dengan multiple entries (sinonim/homonym candidates): {len(multi_ngoko):,}")
    
    # Get top 10 by count
    top_ngoko = sorted(multi_ngoko.items(), key=lambda x: -len(x[1]))[:10]
    print(f"\n  Top 10 ngoko dengan most entries:")
    for ngoko, entries in top_ngoko:
        ids = list(set((e.get('indonesian') or '') for e in entries))[:5]
        print(f"    ngoko={ngoko!r} ({len(entries)} entries, sample ids: {ids})")
    
    # === CROSS-REFERENCE 3: SINONIM BY ID ===
    # Multiple entries dengan id sama tapi ngoko beda
    print("\n=== CROSS-REFERENCE 3: SINONIM BY ID ===")
    id_groups = defaultdict(list)
    for e in all_entries:
        idn = (e.get('indonesian') or '').strip().lower()
        if idn:
            id_groups[idn].append(e)
    
    multi_id = {k: v for k, v in id_groups.items() if len(v) > 1}
    print(f"  Total unique id: {len(id_groups):,}")
    print(f"  Id dengan multiple entries (sinonim candidates): {len(multi_id):,}")
    
    # Get top 10 by count
    top_id = sorted(multi_id.items(), key=lambda x: -len(x[1]))[:10]
    print(f"\n  Top 10 id dengan most entries:")
    for idn, entries in top_id:
        ngokos = list(set((e.get('ngoko') or '') for e in entries))[:5]
        print(f"    id={idn!r} ({len(entries)} entries, sample ngokos: {ngokos})")
    
    # === SAVE REPORT ===
    # Build sample reports for top synonyms
    sample_synonym_ngoko = []
    for ngoko, entries in top_ngoko[:20]:
        sample_synonym_ngoko.append({
            'ngoko': ngoko,
            'entry_count': len(entries),
            'indonesians': list(set(e.get('indonesian') for e in entries if e.get('indonesian')))[:10],
        })
    
    sample_synonym_id = []
    for idn, entries in top_id[:20]:
        sample_synonym_id.append({
            'id': idn,
            'entry_count': len(entries),
            'ngokos': list(set(e.get('ngoko') for e in entries if e.get('ngoko')))[:10],
        })
    
    output = {
        'meta': {
            'description': 'Cross-reference report: duplikat + sinonim by ngoko + sinonim by id',
            'lengkap_count': len(lengkap),
            'netral_count': len(netral),
            'duplicates_filled': len(duplicates),
            'synonym_groups_by_ngoko': len(multi_ngoko),
            'synonym_groups_by_id': len(multi_id),
        },
        'duplicates_filled': duplicates[:50],  # sample
        'synonym_by_ngoko_top20': sample_synonym_ngoko,
        'synonym_by_id_top20': sample_synonym_id,
    }
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved report to {OUT_PATH}")


if __name__ == '__main__':
    main()

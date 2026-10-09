#!/usr/bin/env python3
"""Cari pasangan ngoko+krama untuk 20 Netral entries (dengan Indonesian).

Strategy baru (lebih efektif):
1. Load 2,336 ngoko-krama pairs dari jvwiktionary_ngoko_krama.json
2. Untuk tiap pair, search kamus_draft:
   - Entries dengan ngoko = pair.ngoko (Indonesian != null, krama = null)
   - OR entries dengan krama = pair.krama (Indonesian != null, ngoko = null OR krama_inggil is null)
3. Output sebagai Lengkap pair {id, ngoko, krama, krama_inggil}
4. Stop setelah 20 entries
"""
import os, json, requests
from pathlib import Path

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}

OUT_PATH = '/home/z/my-project/download/kamus-pair-found-20.json'
NGOKO_KRAMA_PATH = '/home/z/my-project/dub-jawa/jvwiktionary_ngoko_krama.json'


def main():
    print("Loading jvwiktionary ngoko-krama pairs...")
    with open(NGOKO_KRAMA_PATH, encoding='utf-8') as f:
        pairs = json.load(f)['pairs']
    print(f"  {len(pairs):,} pairs loaded")
    
    print(f"\nSearching kamus_draft for entries that match these pairs...")
    print(f"  (cuma yang punya Indonesian + krama null = Netral dengan id)")
    
    found_pairs = []
    seen_entry_ids = set()
    
    for i, p in enumerate(pairs):
        ngoko = p['ngoko']
        krama = p['krama']
        inggil = p.get('krama_inggil')
        
        # Search kamus_draft for entries with ngoko=pair.ngoko, indonesian != null, krama = null
        url = (
            f"{URL}/rest/v1/kamus_draft?"
            f"select=id,indonesian,ngoko,krama,krama_inggil,source&"
            f"ngoko=eq.{requests.utils.quote(ngoko)}&"
            f"indonesian=not.is.null&"
            f"or=(krama.is.null)&limit=10"
        )
        r = requests.get(url, headers=H)
        if r.status_code != 200:
            continue
        matches = r.json()
        
        for m in matches:
            row_id = m['id']
            if row_id in seen_entry_ids:
                continue
            seen_entry_ids.add(row_id)
            
            indonesian = m.get('indonesian')
            # We know the ngoko is correct (matched), and pair.krama gives us the krama
            found_pairs.append({
                'row_id': row_id,
                'id': indonesian,
                'ngoko': ngoko,
                'krama': krama,
                'krama_inggil': inggil,
                'method': 'jvwiktionary ngoko match → fill krama',
                'original_source': m.get('source'),
            })
            
            if len(found_pairs) >= 20:
                break
        
        if len(found_pairs) >= 20:
            break
        
        if (i+1) % 200 == 0:
            print(f"  Processed {i+1}/{len(pairs)} pairs, found {len(found_pairs)} matches so far")
    
    print(f"\n=== Found {len(found_pairs)} pairs (target: 20) ===")
    
    # Show details
    for i, fp in enumerate(found_pairs):
        print(f"\n[{i+1}] row_id={fp['row_id']}")
        print(f"    id={fp['id']!r}")
        print(f"    ngoko={fp['ngoko']!r}")
        print(f"    krama={fp['krama']!r}" + (f"  krama_inggil={fp['krama_inggil']!r}" if fp.get('krama_inggil') else ''))
        print(f"    method: {fp['method']}")
    
    # Save
    output = {
        'meta': {
            'description': '20 Netral entries yang berhasil ditemukan pasangan ngoko+krama dari jvwiktionary.',
            'method': 'Search kamus_draft (Netral entries with Indonesian) by ngoko word, match to jvwiktionary ngoko-krama pairs.',
            'total_found': len(found_pairs),
            'target': 20,
        },
        'entries': found_pairs,
    }
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved to {OUT_PATH}")


if __name__ == '__main__':
    main()

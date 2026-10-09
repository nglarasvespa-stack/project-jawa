#!/usr/bin/env python3
"""Buat kamus-draft-jawa.json — versi clean dengan sinonim per field.

Format tiap entry:
  {
    "id": "merah, merah muda",          # indonesian + id_synonyms
    "ngoko": "abang, mera",             # ngoko + dasanama
    "krama": "abrit, sita"              # krama + krama_inggil (merged)
  }

Hanya entry Lengkap (id+ngoko+krama semua terisi).
Source: Supabase kamus_draft table.
"""
import os, json, requests

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
    """Dedup list of strings, preserve order, return comma-separated string."""
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        item = item.strip()
        if not item:
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return ', '.join(result) if result else None


def split_csv(s):
    """Split comma-separated string → list of stripped items."""
    if not s:
        return []
    return [x.strip() for x in s.split(',') if x.strip()]


def main():
    print("Fetching Lengkap entries dari kamus_draft...")
    # Get entries with id+ngoko+krama all filled
    entries = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=indonesian,ngoko,krama,krama_inggil,dasanama,id_synonyms,keterangan,source&"
        f"indonesian=not.is.null&ngoko=neq.&krama=not.is.null"
    )
    print(f"  Fetched: {len(entries):,} Lengkap entries")

    # Build new format
    output = []
    for e in entries:
        # id = indonesian + id_synonyms
        id_items = []
        if e.get('indonesian'):
            id_items.append(e['indonesian'])
        id_items.extend(split_csv(e.get('id_synonyms')))
        id_str = dedup_join(id_items)

        # ngoko = ngoko + dasanama
        ngoko_items = []
        if e.get('ngoko'):
            ngoko_items.append(e['ngoko'])
        ngoko_items.extend(split_csv(e.get('dasanama')))
        ngoko_str = dedup_join(ngoko_items)

        # krama = krama + krama_inggil (MERGED)
        krama_items = []
        if e.get('krama'):
            krama_items.append(e['krama'])
        if e.get('krama_inggil'):
            krama_items.append(e['krama_inggil'])
        krama_str = dedup_join(krama_items)

        # Skip kalau ada field yang kosong setelah merge
        if not id_str or not ngoko_str or not krama_str:
            continue

        entry = {
            'id': id_str,
            'ngoko': ngoko_str,
            'krama': krama_str,
        }
        # Tambah keterangan kalau ada (sebagai catatan tambahan)
        if e.get('keterangan'):
            entry['keterangan'] = e['keterangan']

        output.append(entry)

    # Sort by id alphabetically
    output.sort(key=lambda x: x['id'].lower())

    print(f"\nBuilt {len(output):,} clean entries")

    # Save
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '1.0',
            'description': 'Kamus Jawa clean dengan sinonim per field. krama_inggil di-merge ke krama. Hanya entries Lengkap (id+ngoko+krama semua terisi).',
            'format': 'id, ngoko, krama (comma-separated sinonim per field)',
            'total_entries': len(output),
            'source': 'Supabase kamus_draft (Lengkap entries)',
        },
        'entries': output,
    }

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved to {OUT_PATH}")
    print(f"  File size: {os.path.getsize(OUT_PATH):,} bytes")

    # Sample
    print(f"\n=== Sample 10 entries ===")
    for e in output[:10]:
        print(f"  id={e['id']!r}")
        print(f"    ngoko={e['ngoko']!r}")
        print(f"    krama={e['krama']!r}")
        if e.get('keterangan'):
            print(f"    keterangan={e['keterangan']!r}")
        print()

    # Stats
    multi_id = sum(1 for e in output if ',' in e['id'])
    multi_ngoko = sum(1 for e in output if ',' in e['ngoko'])
    multi_krama = sum(1 for e in output if ',' in e['krama'])
    print(f"=== Stats ===")
    print(f"  Total entries: {len(output):,}")
    print(f"  Entries dengan multiple id sinonim: {multi_id:,}")
    print(f"  Entries dengan multiple ngoko sinonim: {multi_ngoko:,}")
    print(f"  Entries dengan multiple krama sinonim (incl krama_inggil): {multi_krama:,}")


if __name__ == '__main__':
    main()

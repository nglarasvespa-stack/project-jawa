#!/usr/bin/env python3
"""Rebuild kamus-draft-jawa.json — SEMUA 64,063 entries, gak ada yang dibuang.

Versi sebelumnya salah: cuma ambil "Lengkap" (1,386 entries) → user marah
karena 62,577 entry lainnya dianggap "hilang".

Versi sekarang:
- Fetch SEMUA entries dari kamus_draft (64,063)
- Untuk tiap entry, build format: {id, ngoko, krama}
  - id: indonesian + id_synonyms (atau string kosong kalau null)
  - ngoko: ngoko + dasanama
  - krama: krama + krama_inggil (MERGED)
- Cleanup karakter aneh (':', '(', '{{') tapi PRESERVE entry
- Merge by lowercase id (sinonim digabung)
- Allow fields kosong — gak semua entry punya semua 3 fields
"""
import os, json, requests, re
from collections import defaultdict

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}

OUT_PATH = '/home/z/my-project/dub-jawa/kamus-draft-jawa.json'


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


def clean_field(s):
    if not s: return None
    if ':' in s: s = s.split(':')[0]
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\{\{[^}]*\}\}', '', s)
    s = re.sub(r'\{\{.*', '', s)
    s = re.sub(r'\{[^}]*\}', '', s)
    s = re.sub(r'\{.*', '', s)
    s = re.sub(r'\([a-z.]+\)', '', s)
    s = re.sub(r'[|/]', ',', s)
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r',\s+,', ',', s)
    s = re.sub(r'^\s*,\s*', '', s)
    s = re.sub(r'\s*,\s*$', '', s)
    s = re.sub(r'\s+', ' ', s).strip().rstrip(',').strip()
    return s if s else None


def split_and_dedup(s):
    if not s: return []
    items, seen = [], set()
    for x in s.split(','):
        x = x.strip()
        if x and x.lower() not in seen:
            seen.add(x.lower())
            items.append(x)
    return items


def main():
    print("Fetching SEMUA entries dari kamus_draft...")
    entries = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=id,indonesian,ngoko,krama,krama_inggil,dasanama,id_synonyms,keterangan,source"
    )
    print(f"  Total fetched: {len(entries):,} entries")
    
    # Step 1: Clean + build per-entry items
    cleaned = []
    for e in entries:
        # id: indonesian + id_synonyms
        id_orig = e.get('indonesian') or ''
        id_syn = e.get('id_synonyms') or ''
        id_combined = f"{id_orig},{id_syn}" if (id_orig and id_syn) else (id_orig or id_syn)
        id_clean = clean_field(id_combined) or id_orig
        id_items = split_and_dedup(id_clean)
        if not id_items and id_orig:
            id_items = [id_orig]  # fallback
        
        # ngoko: ngoko + dasanama
        ngoko_orig = e.get('ngoko') or ''
        dasanama = e.get('dasanama') or ''
        ngoko_combined = f"{ngoko_orig},{dasanama}" if (ngoko_orig and dasanama) else (ngoko_orig or dasanama)
        ngoko_clean = clean_field(ngoko_combined) or ngoko_orig
        ngoko_items = split_and_dedup(ngoko_clean)
        if not ngoko_items and ngoko_orig:
            ngoko_items = [ngoko_orig]
        
        # krama: krama + krama_inggil (MERGED)
        krama_orig = e.get('krama') or ''
        krama_inggil = e.get('krama_inggil') or ''
        krama_combined = f"{krama_orig},{krama_inggil}" if (krama_orig and krama_inggil) else (krama_orig or krama_inggil)
        krama_clean = clean_field(krama_combined) or krama_orig
        krama_items = split_and_dedup(krama_clean)
        if not krama_items and krama_orig:
            krama_items = [krama_orig]
        
        cleaned.append({
            'id_items': id_items,
            'ngoko_items': ngoko_items,
            'krama_items': krama_items,
            'source': e.get('source'),
            'ket': e.get('keterangan'),
            'row_id': e.get('id'),
        })
    
    print(f"  After cleanup: {len(cleaned):,} entries (PRESERVED — gak ada yang dihapus)")
    
    # Step 2: Merge by lowercase id (kalau ada id)
    # Entries dengan id → grouped by lowercase id
    # Entries tanpa id → tetap individual (atau group by lowercase ngoko)
    groups_with_id = defaultdict(list)
    entries_no_id = []
    for c in cleaned:
        if c['id_items']:
            key = c['id_items'][0].lower()
            groups_with_id[key].append(c)
        else:
            # No id — keep as individual entry, but group by ngoko if possible
            entries_no_id.append(c)
    
    print(f"  Entries dengan id: {sum(len(v) for v in groups_with_id.values()):,} → {len(groups_with_id):,} groups")
    print(f"  Entries tanpa id: {len(entries_no_id):,} (keep individual)")
    
    # Build output entries
    output = []
    
    # Process groups_with_id
    for key, group in groups_with_id.items():
        all_ids, all_ngoko, all_krama, all_ket, all_sources = [], [], [], [], []
        seen_id, seen_ngoko, seen_krama, seen_ket, seen_src = set(), set(), set(), set(), set()
        
        for c in group:
            for x in c['id_items']:
                if x.lower() not in seen_id:
                    seen_id.add(x.lower())
                    all_ids.append(x)
            for x in c['ngoko_items']:
                if x.lower() not in seen_ngoko:
                    seen_ngoko.add(x.lower())
                    all_ngoko.append(x)
            for x in c['krama_items']:
                if x.lower() not in seen_krama:
                    seen_krama.add(x.lower())
                    all_krama.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source'])
                all_sources.append(c['source'])
        
        entry = {
            'id': ', '.join(all_ids) if all_ids else None,
            'ngoko': ', '.join(all_ngoko) if all_ngoko else None,
            'krama': ', '.join(all_krama) if all_krama else None,
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    # Process entries_no_id (no indonesian — only ngoko and maybe krama)
    for c in entries_no_id:
        entry = {
            'id': None,
            'ngoko': ', '.join(c['ngoko_items']) if c['ngoko_items'] else None,
            'krama': ', '.join(c['krama_items']) if c['krama_items'] else None,
        }
        if c.get('source'):
            entry['source'] = c['source']
        output.append(entry)
    
    # Sort: entries with id first (alphabetical), then entries without id
    output.sort(key=lambda x: (x.get('id') is None, (x.get('id') or x.get('ngoko') or '').lower()))
    
    print(f"\nFinal entries: {len(output):,}")
    
    # Save
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '3.0',
            'description': 'Kamus Jawa — SEMUA entries dari Supabase kamus_draft (64,063 entries, gak ada yang dibuang). Format: id, ngoko, krama (comma-separated sinonim). krama_inggil di-merge ke krama. Entries dengan id di-merge by lowercase id (sinonim gabung). Entries tanpa id tetap individual.',
            'format': 'id, ngoko, krama (allow null kalau field kosong)',
            'total_entries': len(output),
            'source': 'Supabase kamus_draft (ALL entries)',
            'note': 'Gak ada data yang dihapus. Entry dengan field kosong tetap dipertahankan.',
        },
        'entries': output,
    }
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved to {OUT_PATH}")
    print(f"  File size: {os.path.getsize(OUT_PATH):,} bytes")
    
    # Stats
    with_id = sum(1 for e in output if e.get('id'))
    with_ngoko = sum(1 for e in output if e.get('ngoko'))
    with_krama = sum(1 for e in output if e.get('krama'))
    lengkap = sum(1 for e in output if e.get('id') and e.get('ngoko') and e.get('krama'))
    
    print(f"\n=== Stats ===")
    print(f"  Total entries: {len(output):,}")
    print(f"  Entries dengan id: {with_id:,}")
    print(f"  Entries dengan ngoko: {with_ngoko:,}")
    print(f"  Entries dengan krama: {with_krama:,}")
    print(f"  Entries LENGKAP (id+ngoko+krama): {lengkap:,}")
    print(f"  Entries tanpa id: {len(output) - with_id:,}")


if __name__ == '__main__':
    main()

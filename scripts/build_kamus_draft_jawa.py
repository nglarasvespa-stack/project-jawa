#!/usr/bin/env python3
"""Rebuild kamus-draft-jawa.json — NETRAL, gak ada label ngoko/krama definitif.

Alasan user:
- Source data label "ngoko"/"krama" sering salah (ada yg labeled ngoko ternyata krama, dll)
- Parser AI juga bikin kesalahan
- Internet data noisy
- Semua harus diperlakukan NETRAL sampai user audit manual

Format baru:
  {
    "id": "merah",                  # Indonesian (kalau ada), tetap dipertahankan
    "jv": "abang, abrit"            # Javanese variants (ALL merged — neutral, no ngoko/krama label)
  }

- Field "jv" gabung dari: ngoko + dasanama + krama + krama_inggil
- Gak ada deklarasi mana ngoko mana krama
- User akan audit + validasi manual
- SEMUA entries dipertahankan (gak ada yang dihapus)
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
    # id: indonesian + id_synonyms
    # jv: ngoko + dasanama + krama + krama_inggil (ALL merged, NEUTRAL)
    cleaned = []
    for e in entries:
        # Indonesian (id) field
        id_orig = e.get('indonesian') or ''
        id_syn = e.get('id_synonyms') or ''
        id_combined = f"{id_orig},{id_syn}" if (id_orig and id_syn) else (id_orig or id_syn)
        id_clean = clean_field(id_combined) or id_orig
        id_items = split_and_dedup(id_clean)
        if not id_items and id_orig:
            id_items = [id_orig]
        
        # Javanese (jv) field — gabung SEMUA: ngoko + dasanama + krama + krama_inggil
        ngoko_orig = e.get('ngoko') or ''
        dasanama = e.get('dasanama') or ''
        krama_orig = e.get('krama') or ''
        krama_inggil = e.get('krama_inggil') or ''
        # All Javanese variants merged
        all_jv_parts = [p for p in [ngoko_orig, dasanama, krama_orig, krama_inggil] if p]
        jv_combined = ', '.join(all_jv_parts)
        jv_clean = clean_field(jv_combined) or jv_combined
        jv_items = split_and_dedup(jv_clean)
        if not jv_items and ngoko_orig:
            jv_items = [ngoko_orig]
        
        cleaned.append({
            'id_items': id_items,
            'jv_items': jv_items,
            'source': e.get('source'),
            'ket': e.get('keterangan'),
        })
    
    print(f"  After cleanup: {len(cleaned):,} entries (PRESERVED)")
    
    # Step 2: Merge by lowercase id (kalau ada id)
    # Entries dengan id → grouped by lowercase id (sinonim Indonesian gabung)
    # Entries tanpa id → group by lowercase jv word (semua Javanese variants)
    groups_with_id = defaultdict(list)
    groups_no_id = defaultdict(list)
    entries_truly_empty = []
    
    for c in cleaned:
        if c['id_items']:
            key = c['id_items'][0].lower()
            groups_with_id[key].append(c)
        elif c['jv_items']:
            key = c['jv_items'][0].lower()
            groups_no_id[key].append(c)
        else:
            entries_truly_empty.append(c)
    
    print(f"  Groups dengan id (Indonesian): {len(groups_with_id):,}")
    print(f"  Groups tanpa id (grouped by jv): {len(groups_no_id):,}")
    print(f"  Entries truly empty (no id, no jv): {len(entries_truly_empty):,}")
    
    # Build output
    output = []
    
    # Groups with id
    for key, group in groups_with_id.items():
        all_ids, all_jv, all_sources = [], [], []
        seen_id, seen_jv, seen_src = set(), set(), set()
        
        for c in group:
            for x in c['id_items']:
                if x.lower() not in seen_id:
                    seen_id.add(x.lower())
                    all_ids.append(x)
            for x in c['jv_items']:
                if x.lower() not in seen_jv:
                    seen_jv.add(x.lower())
                    all_jv.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source'])
                all_sources.append(c['source'])
        
        entry = {
            'id': ', '.join(all_ids) if all_ids else None,
            'jv': ', '.join(all_jv) if all_jv else None,
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    # Groups without id (grouped by jv)
    for key, group in groups_no_id.items():
        all_jv, all_sources = [], []
        seen_jv, seen_src = set(), set()
        
        for c in group:
            for x in c['jv_items']:
                if x.lower() not in seen_jv:
                    seen_jv.add(x.lower())
                    all_jv.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source'])
                all_sources.append(c['source'])
        
        entry = {
            'id': None,
            'jv': ', '.join(all_jv) if all_jv else None,
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    # Sort: with id first (alphabetical), then without id
    output.sort(key=lambda x: (x.get('id') is None, (x.get('id') or x.get('jv') or '').lower()))
    
    print(f"\nFinal entries: {len(output):,}")
    
    # Save
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '4.0',
            'description': 'Kamus Jawa NETRAL — tanpa label definitif ngoko/krama. Field "jv" berisi semua varian Jawa (ngoko+krama+krama_inggil+dasanama) digabung. User akan audit manual untuk tentukan mana ngoko vs krama.',
            'format': 'id (Indonesian jika ada), jv (Javanese variants, NEUTRAL)',
            'total_entries': len(output),
            'source': 'Supabase kamus_draft (ALL 64,063 entries)',
            'note': 'SEMUA entries dipertahankan. Label ngoko/krama dihilangkan karena source data tidak reliable (banyak salah label). User akan audit + validasi manual.',
        },
        'entries': output,
    }
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved to {OUT_PATH}")
    print(f"  File size: {os.path.getsize(OUT_PATH):,} bytes")
    
    # Stats
    with_id = sum(1 for e in output if e.get('id'))
    with_jv = sum(1 for e in output if e.get('jv'))
    both = sum(1 for e in output if e.get('id') and e.get('jv'))
    multi_jv = sum(1 for e in output if e.get('jv') and ',' in e['jv'])
    
    print(f"\n=== Stats ===")
    print(f"  Total entries: {len(output):,}")
    print(f"  Entries dengan id (Indonesian): {with_id:,}")
    print(f"  Entries dengan jv (Javanese): {with_jv:,}")
    print(f"  Entries dengan BOTH id+jv: {both:,}")
    print(f"  Entries dengan multiple jv (sinonim Jawa): {multi_jv:,}")
    
    # Sample
    print(f"\n=== Sample 10 entries ===")
    for e in output[:10]:
        print(f"  id={e.get('id')!r}")
        print(f"    jv={e.get('jv')!r}")


if __name__ == '__main__':
    main()

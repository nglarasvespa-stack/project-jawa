#!/usr/bin/env python3
"""Rebuild kamus-draft-jawa.json v5.0 — logika pair vs netral.

Aturan user:
- Lengkap (id+ngoko+krama SEMUA terisi) → PERTAHANKAN label {id, ngoko, krama}
  + sinonim per field (id_synonyms → id, dasanama → ngoko, krama_inggil → krama)
- Belum lengkap (ada field kosong) → NETRAL {id (jika ada), word: <jv variants>}
  Karena belum terdefinisi mana ngoko mana krama (bisa jadi ngoko, bisa krama,
  bisa id — sampai user audit + validasi)

Format Lengkap:
  {id: "merah, merah muda", ngoko: "abang, mera", krama: "abrit"}

Format Netral (incomplete):
  {id: "merah" (jika ada), word: "abang, abrit" (neutral, no label)}
  ATAU
  {word: "abang"} (kalau gak ada id juga)
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
    
    # Step 1: Build per-entry (clean fields, collect synonyms)
    # Categorize: LENGKAP (id+ngoko+krama all non-empty) vs NETRAL (incomplete)
    lengkap_entries = []  # has all 3
    netral_entries = []   # missing at least one
    
    for e in entries:
        id_orig = e.get('indonesian') or ''
        ngoko_orig = e.get('ngoko') or ''
        krama_orig = e.get('krama') or ''
        id_syn = e.get('id_synonyms') or ''
        dasanama = e.get('dasanama') or ''
        krama_inggil = e.get('krama_inggil') or ''
        
        # Build id_items (indonesian + id_synonyms)
        id_combined = f"{id_orig},{id_syn}" if (id_orig and id_syn) else (id_orig or id_syn)
        id_clean = clean_field(id_combined) or id_orig
        id_items = split_and_dedup(id_clean) if id_clean else ([id_orig] if id_orig else [])
        
        # Build ngoko_items (ngoko + dasanama)
        ngoko_combined = f"{ngoko_orig},{dasanama}" if (ngoko_orig and dasanama) else (ngoko_orig or dasanama)
        ngoko_clean = clean_field(ngoko_combined) or ngoko_orig
        ngoko_items = split_and_dedup(ngoko_clean) if ngoko_clean else ([ngoko_orig] if ngoko_orig else [])
        
        # Build krama_items (krama + krama_inggil)
        krama_combined = f"{krama_orig},{krama_inggil}" if (krama_orig and krama_inggil) else (krama_orig or krama_inggil)
        krama_clean = clean_field(krama_combined) or krama_orig
        krama_items = split_and_dedup(krama_clean) if krama_clean else ([krama_orig] if krama_orig else [])
        
        # Categorize
        if id_items and ngoko_items and krama_items:
            # LENGKAP — keep labels
            lengkap_entries.append({
                'id_items': id_items,
                'ngoko_items': ngoko_items,
                'krama_items': krama_items,
                'source': e.get('source'),
            })
        else:
            # NETRAL — incomplete, jv words jadi "word" (neutral)
            # id tetap dipertahankan kalau ada (Indonesian is clear)
            # All Javanese variants (ngoko + dasanama + krama + krama_inggil) merged jadi "word"
            all_jv_parts = [p for p in [ngoko_orig, dasanama, krama_orig, krama_inggil] if p]
            jv_combined = ', '.join(all_jv_parts)
            jv_clean = clean_field(jv_combined) or jv_combined
            word_items = split_and_dedup(jv_clean) if jv_clean else []
            
            netral_entries.append({
                'id_items': id_items,  # Indonesian (might be empty)
                'word_items': word_items,  # All Javanese variants, NEUTRAL
                'source': e.get('source'),
            })
    
    print(f"\n  LENGKAP (id+ngoko+krama all filled): {len(lengkap_entries):,}")
    print(f"  NETRAL (incomplete): {len(netral_entries):,}")
    
    # Step 2: Merge by lowercase id (sinonim Indonesian digabung)
    # Lengkap entries: group by lowercase first id item
    lengkap_groups = defaultdict(list)
    for c in lengkap_entries:
        key = c['id_items'][0].lower()
        lengkap_groups[key].append(c)
    
    # Netral entries: group by lowercase first id item (kalau ada), else by first word
    netral_groups_with_id = defaultdict(list)
    netral_groups_no_id = defaultdict(list)
    for c in netral_entries:
        if c['id_items']:
            key = c['id_items'][0].lower()
            netral_groups_with_id[key].append(c)
        elif c['word_items']:
            key = c['word_items'][0].lower()
            netral_groups_no_id[key].append(c)
    
    print(f"\n  Lengkap groups (by id): {len(lengkap_groups):,}")
    print(f"  Netral groups dengan id: {len(netral_groups_with_id):,}")
    print(f"  Netral groups tanpa id (by word): {len(netral_groups_no_id):,}")
    
    # Build output
    output = []
    
    # Lengkap entries — output as {id, ngoko, krama}
    for key, group in lengkap_groups.items():
        all_ids, all_ngoko, all_krama, all_sources = [], [], [], []
        seen_id, seen_ngoko, seen_krama, seen_src = set(), set(), set(), set()
        
        for c in group:
            for x in c['id_items']:
                if x.lower() not in seen_id:
                    seen_id.add(x.lower()); all_ids.append(x)
            for x in c['ngoko_items']:
                if x.lower() not in seen_ngoko:
                    seen_ngoko.add(x.lower()); all_ngoko.append(x)
            for x in c['krama_items']:
                if x.lower() not in seen_krama:
                    seen_krama.add(x.lower()); all_krama.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source']); all_sources.append(c['source'])
        
        entry = {
            'id': ', '.join(all_ids),
            'ngoko': ', '.join(all_ngoko),
            'krama': ', '.join(all_krama),
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    # Netral entries with id — output as {id, word (neutral)}
    for key, group in netral_groups_with_id.items():
        all_ids, all_words, all_sources = [], [], []
        seen_id, seen_word, seen_src = set(), set(), set()
        
        for c in group:
            for x in c['id_items']:
                if x.lower() not in seen_id:
                    seen_id.add(x.lower()); all_ids.append(x)
            for x in c['word_items']:
                if x.lower() not in seen_word:
                    seen_word.add(x.lower()); all_words.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source']); all_sources.append(c['source'])
        
        entry = {
            'id': ', '.join(all_ids) if all_ids else None,
            'word': ', '.join(all_words) if all_words else None,  # NEUTRAL
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    # Netral entries without id — output as {word (neutral)}
    for key, group in netral_groups_no_id.items():
        all_words, all_sources = [], []
        seen_word, seen_src = set(), set()
        
        for c in group:
            for x in c['word_items']:
                if x.lower() not in seen_word:
                    seen_word.add(x.lower()); all_words.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source']); all_sources.append(c['source'])
        
        entry = {
            'word': ', '.join(all_words) if all_words else None,  # NEUTRAL
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    # Sort: lengkap first (alphabetical by id), then netral with id, then netral without id
    def sort_key(e):
        if 'ngoko' in e and 'krama' in e:
            return (0, (e.get('id') or '').lower())
        elif e.get('id'):
            return (1, e['id'].lower())
        else:
            return (2, (e.get('word') or '').lower())
    output.sort(key=sort_key)
    
    print(f"\nFinal entries: {len(output):,}")
    
    # Save
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '5.0',
            'description': 'Kamus Jawa — Lengkap entries PERTAHANKAN label {id, ngoko, krama}. Incomplete entries JADI NETRAL {id?, word} karena belum terdefinisi mana ngoko/krama. User akan audit + validasi manual.',
            'format': 'Lengkap: {id, ngoko, krama} (sinonim per field). Netral: {id (jika ada), word (all jv variants, NEUTRAL)}.',
            'total_entries': len(output),
            'source': 'Supabase kamus_draft (ALL entries preserved)',
            'note': 'SEMUA entries dipertahankan. Hanya Lengkap yang keep ngoko/krama labels.',
        },
        'entries': output,
    }
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved to {OUT_PATH}")
    print(f"  File size: {os.path.getsize(OUT_PATH):,} bytes")
    
    # Stats
    lengkap_count = sum(1 for e in output if 'ngoko' in e and 'krama' in e)
    netral_with_id = sum(1 for e in output if e.get('id') and 'word' in e)
    netral_no_id = sum(1 for e in output if not e.get('id') and 'word' in e)
    
    print(f"\n=== Stats ===")
    print(f"  Total entries: {len(output):,}")
    print(f"  Lengkap ({id}+ngoko+krama semua): {lengkap_count:,}")
    print(f"  Netral dengan id (incomplete): {netral_with_id:,}")
    print(f"  Netral tanpa id (cuma word): {netral_no_id:,}")
    
    # Samples
    print(f"\n=== Sample Lengkap entries (5) ===")
    n = 0
    for e in output:
        if 'ngoko' in e and 'krama' in e and n < 5:
            print(f"  id={e['id']!r}")
            print(f"    ngoko={e['ngoko']!r}")
            print(f"    krama={e['krama']!r}")
            n += 1
    
    print(f"\n=== Sample Netral with id (5) ===")
    n = 0
    for e in output:
        if e.get('id') and 'word' in e and n < 5:
            print(f"  id={e['id']!r}")
            print(f"    word={e['word']!r}")
            n += 1
    
    print(f"\n=== Sample Netral no id (5) ===")
    n = 0
    for e in output:
        if not e.get('id') and 'word' in e and n < 5:
            print(f"  word={e['word']!r}")
            n += 1


if __name__ == '__main__':
    main()

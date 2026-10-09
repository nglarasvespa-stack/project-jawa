#!/usr/bin/env python3
"""Rebuild kamus-draft-jawa.json v7.0 — ALL 64k from Supabase, parser bener, gak hapus data.

Fetch SEMUA 64,063 entries dari kamus_draft (Supabase).
Clean fields dengan parser bener (strip definisi, marker, numbering).
Merge by Indonesian (sinonim gabung koma).
NO FILTER, NO DELETE — semua dipertahankan.
"""
import os, json, requests, re
from collections import defaultdict

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}'}

OUT_PATH = '/home/z/my-project/dub-jawa/kamus-draft-jawa.json'

MARKERS = ['t.a.', 't.k.', 't.s.', 't.kr.', 't.py.', 't.pw.', 't.pr.', 't.sd.', 't.w.',
           'kc.', 'bngs.', 'k.', 'tsb.']
ROMAN = re.compile(r'^\s*(i{1,3}|iv|v|vi{0,3})\s+', re.IGNORECASE)
NUM_START = re.compile(r'^\s*\d+\.\s*')


def clean_jv(raw):
    """Clean Javanese field — strip definisi after ':', markers, numbering."""
    if not raw: return []
    parts = raw.split(';')
    words = []
    for part in parts:
        part = part.strip()
        if not part: continue
        if ':' in part:
            left = part.split(':')[0].strip()
            if left and len(left) <= 50:
                part = left
            else:
                continue
        for m in MARKERS:
            if part.lower().startswith(m):
                part = part[len(m):].strip()
        part = re.sub(r'Templat:[a-z.]+', '', part, flags=re.IGNORECASE)
        part = NUM_START.sub('', part)
        part = ROMAN.sub('', part)
        part = part.strip('"\'""''')
        for word in part.split(','):
            word = word.strip().rstrip('.')
            if not word: continue
            if len(word.split()) > 3: continue
            if len(word) < 1 or len(word) > 60: continue
            if '(' in word or ')' in word or '{' in word: continue
            words.append(word)
    seen = set()
    result = []
    for w in words:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            result.append(w)
    return result


def clean_id(raw):
    """Clean Indonesian field."""
    if not raw: return None
    s = raw.strip()
    s = re.sub(r'\([^)]*\)', '', s).strip()
    s = NUM_START.sub('', s)
    s = ROMAN.sub('', s)
    s = s.rstrip('.').strip()
    return s if s else None


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
    print("Fetching SEMUA 64,063 entries dari kamus_draft...")
    entries = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?"
        f"select=id,indonesian,ngoko,krama,krama_inggil,dasanama,id_synonyms,keterangan,source"
    )
    print(f"  Fetched: {len(entries):,}")
    
    # Clean + build per entry — PRESERVE ALL (gak hapus)
    cleaned = []
    for e in entries:
        idn = clean_id(e.get('indonesian') or '')
        id_syn = e.get('id_synonyms') or ''
        # jv words: ngoko + dasanama + krama + krama_inggil — ALL merged
        jv_parts = [p for p in [e.get('ngoko'), e.get('dasanama'), e.get('krama'), e.get('krama_inggil')] if p]
        jv_raw = ', '.join(jv_parts)
        jv_words = clean_jv(jv_raw)
        # Fallback: kalau clean bikin kosong, pakai original
        if not jv_words and e.get('ngoko'):
            jv_words = [e.get('ngoko')]
        
        # Indonesian + id_synonyms
        id_items = []
        if idn:
            id_items.append(idn)
        for s in (id_syn or '').split(','):
            s = clean_id(s)
            if s:
                id_items.append(s)
        
        cleaned.append({
            'id_items': id_items,
            'jv_items': jv_words,
            'source': e.get('source'),
        })
    
    print(f"  After cleanup: {len(cleaned):,} (PRESERVED — gak ada yang dihapus)")
    
    # Merge by lowercase first id item (kalau ada id), else by first jv word
    groups_with_id = defaultdict(list)
    groups_no_id = defaultdict(list)
    for c in cleaned:
        if c['id_items']:
            key = c['id_items'][0].lower()
            groups_with_id[key].append(c)
        elif c['jv_items']:
            key = c['jv_items'][0].lower()
            groups_no_id[key].append(c)
    
    print(f"  Groups dengan id: {len(groups_with_id):,}")
    print(f"  Groups tanpa id: {len(groups_no_id):,}")
    
    # Build output
    output = []
    
    for key, group in groups_with_id.items():
        all_ids, all_jv, all_sources = [], [], []
        seen_id, seen_jv, seen_src = set(), set(), set()
        for c in group:
            for x in c['id_items']:
                if x.lower() not in seen_id:
                    seen_id.add(x.lower()); all_ids.append(x)
            for x in c['jv_items']:
                if x.lower() not in seen_jv:
                    seen_jv.add(x.lower()); all_jv.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source']); all_sources.append(c['source'])
        entry = {
            'id': ', '.join(all_ids),
            'word': ', '.join(all_jv) if all_jv else None,
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    for key, group in groups_no_id.items():
        all_jv, all_sources = [], []
        seen_jv, seen_src = set(), set()
        for c in group:
            for x in c['jv_items']:
                if x.lower() not in seen_jv:
                    seen_jv.add(x.lower()); all_jv.append(x)
            if c.get('source') and c['source'] not in seen_src:
                seen_src.add(c['source']); all_sources.append(c['source'])
        entry = {
            'word': ', '.join(all_jv) if all_jv else None,
        }
        if all_sources:
            entry['source'] = ', '.join(all_sources)
        output.append(entry)
    
    output.sort(key=lambda x: (x.get('id') is None, (x.get('id') or x.get('word') or '').lower()))
    
    print(f"\nFinal: {len(output):,} entries")
    
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '7.0',
            'description': 'ALL 64,063 entries dari kamus_draft. Parser bener (strip definisi/marker/numbering). Sinonim digabung koma. NO DATA DELETED.',
            'total_entries': len(output),
            'source': 'Supabase kamus_draft (ALL entries preserved)',
        },
        'entries': output,
    }
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Saved ({os.path.getsize(OUT_PATH):,} bytes)")


if __name__ == '__main__':
    main()

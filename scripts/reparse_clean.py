#!/usr/bin/env python3
"""Re-parse sastra_dict.csv dengan parser yang BENER.

Perbaikan:
1. Pisahkan kata dari definisi (split pada ":")
2. Hapus marker (t.a., t.k., t.s., kc., bngs., i, ii, kc.)
3. Hapus nomor urut (1, 2, 3 di awal)
4. Split sinonim pada ";" dan ","
5. Keep polysemy sebagai entries terpisah (jangan merge beda makna)
6. Output clean: {indonesian, jv_words (comma-separated)}

Pakai juga kamus_api_extracted.json (sudah bersih, 3,226 entries).
"""
import json, csv, re, os
from collections import defaultdict

DATA_DIR = '/tmp/my-project/dub-jawa/data'
OUT_PATH = '/home/z/my-project/dub-jawa/kamus-draft-jawa.json'

# Markers to strip
MARKERS = [
    't.a.', 't.k.', 't.s.', 't.kr.', 't.py.', 't.pw.', 't.pr.', 't.sd.', 't.w.',
    'kc.', 'bngs.', 'k.', 'tsb.',
    'Templat:t.k', 'Templat:t.a', 'Templat:t.s', 'Templat:t.kr',
    'Templat:k.a', 'Templat:k.a.',
]

# Roman numeral patterns at start (i, ii, iii, iv, etc.)
ROMAN = re.compile(r'^\s*(i{1,3}|iv|v|vi{0,3})\s+', re.IGNORECASE)

# Number at start
NUM_START = re.compile(r'^\s*\d+\.\s*')


def clean_javanese(raw):
    """Parse sastra.org Javanese field → list of clean Javanese words.
    
    Strategy:
    1. Split on ";" (sinonim separator)
    2. For each part: split on ":" → take LEFT side (kata), drop RIGHT side (definisi)
    3. Strip markers, numbering, whitespace
    4. Split on "," for sub-sinonim
    5. Filter out long phrases (likely definitions, not words)
    """
    if not raw:
        return []
    
    # Step 1: Split on ";"
    parts = raw.split(';')
    
    words = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Step 2: Split on ":" → take LEFT (kata), drop RIGHT (definisi)
        if ':' in part:
            left = part.split(':')[0].strip()
            # Only keep left if it's short enough to be a word (not a definition)
            if left and len(left) <= 50:
                part = left
            else:
                # Left is too long — probably a definition, skip
                continue
        
        # Step 3: Strip markers
        for marker in MARKERS:
            if part.lower().startswith(marker):
                part = part[len(marker):].strip()
        # Also strip "Templat:..." patterns
        part = re.sub(r'Templat:[a-z.]+', '', part, flags=re.IGNORECASE)
        
        # Step 4: Strip numbering at start
        part = NUM_START.sub('', part)
        part = ROMAN.sub('', part)
        
        # Step 5: Strip quotes
        part = part.strip('"\'""''')
        
        # Step 6: Split on "," for sub-sinonim
        for word in part.split(','):
            word = word.strip().rstrip('.')
            if not word:
                continue
            # Filter: word should be 1-30 chars, no spaces (single word) or max 3 words
            word_count = len(word.split())
            if word_count > 3:
                continue  # too long — likely a definition
            if len(word) < 1 or len(word) > 60:
                continue
            # Skip if contains "()" or "{}" (template remnants)
            if '(' in word or ')' in word or '{' in word:
                continue
            words.append(word)
    
    # Dedup
    seen = set()
    result = []
    for w in words:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            result.append(w)
    return result


def clean_indonesian(raw):
    """Clean Indonesian field — strip parentheses, keep main word."""
    if not raw:
        return None
    s = raw.strip()
    # Remove text in parentheses
    s = re.sub(r'\([^)]*\)', '', s).strip()
    # Remove numbering
    s = NUM_START.sub('', s)
    s = ROMAN.sub('', s)
    # Strip trailing period
    s = s.rstrip('.').strip()
    return s if s else None


def main():
    all_entries = []  # list of {id, jv_words, source}
    
    # === SOURCE 1: sastra_dict.csv (re-parse properly) ===
    print("Source 1: sastra_dict.csv — RE-PARSE dengan parser bener...")
    csv_path = os.path.join(DATA_DIR, 'sastra_dict.csv')
    if os.path.exists(csv_path):
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            sastra_count = 0
            for row in reader:
                idn = clean_indonesian(row.get('Indonesia', ''))
                jv_raw = row.get('Javanese', '')
                jv_words = clean_javanese(jv_raw)
                if idn and jv_words:
                    all_entries.append({
                        'id': idn,
                        'jv': ', '.join(jv_words),
                        'source': 'sastra.org',
                    })
                    sastra_count += 1
        print(f"  {sastra_count:,} entries (was 11,095 raw rows — cleaned)")
    
    # === SOURCE 2: kamus_api_extracted.json (sudah bersih) ===
    print("\nSource 2: kamus_api_extracted.json (sudah bersih)...")
    api_path = os.path.join(DATA_DIR, 'kamus_api_extracted.json')
    if os.path.exists(api_path):
        with open(api_path, encoding='utf-8') as f:
            d = json.load(f)
        api_count = 0
        for idn, ngoko in d.get('id_to_ngoko', {}).items():
            idn_clean = clean_indonesian(idn)
            if idn_clean and ngoko:
                all_entries.append({
                    'id': idn_clean,
                    'jv': ngoko,
                    'source': 'kamus-api',
                })
                api_count += 1
        print(f"  {api_count:,} entries")
    
    # === SOURCE 3: id_wiktionary_jv_id.json (clean id field) ===
    print("\nSource 3: id_wiktionary_jv_id.json...")
    wt_path = os.path.join(DATA_DIR, 'id_wiktionary_jv_id.json')
    if os.path.exists(wt_path):
        with open(wt_path, encoding='utf-8') as f:
            d = json.load(f)
        wt_count = 0
        for e in d.get('entries', []):
            jv = (e.get('jv') or '').strip()
            idn = clean_indonesian(e.get('id', ''))
            # Skip if id is too long (likely definition, not word)
            if idn and len(idn) > 80:
                continue
            # Skip if id contains ":" (definition)
            if idn and ':' in idn:
                # Try to take part before ":"
                idn = idn.split(':')[0].strip()
                if not idn or len(idn) > 80:
                    continue
            if jv and idn:
                all_entries.append({
                    'id': idn,
                    'jv': jv,
                    'source': 'id-wiktionary',
                })
                wt_count += 1
        print(f"  {wt_count:,} entries (was 1,943 — cleaned)")
    
    # === SOURCE 4: kamus_draft dari Supabase (entries dengan ngoko only, no id) ===
    # Skip — too noisy, will handle separately
    
    print(f"\nTotal entries from sources: {len(all_entries):,}")
    
    # === MERGE: group by lowercase Indonesian, combine jv sinonim ===
    print("\nMerging by Indonesian (combine sinonim dengan koma)...")
    groups = defaultdict(lambda: {'jv_words': [], 'sources': set()})
    for e in all_entries:
        key = e['id'].lower()
        groups[key]['id'] = e['id']  # keep original case
        for w in e['jv'].split(','):
            w = w.strip()
            if w:
                groups[key]['jv_words'].append(w)
        groups[key]['sources'].add(e['source'])
    
    # Dedup jv words per group
    output = []
    for key, g in groups.items():
        seen = set()
        unique_jv = []
        for w in g['jv_words']:
            wl = w.lower()
            if wl not in seen:
                seen.add(wl)
                unique_jv.append(w)
        
        entry = {
            'id': g['id'],
            'word': ', '.join(unique_jv),  # NEUTRAL (no ngoko/krama label)
        }
        if g['sources']:
            entry['source'] = ', '.join(sorted(g['sources']))
        output.append(entry)
    
    # Sort by id
    output.sort(key=lambda x: x['id'].lower())
    
    print(f"Merged entries: {len(output):,}")
    
    # Save
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '6.0',
            'description': 'Re-parse dari source data dengan parser yang bener. Pisah kata dari definisi, hapus marker, hapus numbering, keep polysemy terpisah. Neutral format (no ngoko/krama label).',
            'sources': ['sastra.org (re-parsed)', 'kamus-api (clean)', 'id-wiktionary (cleaned)'],
            'total_entries': len(output),
        },
        'entries': output,
    }
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved to {OUT_PATH}")
    print(f"  File size: {os.path.getsize(OUT_PATH):,} bytes")
    
    # Sample
    print(f"\n=== Sample 15 entries ===")
    for e in output[:15]:
        print(f"  id={e['id']!r:30s}  word={e['word']!r}")


if __name__ == '__main__':
    main()

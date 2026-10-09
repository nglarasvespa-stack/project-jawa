#!/usr/bin/env python3
"""Cleanup kamus-draft-jawa.json — fix entries aneh + re-merge.

Issues found in audit:
1. 1 entry "dahulu, dulu" muncul 2x — perlu di-merge
2. 28 entries dengan ":" atau "(" — sisa parsing jelek dari sastra.org
3. 11 entries dengan "{{", "anane:", dll — sisa template wiki

Cleanup strategy:
1. For each field (id, ngoko, krama), clean up:
   - Hapus text setelah ":" (definitions)
   - Hapus text dalam "(...)" (annotations)
   - Hapus sisa template "{{...}}"
   - Strip whitespace, normalize commas
2. After cleanup, re-merge by id (case-insensitive)
3. Combine synonyms dengan comma
"""
import json, re
from collections import defaultdict

IN_PATH = '/home/z/my-project/dub-jawa/kamus-draft-jawa.json'
OUT_PATH = '/home/z/my-project/dub-jawa/kamus-draft-jawa.json'


def clean_field(s):
    """Clean satu field dari karakter aneh, normalize synonyms."""
    if not s:
        return None
    # Remove text after ":" (definitions)
    if ':' in s:
        s = s.split(':')[0]
    # Remove text in parentheses
    s = re.sub(r'\([^)]*\)', '', s)
    # Remove sisa template {{...}} (with or without closing)
    s = re.sub(r'\{\{[^}]*\}\}', '', s)
    s = re.sub(r'\{\{.*', '', s)  # remove {{ and everything after (unclosed)
    # Remove sisa single brace
    s = re.sub(r'\{[^}]*\}', '', s)
    s = re.sub(r'\{.*', '', s)  # remove lone { and after
    # Remove marker patterns like "(t.k.)", "(k)", "(kawi)"
    s = re.sub(r'\([a-z.]+\)', '', s)
    # Remove leftover special chars
    s = re.sub(r'[|/]', ',', s)
    # Normalize multiple commas/spaces
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r',\s+,', ',', s)
    s = re.sub(r'^\s*,\s*', '', s)
    s = re.sub(r'\s*,\s*$', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # Remove trailing comma
    s = s.rstrip(',').strip()
    if not s:
        return None
    return s


def split_and_dedup(s):
    """Split comma-separated string → list of unique (case-insensitive) items."""
    if not s:
        return []
    items = []
    seen = set()
    for x in s.split(','):
        x = x.strip()
        if x and x.lower() not in seen:
            seen.add(x.lower())
            items.append(x)
    return items


def main():
    with open(IN_PATH, encoding='utf-8') as f:
        d = json.load(f)
    
    entries = d['entries']
    print(f"Loaded: {len(entries):,} entries (before cleanup)")
    
    # Clean each field
    cleaned = []
    for e in entries:
        id_items = split_and_dedup(clean_field(e.get('id')))
        ngoko_items = split_and_dedup(clean_field(e.get('ngoko')))
        krama_items = split_and_dedup(clean_field(e.get('krama')))
        # Also clean keterangan
        ket = e.get('keterangan')
        if ket:
            # Clean keterangan but keep | separator
            ket_parts = []
            for p in ket.split(' | '):
                cp = clean_field(p)
                if cp:
                    ket_parts.append(cp)
            ket = ' | '.join(ket_parts) if ket_parts else None
        
        if not id_items or not ngoko_items or not krama_items:
            continue  # skip entries with empty fields after cleanup
        
        cleaned.append({
            'id_items': id_items,
            'ngoko_items': ngoko_items,
            'krama_items': krama_items,
            'ket': ket,
        })
    
    print(f"After cleaning empty: {len(cleaned):,} entries")
    
    # Re-merge by id (case-insensitive)
    # Build mapping: lowercase id → list of all entries containing that id
    groups = defaultdict(list)
    for c in cleaned:
        # Use first id as group key (or pick most common id)
        key = c['id_items'][0].lower()
        groups[key].append(c)
    
    print(f"Unique id groups after merge: {len(groups):,}")
    
    # Build final entries
    output = []
    for key, group in groups.items():
        # Union all id_items
        all_ids = []
        seen = set()
        for c in group:
            for x in c['id_items']:
                if x.lower() not in seen:
                    seen.add(x.lower())
                    all_ids.append(x)
        
        # Union all ngoko_items
        all_ngoko = []
        seen = set()
        for c in group:
            for x in c['ngoko_items']:
                if x.lower() not in seen:
                    seen.add(x.lower())
                    all_ngoko.append(x)
        
        # Union all krama_items
        all_krama = []
        seen = set()
        for c in group:
            for x in c['krama_items']:
                if x.lower() not in seen:
                    seen.add(x.lower())
                    all_krama.append(x)
        
        # Union keterangan
        all_ket = []
        seen = set()
        for c in group:
            if c.get('ket'):
                for p in c['ket'].split(' | '):
                    p = p.strip()
                    if p and p.lower() not in seen:
                        seen.add(p.lower())
                        all_ket.append(p)
        
        entry = {
            'id': ', '.join(all_ids),
            'ngoko': ', '.join(all_ngoko),
            'krama': ', '.join(all_krama),
        }
        if all_ket:
            entry['keterangan'] = ' | '.join(all_ket)
        output.append(entry)
    
    # Sort by id alphabetically
    output.sort(key=lambda x: x['id'].lower())
    
    print(f"Final entries: {len(output):,}")
    
    # Save
    result = {
        'meta': {
            'name': 'kamus-draft-jawa',
            'version': '2.1',
            'description': 'Kamus Jawa clean dengan sinonim per field. Entries di-MERGE by Indonesian (case-insensitive). krama_inggil di-merge ke krama. v2.1: cleanup karakter aneh (:, (), {{, etc) + re-merge.',
            'format': 'id, ngoko, krama (comma-separated sinonim per field)',
            'total_entries': len(output),
            'source': 'Supabase kamus_draft (Lengkap entries, cleaned + merged)',
        },
        'entries': output,
    }
    
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved to {OUT_PATH}")
    
    # Verify: no more weird entries
    weird = 0
    for e in output:
        for field in ('id', 'ngoko', 'krama'):
            val = e.get(field, '')
            if ':' in val or '(' in val or '{{' in val or '\n' in val:
                weird += 1
                print(f"  STILL WEIRD: {field}={val!r}")
                break
    print(f"\nVerify: entries with weird chars after cleanup: {weird}")
    
    # Verify: no more duplicate ids
    from collections import Counter
    id_count = Counter(e['id'].lower() for e in output)
    dupes = [(k, c) for k, c in id_count.items() if c > 1]
    print(f"Verify: duplicate id entries: {len(dupes)}")
    
    # Sample
    print(f"\n=== Sample 5 entries ===")
    for e in output[:5]:
        print(f"  id={e['id']!r}")
        print(f"    ngoko={e['ngoko']!r}")
        print(f"    krama={e['krama']!r}")


if __name__ == '__main__':
    main()

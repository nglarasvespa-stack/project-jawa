#!/usr/bin/env python3
"""Final patch v3.1.3: fix 16 multi-colon + 13 unbalanced parens."""
import csv, json, re, unicodedata
from pathlib import Path
from collections import Counter

KAMUS_PATH = '/home/z/my-project/dub-jawa/kamus_jawa.json'
SASTRA_CSV = '/tmp/sastra_dict.csv'
NEW_VERSION = '3.1.3'


def strip_accents(s):
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _split_outside_parens(s, delimiter=','):
    parts, current, paren_depth = [], [], 0
    for c in s:
        if c == '(':
            paren_depth += 1
            current.append(c)
        elif c == ')':
            paren_depth = max(0, paren_depth - 1)
            current.append(c)
        elif c == delimiter and paren_depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(c)
    if current:
        parts.append(''.join(current))
    return parts


def clean_v313(raw_jawa: str) -> str:
    """v3.1.3 cleaner — same as v3.1.2 but with:
    - LOOP colon-strip (handles multi-colon `X: Y: Z`)
    - Strip unbalanced parens at end (after balanced strip)
    """
    if not raw_jawa:
        return ''
    s = raw_jawa.strip()
    
    # 1. Split by `;` outside parens
    parts_semi, current, paren_depth = [], [], 0
    for c in s:
        if c == '(':
            paren_depth += 1
            current.append(c)
        elif c == ')':
            paren_depth = max(0, paren_depth - 1)
            current.append(c)
        elif c == ';' and paren_depth == 0:
            parts_semi.append(''.join(current))
            current = []
        else:
            current.append(c)
    if current:
        parts_semi.append(''.join(current))
    s = parts_semi[0].strip() if parts_semi else s
    
    # 2. Split by `kc.`
    kc_parts = re.split(r'\s+kc\.\s+', s, maxsplit=1)
    if len(kc_parts) > 1:
        s = kc_parts[0].strip()
    
    # 3. Split by `. ii ` (sense separator)
    sense_splits = re.split(r'\.\s+(?:i{1,3}|iv|vi{0,3})\s+', s, maxsplit=2, flags=re.IGNORECASE)
    if len(sense_splits) > 1:
        s = sense_splits[0].strip()
    
    # *** FIX 1: LOOP colon-strip (handles `X: Y: Z` → `Y: Z` → `Z`) ***
    for _ in range(5):  # max 5 iterations
        if ':' not in s:
            break
        before, _, after = s.partition(':')
        after_stripped = after.strip()
        # Take AFTER if non-empty and starts with letter
        if after_stripped and re.match(r"^[a-zA-ZÀ-ÿêà']", after_stripped[0]):
            s = after_stripped
        else:
            break
    
    # 5. Split by `ut.` outside parens
    ut_parts, current, paren_depth = [], [], 0
    i = 0
    while i < len(s):
        if (paren_depth == 0 and i + 3 < len(s)
            and s[i:i+4].lower() == ' ut.'
            and (i + 4 == len(s) or not s[i+4].isalpha())):
            ut_parts.append(''.join(current))
            current = []
            i += 4
            continue
        c = s[i]
        if c == '(':
            paren_depth += 1
        elif c == ')':
            paren_depth = max(0, paren_depth - 1)
        current.append(c)
        i += 1
    if current:
        ut_parts.append(''.join(current))
    if len(ut_parts) > 1:
        s = ut_parts[0].strip()
    
    # 6. Split by `,` outside parens
    parts = _split_outside_parens(s, ',')
    if len(parts) > 1:
        first_part = parts[0].strip()
        if len(first_part) >= 3:
            s = first_part
    
    # 7-10. Strip leading numbers, abbrevs, Roman
    s = re.sub(r'^\d+\s+', '', s)
    abbrevs = r'kc\.|bngs\.|ent\.|up\.|dkk\.|ke\.|nj\.|ar\.|tmr\.|wl\.|i\.|s\.|j\.|bl\.|jl\.|jr\.|b\.|k\.|t\.|w\.|ut\.|kw\.|blg\.|kk\.|bls\.'
    for _ in range(4):
        s = re.sub(rf'^(?:{abbrevs})\s+', '', s)
    s = re.sub(r'^(?:i{1,3}|iv|vi{0,3})\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s(?:i{1,3}|iv|vi{0,3})\s', ' ', s, flags=re.IGNORECASE)
    
    # 11. Strip BALANCED parentheticals
    s = re.sub(r'\([^)]*\)', '', s).strip()
    
    # *** FIX 2: Strip UNBALANCED parentheticals ***
    # If there's still a `(` without `)`, strip from `(` onwards
    if '(' in s and ')' not in s:
        s = s.split('(')[0].strip()
    # If there's a `)` without `(`, strip from `)` onwards
    if ')' in s and '(' not in s:
        s = s.split(')')[0].strip()
    
    # 12-15. Final cleanup
    s = s.rstrip('.:').strip()
    s = s.lstrip('-,').strip()
    s = re.sub(r'\s{2,}', ' ', s).strip()
    s = re.sub(r'\s+(?:lsp|dsb|mis|dkk)\.?\s*$', '', s, flags=re.IGNORECASE).strip()
    
    return s


def is_valid_v313(jawa: str) -> bool:
    if not jawa or len(jawa) < 2:
        return False
    if len(jawa) > 50:
        return False
    bad_markers_pattern = r'\b(?:' + r'|'.join([
        'lsp', 'dsb', 'mis', 'up', 'kc', 'bngs', 'ent', 'nj', 'ke',
        'tmr', 'ar', 'wl', 'bl', 'jl', 'jr',
        'kw', 'blg', 'kk', 'bls', 'ut',
    ]) + r')\b'
    if re.search(bad_markers_pattern, jawa, re.IGNORECASE):
        return False
    if re.search(r'\d', jawa):
        return False
    if not re.search(r'[a-zA-ZÀ-ÿêà]', jawa):
        return False
    # Reject unbalanced parens (shouldn't happen after v3.1.3 cleaner)
    if '(' in jawa and ')' not in jawa:
        return False
    if ')' in jawa and '(' not in jawa:
        return False
    if re.search(r'\s(?:i{1,3}|iv|vi{0,3})\s', jawa, re.IGNORECASE):
        return False
    if not re.match(r"^[a-zA-ZÀ-ÿêà']", jawa[0]):
        return False
    return True


def main():
    with open(KAMUS_PATH, encoding='utf-8') as f:
        k = json.load(f)
    id2ng = k['typo_corrections']
    print(f"Before: {len(id2ng):,} entries, version {k['meta']['version']}")
    
    sastra_raw = {}
    with open(SASTRA_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_word = re.sub(r'\s*\([^)]*\)', '', row.get('Indonesia', '').strip()).strip()
            id_norm = strip_accents(id_word.lower())
            if id_norm not in sastra_raw:
                sastra_raw[id_norm] = []
            sastra_raw[id_norm].append(row.get('Javanese', '').strip())
    
    stats = Counter()
    new_id2ng = {}
    fixed_samples = []
    
    for src, tgt in id2ng.items():
        src_norm = strip_accents(src.lower())
        if src_norm not in sastra_raw:
            new_id2ng[src] = tgt
            stats['kept_curated'] += 1
            continue
        
        raw_values = sastra_raw[src_norm]
        chosen = None
        for raw in raw_values:
            cleaned = clean_v313(raw)
            if is_valid_v313(cleaned):
                chosen = cleaned
                break
        
        if chosen is None:
            new_id2ng[src] = tgt
            stats['no_valid_cleaned'] += 1
        elif chosen == tgt:
            new_id2ng[src] = tgt
            stats['already_correct'] += 1
        else:
            new_id2ng[src] = chosen
            stats['fixed'] += 1
            if len(fixed_samples) < 30:
                fixed_samples.append((src, tgt, chosen))
    
    print(f"\n=== Patch v3.1.3 stats ===")
    print(f"  Kept curated: {stats['kept_curated']:,}")
    print(f"  Already correct: {stats['already_correct']:,}")
    print(f"  FIXED: {stats['fixed']:,}")
    print(f"  No valid cleaned: {stats['no_valid_cleaned']:,}")
    
    print(f"\n=== Sample FIXED (previously multi-colon or unbalanced) ===")
    for s, old, new in fixed_samples[:25]:
        print(f"  {s!r:20s}")
        print(f"    OLD: {old!r}")
        print(f"    NEW: {new!r}")
    
    # Save
    k['typo_corrections'] = new_id2ng
    k['meta']['version'] = NEW_VERSION
    k['meta']['last_updated'] = '2026-10-06'
    k['meta']['typo_corrections_count'] = len(new_id2ng)
    k['meta']['note'] = (
        f"v{NEW_VERSION}: Fix multi-colon entries (loop colon-strip) + strip unbalanced parens. "
        f"{stats['fixed']:,} entries fixed. "
        "v3.1.2: fix 503 colon entries. v3.1.0-1: re-import with cleaner fixes. "
        "v3.0.x: full sastra import. AUDIT: 0 hallucination, minimal sampah."
    )
    
    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)
    
    print(f"\nAfter: {len(new_id2ng):,} entries")
    print(f"Saved: {Path(KAMUS_PATH).stat().st_size:,} bytes")
    
    # Final audit
    print(f"\n=== FINAL AUDIT v3.1.3 ===")
    unbal = sum(1 for v in new_id2ng.values() 
                if ('(' in v and ')' not in v) or (')' in v and '(' not in v))
    roman = sum(1 for v in new_id2ng.values()
                if re.search(r'\s(?:i{1,3}|iv|vi{0,3})\s', v, re.IGNORECASE))
    colon = sum(1 for v in new_id2ng.values() if ':' in v)
    multi = sum(1 for v in new_id2ng.values() if '  ' in v)
    ut = sum(1 for v in new_id2ng.values() if re.search(r'\but\.\b', v, re.IGNORECASE))
    print(f"  Unbalanced parens: {unbal}")
    print(f"  Mid-string Roman: {roman}")
    print(f"  Values with ':': {colon}")
    print(f"  Multi-space: {multi}")
    print(f"  'ut.' remaining: {ut}")
    
    # Verify specific multi-colon + unbalanced paren entries
    print(f"\n=== Verify previously-buggy (multi-colon) ===")
    for w in ['bisa', 'kuda', 'awin', 'cericap', 'kedai', 'keropeng', 'kumpul',
              'ladang', 'laki', 'lakur', 'layang', 'mamang', 'rabak', 'ruam',
              'sadap', 'suah']:
        our = new_id2ng.get(w, '(not in kamus)')
        print(f"  {w!r:15s} -> {our!r}")
    
    print(f"\n=== Verify previously-buggy (unbalanced parens) ===")
    for w in ['bayur', 'canar', 'cendera-durja', 'dawa', 'jinah', 'kelandara',
              'kida-kida', 'nyenyai', 'rongak', 'tamban', 'tonggok', 'ubi', 'zohar']:
        our = new_id2ng.get(w, '(not in kamus)')
        print(f"  {w!r:20s} -> {our!r}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Patch v3.1.2: final fix untuk sisa bug.

Strategy:
  1. Split value on `. ii ` FIRST (sense separator) — take first sense
  2. For first sense, if has `:`, take AFTER colon (Indo variant: Javanese root)
  3. Re-clean 503 colon entries + 8 mid-string Roman + 16 unbalanced parens
"""
import csv, json, re, unicodedata
from pathlib import Path
from collections import Counter

KAMUS_PATH = '/home/z/my-project/dub-jawa/kamus_jawa.json'
SASTRA_CSV = '/tmp/sastra_dict.csv'
NEW_VERSION = '3.1.2'


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


def clean_v312(raw_jawa: str) -> str:
    """Final cleaner with proper handling of:
    - `;` sense separator (outside parens)
    - `kc.` (kacabab) additional sense separator
    - `. ii ` period + Roman numeral = sense separator (FIX: do this BEFORE colon)
    - `:` Indo variant: Javanese root (FIX: always take AFTER colon)
    - `ut.` utawa = alternative separator (outside parens)
    - `,` alternative separator (outside parens)
    - Leading numbers, abbreviations, Roman numerals
    - Balanced parentheticals
    - Multi-space, trailing markers
    """
    if not raw_jawa:
        return ''
    s = raw_jawa.strip()
    
    # 1. Split by `;` outside parens — take first sense
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
    
    # 2. Split by `kc.` (kacabab) — take first
    kc_parts = re.split(r'\s+kc\.\s+', s, maxsplit=1)
    if len(kc_parts) > 1:
        s = kc_parts[0].strip()
    
    # *** FIX: 3. Split by `. ii ` (period + Roman numeral) — take FIRST sense ***
    # This is sastra's sense separator. Do this BEFORE colon handling.
    # Pattern: `.` + whitespace + Roman numeral (i, ii, iii, iv, v) + whitespace
    sense_splits = re.split(r'\.\s+(?:i{1,3}|iv|vi{0,3})\s+', s, maxsplit=2, flags=re.IGNORECASE)
    if len(sense_splits) > 1:
        s = sense_splits[0].strip()
    
    # 4. Handle `Indo variant: Javanese root` format
    # FIX: ALWAYS take AFTER colon (sastra format is `<Indo>: <Javanese>`)
    # But only if AFTER is non-empty and looks like a word
    if ':' in s:
        before, _, after = s.partition(':')
        after_stripped = after.strip()
        # Take AFTER if it's non-empty and starts with a letter
        if after_stripped and re.match(r"^[a-zA-ZÀ-ÿêà']", after_stripped[0]):
            s = after_stripped
    
    # 5. Split by `ut.` (utawa = "or") OUTSIDE parens — take first alternative
    # Need to do this respecting parens
    ut_parts, current, paren_depth = [], [], 0
    i = 0
    while i < len(s):
        # Check for " ut. " outside parens
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
    
    # 6. Take first alternative before `,` OUTSIDE parens
    parts = _split_outside_parens(s, ',')
    if len(parts) > 1:
        first_part = parts[0].strip()
        if len(first_part) >= 3:
            s = first_part
    
    # 7. Strip leading numbers (sense markers)
    s = re.sub(r'^\d+\s+', '', s)
    
    # 8. Strip leading sastra abbreviations
    abbrevs = r'kc\.|bngs\.|ent\.|up\.|dkk\.|ke\.|nj\.|ar\.|tmr\.|wl\.|i\.|s\.|j\.|bl\.|jl\.|jr\.|b\.|k\.|t\.|w\.|ut\.|kw\.|blg\.|kk\.|bls\.'
    for _ in range(4):
        s = re.sub(rf'^(?:{abbrevs})\s+', '', s)
    
    # 9. Strip leading Roman numerals
    s = re.sub(r'^(?:i{1,3}|iv|vi{0,3})\s+', '', s, flags=re.IGNORECASE)
    
    # 10. Strip mid-string Roman (any remaining)
    s = re.sub(r'\s(?:i{1,3}|iv|vi{0,3})\s', ' ', s, flags=re.IGNORECASE)
    
    # 11. Strip balanced parentheticals
    s = re.sub(r'\([^)]*\)', '', s).strip()
    
    # 12. Strip trailing period/colon
    s = s.rstrip('.:').strip()
    
    # 13. Strip leading dashes/commas
    s = s.lstrip('-,').strip()
    
    # 14. Collapse multi-space
    s = re.sub(r'\s{2,}', ' ', s).strip()
    
    # 15. Strip trailing markers
    s = re.sub(r'\s+(?:lsp|dsb|mis|dkk)\.?\s*$', '', s, flags=re.IGNORECASE).strip()
    
    return s


def is_valid_v312(jawa: str) -> bool:
    """Final validation."""
    if not jawa or len(jawa) < 2:
        return False
    if len(jawa) > 50:
        return False
    # Reject remaining markers as whole words
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
    # Reject unbalanced parens
    if '(' in jawa and ')' not in jawa:
        return False
    if ')' in jawa and '(' not in jawa:
        return False
    # Reject mid-string Roman numerals
    if re.search(r'\s(?:i{1,3}|iv|vi{0,3})\s', jawa, re.IGNORECASE):
        return False
    # Reject if starts with non-letter
    if not re.match(r"^[a-zA-ZÀ-ÿêà']", jawa[0]):
        return False
    return True


def main():
    with open(KAMUS_PATH, encoding='utf-8') as f:
        k = json.load(f)
    id2ng = k['typo_corrections']
    print(f"Before: {len(id2ng):,} entries, version {k['meta']['version']}")
    
    # Load sastra raw
    sastra_raw = {}
    with open(SASTRA_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_word_raw = row.get('Indonesia', '').strip()
            jawa_raw = row.get('Javanese', '').strip()
            if not id_word_raw or not jawa_raw:
                continue
            id_word = re.sub(r'\s*\([^)]*\)', '', id_word_raw).strip()
            id_norm = strip_accents(id_word.lower())
            if id_norm not in sastra_raw:
                sastra_raw[id_norm] = []
            sastra_raw[id_norm].append(jawa_raw)
    
    # Re-clean all sastra-derived entries with v3.1.2 cleaner
    stats = Counter()
    new_id2ng = {}
    fixed_samples = []
    still_buggy = []
    
    for src, tgt in id2ng.items():
        src_norm = strip_accents(src.lower())
        if src_norm not in sastra_raw:
            new_id2ng[src] = tgt
            stats['kept_curated'] += 1
            continue
        
        raw_values = sastra_raw[src_norm]
        chosen = None
        for raw in raw_values:
            cleaned = clean_v312(raw)
            if is_valid_v312(cleaned):
                chosen = cleaned
                break
        
        if chosen is None:
            new_id2ng[src] = tgt
            stats['no_valid_cleaned'] += 1
            if len(still_buggy) < 20:
                still_buggy.append((src, tgt, raw_values[:1]))
        elif chosen == tgt:
            new_id2ng[src] = tgt
            stats['already_correct'] += 1
        else:
            new_id2ng[src] = chosen
            stats['fixed'] += 1
            if len(fixed_samples) < 30:
                fixed_samples.append((src, tgt, chosen))
    
    print(f"\n=== Patch v3.1.2 stats ===")
    print(f"  Kept curated: {stats['kept_curated']:,}")
    print(f"  Already correct: {stats['already_correct']:,}")
    print(f"  FIXED: {stats['fixed']:,}")
    print(f"  No valid cleaned (kept existing): {stats['no_valid_cleaned']:,}")
    
    print(f"\n=== Sample FIXED ===")
    for s, old, new in fixed_samples[:25]:
        print(f"  {s!r:20s}")
        print(f"    OLD: {old!r}")
        print(f"    NEW: {new!r}")
    
    print(f"\n=== Still buggy (no valid cleaned) ===")
    for s, t, raws in still_buggy:
        print(f"  {s!r:20s} -> {t!r}")
        print(f"    sastra raw: {raws[0]!r}")
    
    # Save
    k['typo_corrections'] = new_id2ng
    k['meta']['version'] = NEW_VERSION
    k['meta']['last_updated'] = '2026-10-06'
    k['meta']['typo_corrections_count'] = len(new_id2ng)
    k['meta']['note'] = (
        f"v{NEW_VERSION}: FINAL PATCH — fix 503 colon entries (always take AFTER colon, "
        "sastra format is `Indo variant: Javanese root`). Fix 8 mid-string Roman numerals "
        "(split on `. ii ` first). Fix unbalanced parens (better paren-aware splitting). "
        f"{stats['fixed']:,} entries fixed. "
        "v3.1.0-1: re-import sastra with cleaner fixes. v3.0.x: full sastra import."
    )
    
    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)
    
    print(f"\nAfter: {len(new_id2ng):,} entries")
    print(f"Saved: {Path(KAMUS_PATH).stat().st_size:,} bytes")
    
    # Final audit
    print(f"\n=== FINAL AUDIT ===")
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
    
    # Verify specific entries
    print(f"\n=== Verify previously-buggy ===")
    for w in ['uang', 'bunuh', 'pikir', 'pindah', 'paling', 'amat', 'kuda', 
              'acuh', 'adam', 'abantara', 'ambal', 'aras', 'badam', 'acah',
              'abai', 'abar', 'lampas', 'lampir', 'abur', 'adar', 'agah']:
        our = new_id2ng.get(w, '(not in kamus)')
        print(f"  {w!r:15s} -> {our!r}")


if __name__ == '__main__':
    main()

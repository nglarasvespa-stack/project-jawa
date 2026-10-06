#!/usr/bin/env python3
"""
Patch kamus v3.1.0 → v3.1.1: fix remaining bugs.

Bugs to fix:
  1. Entries that still have Indonesian derivation as value (e.g., 'acah' → 'mengacah')
     because cleaner failed (ut. was treated as bad marker, not alternative separator)
  2. Remaining 16 unbalanced parens
  3. Remaining 8 mid-string Roman numerals

Strategy: re-apply FIXED cleaner to all sastra-derived entries.
"""
import csv, json, re, unicodedata
from pathlib import Path
from collections import Counter

KAMUS_PATH = '/home/z/my-project/dub-jawa/kamus_jawa.json'
SASTRA_CSV = '/tmp/sastra_dict.csv'
NEW_VERSION = '3.1.1'


def strip_accents(s):
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _split_outside_parens(s, delimiter=','):
    """Split by delimiter only outside parens."""
    parts = []
    current = []
    paren_depth = 0
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


def clean_javanese_v311(raw_jawa: str) -> str:
    """FIXED cleaner — handles ut., kc., colon format, Roman numerals mid-string."""
    if not raw_jawa:
        return ''
    s = raw_jawa.strip()
    
    # 1. Split by `;` outside parens (take first sense)
    parts_semi = []
    current = []
    paren_depth = 0
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
    
    # 2. Split by `kc.` (kacabab = "also") — take first
    kc_parts = re.split(r'\s+kc\.\s+', s, maxsplit=1)
    if len(kc_parts) > 1:
        s = kc_parts[0].strip()
    
    # 3. Handle `Indonesian_derivation: Javanese_root` format
    # If before `:` looks like Indonesian derivation (di/meng/ter/ke/men/ber prefix),
    # take after `:`
    if ':' in s:
        before, _, after = s.partition(':')
        before_stripped = before.strip()
        after_stripped = after.strip()
        # Check if before looks like Indonesian derivation (prefix + lowercase word)
        if after_stripped and re.match(
            r'^(di|ter|ke|meng|mem|men|meny|ber|se|pe|diper|keber|keter)[a-z]{3,}',
            before_stripped.lower()
        ):
            s = after_stripped
    
    # 4. Split by `ut.` (utawa = "or") — take first alternative
    ut_parts = re.split(r'\s+ut\.\s+', s, maxsplit=1)
    if len(ut_parts) > 1:
        s = ut_parts[0].strip()
    
    # 5. Take first alternative before `,` outside parens
    parts = _split_outside_parens(s, ',')
    if len(parts) > 1:
        first_part = parts[0].strip()
        if len(first_part) >= 3:
            s = first_part
    
    # 6. Strip leading numbers (sense markers)
    s = re.sub(r'^\d+\s+', '', s)
    
    # 7. Strip leading sastra abbreviations (extended)
    abbrevs = r'kc\.|bngs\.|ent\.|up\.|dkk\.|ke\.|nj\.|ar\.|tmr\.|wl\.|i\.|s\.|j\.|bl\.|jl\.|jr\.|b\.|k\.|t\.|w\.|ut\.|kw\.|blg\.|kk\.|bls\.'
    for _ in range(4):
        s = re.sub(rf'^(?:{abbrevs})\s+', '', s)
    
    # 8. Strip leading Roman numerals
    s = re.sub(r'^(?:i{1,3}|iv|vi{0,3})\s+', '', s, flags=re.IGNORECASE)
    
    # 9. Strip mid-string Roman numerals like ". ii content"
    s = re.sub(r'\.\s+(?:i{1,3}|iv|vi{0,3})\s+', '. ', s, flags=re.IGNORECASE)
    s = re.sub(r'\s(?:i{1,3}|iv|vi{0,3})\s', ' ', s, flags=re.IGNORECASE)
    
    # 10. Strip balanced parentheticals
    s = re.sub(r'\([^)]*\)', '', s).strip()
    
    # 11. Strip trailing period
    s = s.rstrip('.').strip()
    
    # 12. Strip leading dashes
    s = s.lstrip('-').strip()
    
    # 13. Collapse multi-space
    s = re.sub(r'\s{2,}', ' ', s).strip()
    
    # 14. Strip trailing markers
    s = re.sub(r'\s+(?:lsp|dsb|mis|dkk)\.?\s*$', '', s, flags=re.IGNORECASE).strip()
    
    return s


def is_valid_v311(jawa: str) -> bool:
    """Validate cleaned translation.
    
    FIXED: bad_markers check pakai word boundary (regex \\b) supaya
    'mis' tidak match 'amis' (false positive).
    """
    if not jawa or len(jawa) < 2:
        return False
    if len(jawa) > 50:
        return False
    # Reject remaining markers as WHOLE WORDS (word boundary)
    # Pattern: \b(?:marker1|marker2|...)\b  (case-insensitive)
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
    # Reject mid-string Roman numerals (whole word, not substring)
    if re.search(r'\s(?:i{1,3}|iv|vi{0,3})\s', jawa, re.IGNORECASE):
        return False
    return True


def main():
    # Load kamus
    with open(KAMUS_PATH, encoding='utf-8') as f:
        k = json.load(f)
    id2ng = k['typo_corrections']
    
    print(f"Before: {len(id2ng):,} entries, version {k['meta']['version']}")
    
    # Load sastra raw for re-cleaning
    sastra_raw = {}  # id_norm -> list of raw Javanese values
    with open(SASTRA_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_word_raw = row.get('Indonesia', '').strip()
            jawa_raw = row.get('Javanese', '').strip()
            if not id_word_raw or not jawa_raw:
                continue
            # Clean key (strip parens, etc.)
            id_word = re.sub(r'\s*\([^)]*\)', '', id_word_raw).strip()
            id_norm = strip_accents(id_word.lower())
            if id_norm not in sastra_raw:
                sastra_raw[id_norm] = []
            sastra_raw[id_norm].append(jawa_raw)
    
    print(f"Sastra raw loaded: {len(sastra_raw):,} unique Indonesian words")
    
    # For each entry in kamus, try to re-clean using FIXED cleaner
    stats = Counter()
    new_id2ng = {}
    buggy_existing = []
    fixed_samples = []
    
    for src, tgt in id2ng.items():
        src_norm = strip_accents(src.lower())
        if src_norm not in sastra_raw:
            # Not in sastra — keep as-is (curated entry)
            new_id2ng[src] = tgt
            stats['kept_curated'] += 1
            continue
        
        # In sastra — try to re-clean
        raw_values = sastra_raw[src_norm]
        chosen = None
        for raw in raw_values:
            cleaned = clean_javanese_v311(raw)
            if is_valid_v311(cleaned):
                chosen = cleaned
                break
        
        if chosen is None:
            # Couldn't find valid cleaned — keep existing (might be buggy, but at least exists)
            new_id2ng[src] = tgt
            stats['no_valid_cleaned'] += 1
            if len(buggy_existing) < 10:
                buggy_existing.append((src, tgt, raw_values[:2]))
        elif chosen == tgt:
            # Already cleaned correctly
            new_id2ng[src] = tgt
            stats['already_correct'] += 1
        else:
            # Need to update with fixed version
            new_id2ng[src] = chosen
            stats['fixed'] += 1
            if len(fixed_samples) < 20:
                fixed_samples.append((src, tgt, chosen))
    
    print(f"\n=== Patch stats ===")
    print(f"  Kept curated (not in sastra): {stats['kept_curated']:,}")
    print(f"  Already correct: {stats['already_correct']:,}")
    print(f"  FIXED with new cleaner: {stats['fixed']:,}")
    print(f"  No valid cleaned (kept existing): {stats['no_valid_cleaned']:,}")
    
    print(f"\n=== Sample FIXED entries ===")
    for s, old, new in fixed_samples[:20]:
        print(f"  {s!r:20s}")
        print(f"    OLD: {old!r}")
        print(f"    NEW: {new!r}")
    
    print(f"\n=== Sample entries that couldn't be cleaned (still buggy) ===")
    for s, t, raws in buggy_existing:
        print(f"  {s!r} -> {t!r}  (sastra raw: {raws[0]!r})")
    
    # Save
    k['typo_corrections'] = new_id2ng
    k['meta']['version'] = NEW_VERSION
    k['meta']['last_updated'] = '2026-10-06'
    k['meta']['typo_corrections_count'] = len(new_id2ng)
    k['meta']['note'] = (
        f"v{NEW_VERSION}: PATCH — re-clean all sastra-derived entries with FIXED cleaner. "
        f"{stats['fixed']:,} entries fixed. Bug fixes: handle 'ut.' (utawa=or) and 'kc.' (kacabab=also) "
        f"as alternative separators, fix mid-string Roman numerals, fix unbalanced parens. "
        "v3.1.0: re-import dengan cleaner colon-handling fix. v3.0.x: full sastra import."
    )
    
    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)
    
    print(f"\nAfter: {len(new_id2ng):,} entries")
    print(f"Saved: {Path(KAMUS_PATH).stat().st_size:,} bytes")
    
    # Final audit
    print(f"\n=== FINAL AUDIT ===")
    paren_unbalanced = sum(1 for v in new_id2ng.values() 
                           if ('(' in v and ')' not in v) or (')' in v and '(' not in v))
    roman_mid = sum(1 for v in new_id2ng.values()
                    if re.search(r'\s(?:i{1,3}|iv|vi{0,3})\s', v, re.IGNORECASE))
    multi_space = sum(1 for v in new_id2ng.values() if '  ' in v)
    ut_remaining = sum(1 for v in new_id2ng.values() if 'ut.' in v.lower())
    print(f"  Unbalanced parens: {paren_unbalanced}")
    print(f"  Mid-string Roman numerals: {roman_mid}")
    print(f"  Multi-space: {multi_space}")
    print(f"  'ut.' remaining (should be 0): {ut_remaining}")
    
    # Verify specific previously-buggy entries
    print(f"\n=== Verify previously-buggy entries ===")
    for w in ['acah', 'abai', 'abar', 'lampas', 'lampir', 'abur', 'adar', 'agah',
              'abah-abah', 'ambal', 'aras', 'badam']:
        our = new_id2ng.get(w, '(not in kamus)')
        print(f"  {w!r:15s} -> {our!r}")


if __name__ == '__main__':
    main()

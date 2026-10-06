#!/usr/bin/env python3
"""
Cleanup kamus_jawa.json v3.0.1 → v3.0.2.

Fix keys with non-letter chars:
  1. Comma-separated variant keys (241) → split, take first variant
     e.g., "afrit, 'ifrit" → "afrit"  (drop second variant since it has apostrophe)
  2. Parens in keys (30) → split into two entries
     e.g., "alur(an)" → "alur" + "aluran"  (both forms valid)
  3. Colon in keys (1) → strip

After cleanup: all keys should be clean alphabetic (with optional dash/apostrophe).
"""
import json
import re
import unicodedata
from pathlib import Path
from collections import Counter

KAMUS_PATH = '/home/z/my-project/dub-jawa/kamus_jawa.json'
NEW_VERSION = '3.0.2'


def strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def split_key_variants(raw_key: str) -> list[str]:
    """Split a sastra.org key into multiple variant forms.
    
    Examples:
      'afrit, \'ifrit' -> ['afrit']  (drop second variant with apostrophe)
      'abah-abah' -> ['abah-abah']  (no comma, keep as-is)
      'alur(an)' -> ['alur', 'aluran']  (split parens)
      'perabung (an)' -> ['perabung', 'perabungan']
      'betara, betari:' -> ['betara']  (drop second variant + colon)
    """
    s = raw_key.strip()
    # Strip trailing colon
    s = s.rstrip(':').strip()
    
    # Handle parens: split into 2 forms (without parens, with parens-content appended)
    # e.g., 'alur(an)' -> 'alur' + 'aluran'
    # 'perabung (an)' -> 'perabung' + 'perabungan'
    paren_match = re.search(r'(\S*)\s*\(([^)]+)\)', s)
    forms_without_parens = []
    if paren_match:
        prefix = paren_match.group(1).strip()
        suffix = paren_match.group(2).strip()
        if prefix:
            forms_without_parens.append(prefix)
        if prefix and suffix:
            forms_without_parens.append(prefix + suffix)
        # Remove the parens part from s for further comma-splitting
        s = s.replace(paren_match.group(0), prefix).strip()
    
    # Handle comma: take first variant only
    # (second variant often has weird chars like apostrophe)
    if ',' in s:
        first = s.split(',')[0].strip()
        # Validate first variant — only letters, dashes, apostrophes
        if first and re.match(r"^[a-zA-Zà-ÿê\s\-\']+$", first):
            forms_without_parens.insert(0, first)
        return forms_without_parens
    
    # No comma — validate the whole string
    if re.match(r"^[a-zA-Zà-ÿê\s\-\']+$", s):
        forms_without_parens.insert(0, s)
    
    # Dedupe + filter empty
    seen = set()
    result = []
    for f in forms_without_parens:
        f = f.strip()
        if f and f not in seen:
            seen.add(f)
            result.append(f)
    return result


def main():
    with open(KAMUS_PATH, encoding='utf-8') as f:
        k = json.load(f)
    
    id2ng = k['typo_corrections']
    n2k = k['ngoko_to_krama']
    
    print(f"Before: typo={len(id2ng):,}, n2k={len(n2k):,}")
    
    # Identify keys that need cleaning
    weird_keys = []
    for s in id2ng.keys():
        weird = re.findall(r'[^a-zA-Zà-ÿê\s\-\']', s)
        if weird:
            weird_keys.append(s)
    
    print(f"Keys with non-letter chars: {len(weird_keys)}")
    
    # Build new kamus: keep clean keys, split weird keys
    new_id2ng = {}
    stats = Counter()
    new_from_split = []
    
    for src, tgt in id2ng.items():
        weird = re.findall(r'[^a-zA-Zà-ÿê\s\-\']', src)
        if not weird:
            # Clean key — keep as-is
            new_id2ng[src] = tgt
            stats['kept_clean'] += 1
        else:
            # Need to split
            variants = split_key_variants(src)
            if not variants:
                # Cannot clean — drop
                stats['dropped_uncleanable'] += 1
                continue
            added = False
            for v in variants:
                v_norm = v.lower()
                # Strip accents from key (existing convention)
                v_key = strip_accents(v_norm)
                if v_key and v_key not in new_id2ng:
                    new_id2ng[v_key] = tgt
                    added = True
            if added:
                stats['split_to_new'] += 1
                if len(new_from_split) < 10:
                    new_from_split.append((src, variants, tgt))
            else:
                stats['split_but_duplicate'] += 1
    
    print(f"\nCleanup stats:")
    print(f"  Kept clean: {stats['kept_clean']:,}")
    print(f"  Split to new variants: {stats['split_to_new']:,}")
    print(f"  Split but all dupes: {stats['split_but_duplicate']:,}")
    print(f"  Dropped (uncleanable): {stats['dropped_uncleanable']:,}")
    
    print(f"\nSample split entries:")
    for orig, variants, tgt in new_from_split:
        print(f"  {orig!r:30s} -> variants: {variants}, target: {tgt!r}")
    
    # Save
    k['typo_corrections'] = new_id2ng
    k['ngoko_to_krama'] = n2k
    k['meta']['version'] = NEW_VERSION
    k['meta']['last_updated'] = '2026-10-06'
    k['meta']['typo_corrections_count'] = len(new_id2ng)
    k['meta']['ngoko_to_krama_count'] = len(n2k)
    k['meta']['note'] = (
        f"v{NEW_VERSION}: CLEANUP KEYS — split 241 comma-separated variants, "
        f"30 parens variants (e.g., 'alur(an)' -> 'alur' + 'aluran'), "
        f"strip 1 trailing colon. "
        f"v3.0.1: Strip trailing 'lsp'/'dsb'/'mis' markers + multi-space. "
        f"v3.0.0: Import all sastra.org (10,242 new entries). Baku spelling preserved. "
        "Coverage 75.3% → 81.3%. AUDIT: 0 hallucination markers."
    )
    
    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)
    
    print(f"\nAfter: typo={len(new_id2ng):,}")
    print(f"File size: {Path(KAMUS_PATH).stat().st_size:,} bytes")
    
    # Final audit
    print(f"\n=== FINAL KEY AUDIT ===")
    weird_remaining = sum(1 for s in new_id2ng.keys() 
                           if re.findall(r'[^a-zA-Zà-ÿê\s\-\']', s))
    print(f"  Keys with non-letter chars: {weird_remaining}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Cleanup kamus_jawa.json v3.0.0 → v3.0.1.

Bersihkan sampah yang lolos dari import v3.0.0:
  1. Multi-space in values (23 entries) → normalize ke single space
  2. Trailing 'lsp' / 'dsb' / 'mis' (without period) markers (72 entries) → strip trailing marker
  3. Entries that become empty/invalid after cleaning → remove
  4. Long values >50 chars → keep (legitimate sastra descriptions, but flag for review)
"""
import json
import re
import unicodedata
from pathlib import Path
from collections import Counter

KAMUS_PATH = '/home/z/my-project/dub-jawa/kamus_jawa.json'
NEW_VERSION = '3.0.1'


def strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# Trailing marker patterns (without period — sastra's "lsp", "dsb", "mis")
# These appear at end of values like 'kayu sanggan gedheg lsp'
TRAILING_MARKERS = [
    r'\s+lsp\s*$',      # dan lain sebagainya pula
    r'\s+dsb\s*$',      # dan sebagainya
    r'\s+mis\s*$',      # misalnya
    r'\s+lsp\.\s*$',    # with period
    r'\s+dsb\.\s*$',    # with period
    r'\s+mis\.\s*$',    # with period
    r'\s+dkk\.?\s*$',   # dan kawan-kawan
    r'\s+bl\.?\s*$',    # baris lingsir?
]


def clean_value(s: str) -> str:
    """Apply all cleaning steps to a kamus value."""
    if not s:
        return s
    # 1. Strip trailing markers
    for pat in TRAILING_MARKERS:
        s = re.sub(pat, '', s, flags=re.IGNORECASE)
    # 2. Normalize multi-space to single space
    s = re.sub(r'\s{2,}', ' ', s)
    # 3. Strip leading/trailing whitespace
    s = s.strip()
    # 4. Strip trailing period if value is just a word (not end of sentence)
    s = s.rstrip('.').strip()
    return s


def is_valid_value(s: str) -> bool:
    """Check if value is valid (not empty, has letters, not too short)."""
    if not s or len(s) < 2:
        return False
    # Must have at least one letter
    if not re.search(r'[a-zA-ZÀ-ÿêà]', s):
        return False
    # Reject if still has 'lsp' / 'dsb' / etc. after cleaning (means there's something
    # weird in the middle, not just at the end)
    if re.search(r'\b(lsp|dsb|mis|dkk)\b', s, flags=re.IGNORECASE):
        return False
    # Reject if has digits
    if re.search(r'\d', s):
        return False
    return True


def main():
    # Load
    with open(KAMUS_PATH, encoding='utf-8') as f:
        k = json.load(f)
    
    id2ng = k['typo_corrections']
    n2k = k['ngoko_to_krama']
    
    print(f"Before: typo={len(id2ng):,}, n2k={len(n2k):,}")
    
    # === Clean typo_corrections values ===
    new_id2ng = {}
    stats = Counter()
    removed_entries = []
    cleaned_entries = []
    
    for src, tgt in id2ng.items():
        original = tgt
        cleaned = clean_value(tgt)
        
        if cleaned == original:
            # No change
            new_id2ng[src] = tgt
            stats['unchanged'] += 1
        elif not is_valid_value(cleaned):
            # Invalid after cleaning — remove
            stats['removed_invalid'] += 1
            removed_entries.append((src, original, cleaned))
        else:
            # Changed but still valid
            new_id2ng[src] = cleaned
            stats['cleaned'] += 1
            cleaned_entries.append((src, original, cleaned))
    
    # === Clean n2k values (same logic) ===
    new_n2k = {}
    n2k_removed = []
    n2k_cleaned = []
    for src, tgt in n2k.items():
        original = tgt
        cleaned = clean_value(tgt)
        if cleaned == original:
            new_n2k[src] = tgt
        elif not is_valid_value(cleaned):
            n2k_removed.append((src, original, cleaned))
        else:
            new_n2k[src] = cleaned
            n2k_cleaned.append((src, original, cleaned))
    
    print(f"\n=== typo_corrections cleanup ===")
    print(f"  Unchanged:     {stats['unchanged']:,}")
    print(f"  Cleaned:      {stats['cleaned']:,}")
    print(f"  Removed (invalid after clean): {stats['removed_invalid']:,}")
    
    print(f"\n=== n2k cleanup ===")
    print(f"  Cleaned:      {len(n2k_cleaned):,}")
    print(f"  Removed:      {len(n2k_removed):,}")
    
    # Show samples
    print(f"\n=== Sample cleaned (typo_corrections) ===")
    for s, o, c in cleaned_entries[:10]:
        print(f"  {s!r:25s}")
        print(f"    BEFORE: {o!r}")
        print(f"    AFTER:  {c!r}")
    
    print(f"\n=== Sample removed (typo_corrections) ===")
    for s, o, c in removed_entries[:8]:
        print(f"  {s!r:25s}  before={o!r}  after={c!r}")
    
    # Update kamus
    k['typo_corrections'] = new_id2ng
    k['ngoko_to_krama'] = new_n2k
    k['meta']['version'] = NEW_VERSION
    k['meta']['last_updated'] = '2026-10-06'
    k['meta']['typo_corrections_count'] = len(new_id2ng)
    k['meta']['ngoko_to_krama_count'] = len(new_n2k)
    k['meta']['note'] = (
        f"v{NEW_VERSION}: CLEANUP — strip trailing 'lsp'/'dsb'/'mis' markers "
        f"({stats['cleaned']} cleaned, {stats['removed_invalid']} removed), "
        f"normalize multi-space. "
        f"v3.0.0: Import all sastra.org (10,242 new entries). Baku spelling preserved. "
        "Coverage 75.3% → 81.3%. AUDIT: 0 hallucination markers."
    )
    
    # Save
    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)
    
    print(f"\nAfter: typo={len(new_id2ng):,}, n2k={len(new_n2k):,}")
    print(f"Saved: {Path(KAMUS_PATH).stat().st_size:,} bytes")
    
    # === Re-audit sampah after cleanup ===
    print(f"\n=== RE-AUDIT after cleanup ===")
    multi_space = sum(1 for v in new_id2ng.values() if '  ' in v)
    lsp_leak = sum(1 for v in new_id2ng.values() if re.search(r'\b(lsp|dsb|mis|dkk)\b', v, re.IGNORECASE))
    print(f"  Multi-space: {multi_space}")
    print(f"  lsp/dsb/mis leak: {lsp_leak}")


if __name__ == '__main__':
    main()

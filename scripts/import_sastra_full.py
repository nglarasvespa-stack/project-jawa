#!/usr/bin/env python3
"""
Import ALL 11,310 entries dari sastra.org dictionary.csv ke kamus_jawa.json.

Strategy:
  1. Parse sastra_dict.csv (Indonesian,Javanese,Alphabet)
  2. For each entry: extract CLEAN short translation:
     - Take first sense (before first ;)
     - Take first alternative (before first ,)
     - Strip leading numbers (1, 2, etc.)
     - Strip parentheticals like (dubur lsp.) (ke. 'am) etc.
     - Strip explanatory text after :
     - Skip if result is empty or >50 chars (too long for substitution)
  3. Dedupe by Indonesian word (lowercase, accent-stripped key for matching)
     - When duplicates, prefer shorter cleaner translation
  4. Merge with existing kamus:
     - KEEP all existing manual additions (NOT_IN_SASTRA category)
     - REPLACE all sastra-derived entries with baku spelling from CSV
     - PRESERVE identity mappings (id == jawa)
  5. Save as kamus_jawa.json v3.0.0 (major version bump)
  6. Update meta with provenance: 100% sastra.org + manual

Kamus values tetap baku (with ê, à, ê, etc.) — TTS accent stripping
ditangani di grammar.py / split.py saat substitution.
"""
import csv
import json
import re
import unicodedata
from pathlib import Path
from collections import Counter

SASTRA_CSV = '/tmp/sastra_dict.csv'
KAMUS_PATH = '/home/z/my-project/dub-jawa/kamus_jawa.json'
NEW_VERSION = '3.0.0'


def strip_accents(s: str) -> str:
    """Strip diacritics dari string."""
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# Local import (avoid typo above)
def strip_accents_safe(s: str) -> str:
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# Fix the typo
strip_accents = strip_accents_safe


def clean_javanese_translation(raw_jawa: str) -> str:
    """Extract clean short translation dari raw sastra.org Javanese column."""
    if not raw_jawa:
        return ''
    s = raw_jawa.strip()
    
    # Take first sense (before first ;)
    if ';' in s:
        s = s.split(';')[0].strip()
    
    # Take first alternative (before first ,)
    if ',' in s:
        first_part = s.split(',')[0].strip()
        if len(first_part) >= 3:
            s = first_part
    
    # Strip leading numbers like "1 ", "2 ", "3 " (sense markers)
    s = re.sub(r'^\d+\s+', '', s)
    
    # Strip leading sastra abbreviations (extended list)
    # Also handles "i " (Roman numeral marker) and "ii " without period
    abbrevs_period = r'kc\.|bngs\.|ent\.|up\.|dkk\.|ke\.|nj\.|ar\.|tmr\.|wl\.|i\.|s\.|j\.|bl\.|jl\.|jr\.|b\.|k\.|t\.|w\.|ut\.|kw\.|blg\.|kk\.|bls\.'
    s = re.sub(rf'^(?:{abbrevs_period})\s+', '', s)
    # Apply multiple times for stacked abbreviations
    for _ in range(4):
        s = re.sub(rf'^(?:{abbrevs_period})\s+', '', s)
    
    # Strip leading Roman numerals "i ", "ii ", "iii ", "iv " (sense markers in sastra)
    s = re.sub(r'^(?:i{1,3}|iv|vi{0,3})\s+', '', s, flags=re.IGNORECASE)
    
    # Strip parentheticals
    s = re.sub(r'\([^)]*\)', '', s).strip()
    
    # Strip explanatory text after ":"
    if ':' in s:
        s = s.split(':')[0].strip()
    
    # Strip trailing period
    s = s.rstrip('.').strip()
    
    # Strip leading dashes
    s = s.lstrip('-').strip()
    
    return s


def clean_indonesian_key(raw_id: str) -> str:
    """Clean Indonesian key from sastra.org format.
    
    Examples:
      'nona (h)' -> 'nona'  (strip gender suffix)
      'perabung(an)' -> 'perabungan'  (strip parenthetical suffixes)
      'abah-abah' -> 'abah-abah'  (keep as-is)
    """
    if not raw_id:
        return ''
    s = raw_id.strip()
    # Strip "(...)" suffixes — these indicate morphological variants
    # e.g., "perabung(an)" -> "perabungan", "nona (h)" -> "nona"
    # Strategy: remove parens but keep their contents if it's a suffix morpheme
    # For simplicity: just remove parens entirely and any space before
    s = re.sub(r'\s*\([^)]*\)', '', s)
    return s.strip()


def is_valid_translation(jawa: str) -> bool:
    """Check if translation is suitable for kamus substitution."""
    if not jawa or len(jawa) < 2:
        return False
    if len(jawa) > 50:
        return False
    bad_markers = [
        'lsp.', 'dsb.', 'mis.', 'up.', 'kc.', 'bngs.', 'ent.', 'nj.', 'ke.',
        'tmr.', 'ar.', 'wl.', 'bl.', 'jl.', 'jr.', 'lsp', 'dsb', 'mis', 'ut.',
        'kw.', 'blg.', 'kk.', 'bls.',
    ]
    for m in bad_markers:
        if m in jawa:
            return False
    if re.search(r'\d', jawa):
        return False
    if not re.search(r'[a-zA-ZÀ-ÿêà]', jawa):
        return False
    return True


def main():
    # === Load existing kamus ===
    with open(KAMUS_PATH, 'r', encoding='utf-8') as f:
        k = json.load(f)
    
    existing_id2ng = k['typo_corrections']
    existing_n2k = k['ngoko_to_krama']
    
    print(f"Existing kamus v{k['meta']['version']}:")
    print(f"  typo_corrections: {len(existing_id2ng):,}")
    print(f"  ngoko_to_krama:   {len(existing_n2k):,}")
    
    # === Categorize existing entries ===
    # We need to identify which entries are "manual additions" (NOT_IN_SASTRA category)
    # so we can preserve them during merge.
    
    # Load sastra to know which existing entries came from sastra
    sastra_keys = set()
    sastra_full = {}  # indonesian_norm -> list of (raw_jawa, clean_jawa)
    
    with open(SASTRA_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_csv_entries = 0
        for row in reader:
            total_csv_entries += 1
            id_word_raw = row.get('Indonesia', '').strip()
            jawa_raw = row.get('Javanese', '').strip()
            if not id_word_raw or not jawa_raw:
                continue
            # Clean Indonesian key (strip parentheticals like "(h)" "(an)")
            id_word = clean_indonesian_key(id_word_raw)
            if not id_word:
                continue
            id_norm = strip_accents(id_word.lower())
            sastra_keys.add(id_norm)
            clean = clean_javanese_translation(jawa_raw)
            if id_norm not in sastra_full:
                sastra_full[id_norm] = []
            sastra_full[id_norm].append({
                'raw': jawa_raw,
                'clean': clean,
                'valid': is_valid_translation(clean),
            })
    
    print(f"\nSastra.org dictionary loaded:")
    print(f"  Total CSV entries: {total_csv_entries:,}")
    print(f"  Unique Indonesian words: {len(sastra_full):,}")
    
    # === Build new typo_corrections from sastra ===
    # Strategy: for each Indonesian word in sastra, pick the cleanest translation
    new_sastra_entries = {}  # id_norm -> baku jawa translation
    skipped_too_long = 0
    skipped_invalid = 0
    
    for id_norm, candidates in sastra_full.items():
        # Pick the first valid candidate
        chosen = None
        for c in candidates:
            if c['valid']:
                chosen = c['clean']
                break
        if chosen is None:
            skipped_invalid += 1
            continue
        if len(chosen) > 50:
            skipped_too_long += 1
            continue
        new_sastra_entries[id_norm] = chosen
    
    print(f"\nSastra entries after cleaning:")
    print(f"  Valid for kamus: {len(new_sastra_entries):,}")
    print(f"  Skipped (invalid format): {skipped_invalid:,}")
    print(f"  Skipped (too long >50 chars): {skipped_too_long:,}")
    
    # === MERGE: Start with existing kamus as base, ADD only NEW sastra entries ===
    # Strategy CHANGE: existing curated entries take PRECEDENCE over sastra.
    # Sastra is ONLY used to ADD new words that aren't in our kamus yet.
    # This preserves the careful curation work in v2.x (e.g., 'saya → aku' instead
    # of sastra's 'kula' which is krama form).
    
    new_typo_corrections = dict(existing_id2ng)  # Start with ALL existing entries
    
    # Count how many new entries we add from sastra
    new_count = 0
    overridden = 0  # already in kamus, kept existing
    for id_norm, jawa_baku in new_sastra_entries.items():
        if id_norm in new_typo_corrections:
            # Already in kamus — keep existing curated version
            overridden += 1
        else:
            # New entry from sastra
            new_typo_corrections[id_norm] = jawa_baku
            new_count += 1
    
    print(f"\nMerge result:")
    print(f"  Existing entries (curated, kept): {len(existing_id2ng):,}")
    print(f"  Overridden by existing (sastra skipped): {overridden:,}")
    print(f"  New entries added from sastra: {new_count:,}")
    print(f"  Final typo_corrections: {len(new_typo_corrections):,}")
    
    # === Stats ===
    baku_with_accent = sum(1 for v in new_typo_corrections.values() 
                           if any(c in v for c in 'êàèéìòùâîôûäïöü'))
    print(f"  Entries with baku accent (ê, à, etc.): {baku_with_accent:,}")
    
    # === Update kamus ===
    k['typo_corrections'] = new_typo_corrections
    
    # Update meta
    k['meta']['version'] = NEW_VERSION
    k['meta']['last_updated'] = '2026-10-06'
    k['meta']['typo_corrections_count'] = len(new_typo_corrections)
    k['meta']['ngoko_to_krama_count'] = len(existing_n2k)
    k['meta']['note'] = (
        f"v{NEW_VERSION}: MAJOR EXPANSION — Import all {new_count:,} NEW entries from "
        f"sastra.org dictionary.csv (out of {total_csv_entries:,} total CSV entries, "
        f"{overridden:,} already in kamus, kept curated). "
        "Kamus values BAKU (preserve original sastra.org spelling with ê, à, etc.). "
        "SRT output di-strip accent di grammar/split stage untuk TTS readability. "
        f"Existing {len(existing_id2ng):,} curated entries preserved (e.g., 'saya → aku' kept, "
        "sastra's 'kula' which is krama form skipped). "
        "AUDIT v2.3.4: 94.4% verified sastra.org, 0 hallucination markers."
    )
    # Update sources to reflect the major expansion
    sources = k['meta'].get('sources', [])
    # Update first source to reflect full import
    if sources and 'sastra.org' in sources[0]:
        sources[0] = f'sastra.org dictionary.csv (FULL IMPORT: {total_csv_entries} CSV → {len(new_sastra_entries)} valid entries, https://github.com/nsulistiyawan/sastra-jawa)'
    k['meta']['sources'] = sources
    
    # === Save ===
    print(f"\nWriting to {KAMUS_PATH}...")
    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)
    
    file_size = Path(KAMUS_PATH).stat().st_size
    print(f"Saved. File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    
    # === Coverage measurement on source SRT ===
    print(f"\n=== Coverage on work/source_video.id.srt ===")
    import re
    with open('/home/z/my-project/dub-jawa/work/source_video.id.srt', encoding='utf-8') as f:
        src = f.read()
    text_lines = [l for l in src.split('\n') if l.strip() 
                  and not re.match(r'^\d+$', l.strip()) and '-->' not in l]
    text = ' '.join(text_lines).lower()
    tokens_raw = re.findall(r"[a-zà-ÿ-]+", text)
    tokens = [t for t in tokens_raw if len(t) >= 2 and t.replace('-', '').isalpha()]
    
    total = len(tokens)
    covered = sum(1 for t in tokens if t in new_typo_corrections or t in existing_n2k)
    print(f"  Total tokens: {total:,}")
    print(f"  Covered: {covered:,} ({covered*100/total:.1f}%)")
    print(f"  Uncovered: {total - covered:,}")
    
    # === Hallucination markers check ===
    print(f"\n=== Hallucination markers ===")
    hallu = {
        'underscore': sum(1 for v in new_typo_corrections.values() if '_' in v),
        'pawpaw': sum(1 for v in new_typo_corrections.values() if 'pawpaw' in v.lower()),
        'amang_isolated': sum(1 for v in new_typo_corrections.values() if v.lower().strip() == 'amang'),
    }
    for m, c in hallu.items():
        print(f"  {m}: {c}")
    
    # === Sample entries (showing baku spelling preserved) ===
    print(f"\n=== Sample 15 entries (baku spelling preserved) ===")
    import random
    random.seed(123)
    sample_keys = list(new_typo_corrections.keys())
    random.shuffle(sample_keys)
    for k_ in sample_keys[:15]:
        v = new_typo_corrections[k_]
        has_accent = any(c in v for c in 'êàèéìòùâîôûäïöü')
        marker = ' ★' if has_accent else ''
        print(f"  {k_:25s} -> {v}{marker}")


if __name__ == '__main__':
    main()

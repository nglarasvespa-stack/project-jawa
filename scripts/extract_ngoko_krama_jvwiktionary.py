#!/usr/bin/env python3
"""Extract ngoko-krama pairs HANYA dari jvwiktionary-latest.xml.

Baca tiap halaman {{basa|jv}} (page title = ngoko word).
Cari template:
  - {{ngoko|X|inggil=Y}}  → krama=X, krama_inggil=Y
  - {{krama|X}}           → krama=X
  - inggil=Y              → krama_inggil=Y

Output: dub-jawa/data/jvwiktionary_ngoko_krama.json
Hanya pasangan yang ada krama-nya (skip yang nggak punya).
"""
import re
import json
from pathlib import Path

XML_PATH = Path('/tmp/my-project/dub-jawa/data/jvwiktionary-latest.xml')
OUT_PATH = Path('/home/z/my-project/download/jvwiktionary_ngoko_krama.json')


def extract_krama(text):
    """Cari {{krama|X}} template → X adalah krama form."""
    # {{krama|X}} or {{krama|X|...}}
    matches = re.findall(r'\{\{krama\|([^|}]+)(?:\|[^}]*)?\}\}', text)
    # Filter out garbage (templates pages, etc)
    cleaned = []
    for m in matches:
        m = m.strip()
        # Skip if it's a parameter like "kelas=" or contains weird chars
        if '=' in m or '<' in m or '>' in m or '{' in m:
            continue
        if len(m) < 1 or len(m) > 80:
            continue
        cleaned.append(m)
    return cleaned[0] if cleaned else None


def extract_ngoko_inggil(text):
    """Cari {{ngoko|X|inggil=Y}} template → krama=X, krama_inggil=Y.
    
    Pattern: {{ngoko|X|inggil=Y}} or {{ngoko|X|...|inggil=Y|...}}
    """
    # Try pattern with inggil=
    m = re.search(r'\{\{ngoko\|([^|}]+)[^}]*?inggil=([^|}]+)[^}]*\}\}', text)
    if m:
        ngoko_val = m.group(1).strip()
        inggil_val = m.group(2).strip()
        # Skip if has weird chars
        if '=' in ngoko_val or '<' in ngoko_val:
            ngoko_val = None
        if '=' in inggil_val or '<' in inggil_val:
            inggil_val = None
        return ngoko_val, inggil_val
    # Try {{ngoko|X}} without inggil
    m = re.search(r'\{\{ngoko\|([^|}]+)(?:\|[^}]*)?\}\}', text)
    if m:
        ngoko_val = m.group(1).strip()
        if '=' in ngoko_val or '<' in ngoko_val:
            return None, None
        return ngoko_val, None
    return None, None


def extract_inggil_standalone(text):
    """Cari inggil=Y dalam template apa pun → krama_inggil=Y."""
    m = re.search(r'inggil=([^|}\s]+)', text)
    if m:
        v = m.group(1).strip()
        if '=' in v or '<' in v:
            return None
        return v
    return None


def main():
    print(f'Reading {XML_PATH} (~30 detik untuk 86MB)...')
    
    pairs = []
    stats = {
        'total_pages': 0,
        'basa_jv_pages': 0,
        'with_krama_template': 0,
        'with_ngoko_template': 0,
        'with_inggil': 0,
        'pairs_extracted': 0,
    }
    
    buf = ''
    with open(XML_PATH, encoding='utf-8') as f:
        for line in f:
            buf += line
            if '</page>' in line:
                stats['total_pages'] += 1
                # Parse page
                ns_m = re.search(r'<ns>([^<]+)</ns>', buf)
                title_m = re.search(r'<title>([^<]+)</title>', buf)
                text_m = re.search(r'<text[^>]*>(.*?)</text>', buf, re.DOTALL)
                if not (ns_m and title_m and text_m):
                    buf = ''
                    continue
                ns = ns_m.group(1).strip()
                title = title_m.group(1).strip()
                text = text_m.group(1)
                
                # Skip non-main-namespace pages (templates, discussions, etc)
                if ns != '0':
                    buf = ''
                    continue
                # Skip pages starting with Cithakan: (templates) or special prefixes
                if title.startswith(('Cithakan:', 'Parembugan:', 'Mirunggan:', 'Barkas:', 'Wikisastra:')):
                    buf = ''
                    continue
                
                # Only pages with {{basa|jv}} (Javanese word)
                if '{{basa|jv}}' not in text:
                    buf = ''
                    continue
                
                stats['basa_jv_pages'] += 1
                
                # Page title = ngoko
                ngoko = title
                
                # Try {{krama|X}} template
                krama = extract_krama(text)
                if krama:
                    stats['with_krama_template'] += 1
                
                # Try {{ngoko|X|inggil=Y}} template
                ngoko_tpl, inggil = extract_ngoko_inggil(text)
                if ngoko_tpl:
                    stats['with_ngoko_template'] += 1
                    # {{ngoko|X}} means X is krama form (page title is ngoko)
                    if not krama:
                        krama = ngoko_tpl
                
                # Try standalone inggil=
                if not inggil:
                    inggil = extract_inggil_standalone(text)
                if inggil:
                    stats['with_inggil'] += 1
                
                # Only save if has krama (the actual ngoko-krama pair)
                if krama:
                    pairs.append({
                        'ngoko': ngoko,
                        'krama': krama,
                        'krama_inggil': inggil,
                    })
                    stats['pairs_extracted'] += 1
                
                buf = ''
                if stats['total_pages'] % 20000 == 0:
                    print(f'  ... {stats["total_pages"]:,} pages, {stats["pairs_extracted"]:,} pairs')
    
    print(f'\n=== Extraction Results ===')
    print(f'Total pages:                  {stats["total_pages"]:,}')
    print(f'Pages with {{{{basa|jv}}}}:        {stats["basa_jv_pages"]:,}')
    print(f'  - with {{{{krama|X}}}} template:  {stats["with_krama_template"]:,}')
    print(f'  - with {{{{ngoko|X}}}} template:  {stats["with_ngoko_template"]:,}')
    print(f'  - with inggil= :             {stats["with_inggil"]:,}')
    print(f'Pairs extracted (with krama): {stats["pairs_extracted"]:,}')
    
    # Sort by ngoko alphabetically
    pairs.sort(key=lambda p: p['ngoko'].lower())
    
    # Save
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'source': 'jvwiktionary-latest.xml',
                'description': 'Ngoko-Krama pairs extracted ONLY from jvwiktionary (Javanese Wiktionary). Page title = ngoko, {{krama|X}} or {{ngoko|X}} = krama form, inggil=Y = krama_inggil.',
                'extracted_at': '2026-10-07',
                'stats': stats,
            },
            'pairs': pairs,
        }, f, ensure_ascii=False, indent=2)
    
    print(f'\n✓ Saved {len(pairs):,} pairs to {OUT_PATH}')
    print(f'\n=== Sample (first 20) ===')
    for p in pairs[:20]:
        print(f'  {p["ngoko"]!r} → krama={p["krama"]!r}' + (f', krama_inggil={p["krama_inggil"]!r}' if p.get('krama_inggil') else ''))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Test kamus v2.3.0 dengan running grammar + split stage pada sample SRT.
Ukur coverage improvement dan verify tidak ada regression.
"""
import sys
import json
import re
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, '/home/z/my-project/dub-jawa')
sys.path.insert(0, '/home/z/my-project/dub-jawa/src')

from stages.grammar import fix_grammar, fix_text, _load_kamus
from stages.split import split_levels

# === Test 1: Coverage improvement ===
print("="*60)
print("TEST 1: Coverage measurement")
print("="*60)

with open('/home/z/my-project/dub-jawa/kamus_jawa.json') as f:
    k = json.load(f)
id2ng = k['typo_corrections']
n2k = k['ngoko_to_krama']
print(f"Kamus v{k['meta']['version']}: {len(id2ng)} typo + {len(n2k)} n2k")

# === Test 2: Grammar fix on small sample ===
print("\n" + "="*60)
print("TEST 2: Grammar fix on first 50 subs of source SRT")
print("="*60)

import pysrt
srt_path = Path('/home/z/my-project/dub-jawa/work/source_video.id.srt')
srt = pysrt.open(srt_path)
print(f"Total subs in source: {len(srt)}")

# Take first 50 subs as sample
sample_subs = list(srt)[:50]
kamus_path = Path('/home/z/my-project/dub-jawa/kamus_jawa.json')
kamus = _load_kamus(kamus_path)
punct_rules = kamus.get('punctuation_rules', {})

print("\nSample grammar fix (first 10 subs):")
for i, sub in enumerate(sample_subs[:10]):
    original = sub.text
    fixed, stats = fix_text(original, kamus['typo_corrections'], punct_rules)
    changes = []
    if stats['typos_fixed']:
        changes.append(f"+{stats['typos_fixed']} typo")
    if stats['punct_added']:
        changes.append("punct")
    if stats['capitalized']:
        changes.append("cap")
    chg_str = ", ".join(changes) if changes else "no change"
    print(f"\n  [{i+1}] {chg_str}")
    print(f"      SRC: {original}")
    print(f"      OUT: {fixed}")

# === Test 3: Full grammar + split on first 200 subs ===
print("\n" + "="*60)
print("TEST 3: Grammar + split on first 200 subs (timing)")
print("="*60)

t0 = time.time()
# Build a small SRT in memory
import io
sample_text = ""
for sub in sample_subs + list(srt)[50:200]:
    sample_text += str(sub) + "\n\n"

# Write to temp file
sample_path = Path('/tmp/sample_test.srt')
sample_path.write_text(sample_text, encoding='utf-8')
print(f"Sample SRT: 200 subs, {sample_path.stat().st_size} bytes")

# Run grammar
from pathlib import Path
work_dir = Path('/tmp/test_work')
work_dir.mkdir(exist_ok=True)
# Copy sample as translated.srt
(work_dir / 'translated.srt').write_text(sample_text, encoding='utf-8')

t1 = time.time()
# Create required subdirs (reports)
(work_dir / 'reports').mkdir(exist_ok=True)
result = fix_grammar(work_dir, kamus_path)
t2 = time.time()
print(f"Grammar fix: {t2-t1:.2f}s, {result.total_typos_fixed} typos fixed in {result.total_subs} subs")

# Run split
t3 = time.time()
output_dir = work_dir / 'output'
output_dir.mkdir(exist_ok=True)
split_result = split_levels(work_dir, output_dir, kamus_path)
t4 = time.time()
print(f"Split: {t4-t3:.2f}s")
print(f"  Ngoko: {output_dir / 'ngoko.srt'}")
print(f"  Krama: {output_dir / 'krama.srt'}")

# Show first 5 lines of each output
print("\n--- Ngoko sample (first 5 subs) ---")
ngoko_srt = pysrt.open(output_dir / 'ngoko.srt')
for i, sub in enumerate(list(ngoko_srt)[:5]):
    print(f"  [{i+1}] {sub.text}")

print("\n--- Krama sample (first 5 subs) ---")
krama_srt = pysrt.open(output_dir / 'krama.srt')
for i, sub in enumerate(list(krama_srt)[:5]):
    print(f"  [{i+1}] {sub.text}")

# === Test 4: Coverage on the 200-sub sample ===
print("\n" + "="*60)
print("TEST 4: Coverage on 200-sub sample (after grammar fix)")
print("="*60)

with open(work_dir / 'grammar_fixed.srt') as f:
    gf = f.read()
text_lines = [l for l in gf.split('\n') if l.strip() and not re.match(r'^\d+$', l.strip()) and '-->' not in l]
text = ' '.join(text_lines).lower()
tokens_raw = re.findall(r"[a-zà-ÿ-]+", text)
tokens = [t for t in tokens_raw if len(t) >= 2 and t.replace('-','').isalpha()]
total = len(tokens)
covered = sum(1 for t in tokens if t in id2ng or t in n2k)
print(f"Total tokens: {total}")
print(f"Covered: {covered} ({covered*100/total:.1f}%)")

# === Test 5: Forbidden pattern check ===
print("\n" + "="*60)
print("TEST 5: Forbidden patterns in output")
print("="*60)
forbidden_patterns = ['_', 'pawpaw', '  ', '..']
issues = []
for p in forbidden_patterns:
    if p in gf:
        issues.append(f"FOUND '{p}' in grammar_fixed output")
if issues:
    print("\n".join(issues))
else:
    print("OK: no forbidden patterns in output")

print("\n" + "="*60)
print("DONE")
print("="*60)

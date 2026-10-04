# Stage 3: Grammar Fix Report

## Summary
- **Total subtitles**: 2877
- **Subs with changes**: 2875 (99.9%)
- **Total typos fixed**: 3
- **Punctuation added**: 2873
- **Capitalized**: 21
- **Whitespace stripped**: 1

## Files
- Input: `work/translated.srt`
- Output: `work/grammar_fixed.srt`

## Sample Diffs (first 5 + last 5 changed)
  - **#1**
    - Before: `ah`
    - After:  `Ah.`
  - **#2**
    - Before: `kowe teko saka ngendi`
    - After:  `Kowe teko saka ngendi?`
  - **#3**
    - Before: `iki ing nagara maneh?`
    - After:  `Iki ing nagara maneh?`
  - **#4**
    - Before: `muncul tanpa jejak`
    - After:  `Muncul tanpa jejak.`
  - **#5**
    - Before: `satoe gerak ngalahaken wong kuwat`
    - After:  `Satoe gerak ngalahaken wong kuwat.`
  - **#2873**
    - Before: `欽此`
    - After:  `欽此.`
  - **#2874**
    - Before: `沒想到三殿下動作挺快`
    - After:  `沒想到三殿下動作挺快.`
  - **#2875**
    - Before: `老爺子`
    - After:  `老爺子.`
  - **#2876**
    - Before: `收拾東西`
    - After:  `收拾東西.`
  - **#2877**
    - Before: `咱們去京城了`
    - After:  `咱們去京城了.`


## Next step
User review: periksa sample di atas. Kalau substitusi typo salah (mis. "yang" diganti
"kang" padahal "yang" memang Jawa yang benar), edit `kamus_jawa.json` di bagian
`typo_corrections` dan jalankan ulang.

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 4 (Split ngoko/krama).

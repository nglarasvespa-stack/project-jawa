# Stage 3: Grammar Fix Report

## Summary
- **Total subtitles**: 5233
- **Subs with changes**: 5210 (99.6%)
- **Total typos fixed**: 16270
- **Punctuation added**: 4759
- **Capitalized**: 832
- **Whitespace stripped**: 150

## Files
- Input: `work/source_video.id.srt`
- Output: `work/grammar_fixed.srt`

## Sample Diffs (first 5 + last 5 changed)
  - **#1**
    - Before: `Masuk dari gerbang barat lebih aman`
    - After:  `Mlebu saka lawang kulon luwih tentrem.`
  - **#2**
    - Before: `Di sana lebih sepi`
    - After:  `Ing kana luwih sepi.`
  - **#3**
    - Before: `Di balik pintu ini adalah halaman samping`
    - After:  `Ing balik lawang iki iku pelataran sisih.`
  - **#4**
    - Before: `Ketuk pintu depannya`
    - After:  `Swara petok lawang ngarepe.`
  - **#5**
    - Before: `Nona`
    - After:  `Ndoro.`
  - **#5229**
    - Before: `Huchen`
    - After:  `Huchen.`
  - **#5230**
    - Before: `Busur silang tangan biasa untuk Baturu`
    - After:  `Gendhewa tumpang-tumpangan mrapat asta lumrah kanggo Baturu.`
  - **#5231**
    - Before: `Bungkus dengan peti`
    - After:  `Bungkus karo peti.`
  - **#5232**
    - Before: `Jangan lupa`
    - After:  `Aja lali.`
  - **#5233**
    - Before: `Bayar dulu hutang budi itu`
    - After:  `Mbayar biyen utang budi iku.`


## Next step
User review: periksa sample di atas. Kalau substitusi typo salah (mis. "yang" diganti
"kang" padahal "yang" memang Jawa yang benar), edit `kamus_jawa.json` di bagian
`typo_corrections` dan jalankan ulang.

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 4 (Split ngoko/krama).

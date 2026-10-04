# Stage 3: Grammar Fix Report

## Summary
- **Total subtitles**: 2831
- **Subs with changes**: 1997 (70.5%)
- **Total typos fixed**: 166
- **Punctuation added**: 1374
- **Capitalized**: 810
- **Whitespace stripped**: 225

## Files
- Input: `work/source_video.jv.srt`
- Output: `work/grammar_fixed.srt`

## Sample Diffs (first 5 + last 5 changed)
  - **#3**
    - Before: `Muncul saka awang-awang,`
    - After:  `Muncul saka awang-awang.`
  - **#4**
    - Before: `ngalahake
ahli Body Tempering Realm tahap pungkasan mung nganggo siji gerakan,`
    - After:  `Ngalahake ahli Body Tempering Realm tahap pungkasan mung nganggo siji gerakan.`
  - **#5**
    - Before: `apa iki bisa dadi master kultivasi sing nyendiri?`
    - After:  `Apa iki saged dadi master kultivasi sing nyendiri?`
  - **#6**
    - Before: `Kowé—`
    - After:  `Kowé—.`
  - **#8**
    - Before: `Aku ora ngakoni kaluhuranmu`
    - After:  `Aku ora ngakoni kaluhuranmu.`
  - **#2826**
    - Before: `Prentahake Song Yi supaya nggawa keluargane menyang
ibukutha kanggo ketemu langsung.`
    - After:  `Prentahake Song Yi supaya nggawa keluargane menyang ibukutha kanggo ketemu langsung.`
  - **#2827**
    - Before: `Miturut dekrit kekaisaran`
    - After:  `Miturut dekrit kekaisaran.`
  - **#2829**
    - Before: `Wong tuwa,`
    - After:  `Wong tuwa.`
  - **#2830**
    - Before: `kemasi barang-barangmu,`
    - After:  `Kemasi barang-barangmu.`
  - **#2831**
    - Before: `kita arep menyang ibukutha.`
    - After:  `Kita arep menyang ibukutha.`


## Next step
User review: periksa sample di atas. Kalau substitusi typo salah (mis. "yang" diganti
"kang" padahal "yang" memang Jawa yang benar), edit `kamus_jawa.json` di bagian
`typo_corrections` dan jalankan ulang.

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 4 (Split ngoko/krama).

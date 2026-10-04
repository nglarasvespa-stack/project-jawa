# Stage 2: Translate Report

## Summary
- **Source language**: `zh-Hant`
- **Total subtitles**: 2877
- **Total batches**: 3
- **Successful batches**: 3 (100.0%)
- **Failed batches**: 0
- **Elapsed time**: 14.1s (0.2m)

## Files
- Input: `work/source_video.zh-Hant.srt`
- Output: `work/translated.srt`

## Failed Translations
- Failed indices: (none)

## Sample Before/After
  - **#1**
    - Before: `啊`
    - After:  `ah`
  - **#2**
    - Before: `給我幹哪來了`
    - After:  `kowe teko saka ngendi`
  - **#3**
    - Before: `這還是國內嗎`
    - After:  `iki ing nagara maneh?`
  - **#4**
    - Before: `憑空出現`
    - After:  `muncul tanpa jejak`
  - **#5**
    - Before: `一招制服鍛體境後期`
    - After:  `satoe gerak ngalahaken wong kuwat`
  - **#46**
    - Before: `那豈不是遍地都是`
    - After:  `Apa ora kabeh ana`
  - **#47**
    - Before: `好幾個幾十萬`
    - After:  `Puluhan ewu`
  - **#48**
    - Before: `大仙`
    - After:  `Dewa`
  - **#49**
    - Before: `天色不早`
    - After:  `Wanci wis mbengi`
  - **#50**
    - Before: `我得趕緊下山了`
    - After:  `Kudu turun gunung cepet`


## Next step
User review: apakah terjemahan masuk akal? Kalau banyak yang gagal, coba:
  - Kecilkan batch_size (default 20 -> 10) di config.json
  - Atur limit untuk testing subset

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 3 (Grammar fix).

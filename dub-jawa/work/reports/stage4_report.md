# Stage 4: Split ngoko/krama Report

## Summary
- **Total subtitles**: 2831
- **Ngoko substitutions**: 849 (di 718 subs)
- **Krama substitutions**: 4757 (di 2112 subs)

## Files
- Input: `work/grammar_fixed.srt`
- Output ngoko: `output/ngoko.srt`
- Output krama: `output/krama.srt`

## Sample Diffs (first 5 with changes)
  - **#1**
    - Original: `Aku iki tekan ngendi?`
    - Ngoko:    `Aku iki tekan ngendi?`
    - Krama:    `Kula punika tekan pundi?`
  - **#2**
    - Original: `Apa iki isih negara kita?`
    - Ngoko:    `Apa iki isih negara kita?`
    - Krama:    `Menapa punika masih negara kita?`
  - **#4**
    - Original: `Ngalahake ahli Body Tempering Realm tahap pungkasan mung nganggo siji gerakan.`
    - Ngoko:    `Ngalahake ahli Body Tempering Realm tahap pungkasan mung nganggo siji gerakan.`
    - Krama:    `Ngalahake ahli Body Tempering Realm tahap pungkasan namung ngginakaken setunggal gerakan.`
  - **#5**
    - Original: `Apa iki saged dadi master kultivasi sing nyendiri?`
    - Ngoko:    `Apa iki bisa dadi master kultivasi sing nyendiri?`
    - Krama:    `Menapa punika saged dados master kultivasi ingkang nyendiri?`
  - **#6**
    - Original: `Kowé—.`
    - Ngoko:    `Ko—.`
    - Krama:    `Kowé—.`


## Limitasi dictionary-only
- Hanya kata yang ada di `kamus_jawa.json["ngoko_to_krama"]` yang bisa di-substitusi.
- Kata dengan imbuhan, dwilingga, atau bentuk elision tidak ditangkap.
- Untuk kualitas tinggi, bisa upgrade ke LLM-based split (Tahap 5+).

## Next step
User review: cek sample di atas. Kalau substitusi terlalu sedikit, edit `kamus_jawa.json`
tambah lebih banyak entry ngoko<->krama. Kalau sudah OK, lanjut ke Stage 5 (TTS).

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 5 (TTS - edge-tts Dimas/Siti).

# Stage 4: Split ngoko/krama Report

## Summary
- **Total subtitles**: 2877
- **Ngoko substitutions**: 8 (di 6 subs)
- **Krama substitutions**: 54 (di 33 subs)

## Files
- Input: `work/grammar_fixed.srt`
- Output ngoko: `output/ngoko.srt`
- Output krama: `output/krama.srt`

## Sample Diffs (first 5 with changes)
  - **#2**
    - Original: `Kowe teko saka ngendi?`
    - Ngoko:    `Kowe teko saka ngendi?`
    - Krama:    `Panjenengan teko saka pundi?`
  - **#3**
    - Original: `Iki ing nagara maneh?`
    - Ngoko:    `Iki ing nagara maneh?`
    - Krama:    `Punika ing nagara malih?`
  - **#5**
    - Original: `Satoe gerak ngalahaken wong kuwat.`
    - Ngoko:    `Satoe gerak ngalahaken wong kuwat.`
    - Krama:    `Satoe gerak ngalahaken wong kukuwat.`
  - **#7**
    - Original: `Kowe.`
    - Ngoko:    `Kowe.`
    - Krama:    `Panjenengan.`
  - **#9**
    - Original: `Aku ora ngerti kawasa sampeyan.`
    - Ngoko:    `Aku ora ngerti kawasa sampeyan.`
    - Krama:    `Kula boten sumerep kawasa sampeyan.`


## Limitasi dictionary-only
- Hanya kata yang ada di `kamus_jawa.json["ngoko_to_krama"]` yang bisa di-substitusi.
- Kata dengan imbuhan, dwilingga, atau bentuk elision tidak ditangkap.
- Untuk kualitas tinggi, bisa upgrade ke LLM-based split (Tahap 5+).

## Next step
User review: cek sample di atas. Kalau substitusi terlalu sedikit, edit `kamus_jawa.json`
tambah lebih banyak entry ngoko<->krama. Kalau sudah OK, lanjut ke Stage 5 (TTS).

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 5 (TTS - edge-tts Dimas/Siti).

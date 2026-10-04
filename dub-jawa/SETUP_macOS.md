# Setup Dub-Jawa di macOS (MacBook Pro M1/M2/M3)

Panduan lengkap untuk menjalankan dub-jawa di MacBook lokal. Project ini dikembangkan
di sandbox z.ai, tapi bisa dijalankan di Mac dengan beberapa penyesuaian.

## Prerequisites

| Yang dibutuhkan | Cara cek | Install kalau belum |
|-----------------|----------|---------------------|
| macOS 12+ | `sw_vers` | (sudah ada) |
| Python 3.10+ | `python3 --version` | `brew install python@3.12` |
| Homebrew | `brew --version` | https://brew.sh |
| ffmpeg | `ffmpeg -version` | `brew install ffmpeg` |
| 4GB free disk | `df -h ~` | (untuk video + audio output) |

### 1. Download & Extract

```bash
# Download file dub-jawa.tar.gz dari sandbox (lihat chat untuk link)
# Simpan ke folder proyek, misal ~/Projects

mkdir -p ~/Projects
cd ~/Projects
tar -xzf ~/Downloads/dub-jawa.tar.gz
cd dub-jawa
```

### 2. Buat Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
# prompt shell akan berubah jadi (.venv)
```

Untuk aktivasi otomatis tiap buka terminal baru:
```bash
echo 'source ~/Projects/dub-jawa/.venv/bin/activate' >> ~/.zshrc
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Setelah install, verifikasi semua jalan:
```bash
python main.py --list-voices
# harusnya muncul 6 voice: jv-ID-DimasNeural, jv-ID-SitiNeural,
# id-ID-ArdiNeural, id-ID-GadisNeural, su-ID-JajangNeural, su-ID-TutiNeural
```

Kalau muncul error, coba:
```bash
# install ulang edge-tts manual
pip install edge-tts --upgrade
```

### 4. Test Pipeline (3 stage pertama, tanpa LLM)

```bash
# Stage 1 - pakai SRT yang sudah ada (downsub.com)
python main.py --srt "/path/ke/file.srt"

# Stage 3 - grammar fix (instant, no LLM)
python main.py --grammar

# Stage 4 - split ngoko/krama (instant, no LLM)
python main.py --split
```

Cek output:
```bash
ls -la output/
# ngoko.srt + krama.srt harusnya ada
```

### 5. Mode TUI (interactive)

```bash
python main.py
```

Hotkeys:
- `Ctrl+→` / `Ctrl+←` : pindah antar tab stage
- `Tab` / `Shift+Tab` : pindah fokus antar widget
- `Enter` : trigger tombol aktif
- `Y` : approve stage terakhir
- `N` : reject stage
- `E` : edit file (info.json / kamus_jawa.json)
- `q` : quit

---

## ⚠️ Limitasi: Stage 2 (Translate) di Mac

Stage 2 (Translate) pakai `z-ai chat` CLI yang **hanya tersedia di sandbox z.ai**,
TIDAK tersedia di Mac. Untuk pakai Stage 2 di Mac, ada 3 opsi:

### Opsi A: Install Ollama (gratis, lokal, recommended)

```bash
# install Ollama dari https://ollama.com (download .dmg)
# atau via brew:
brew install ollama
ollama serve &  # start daemon di background

# download model Javanese-capable (~5GB)
ollama pull qwen2.5:7b
# atau model lebih besar kalau RAM cukup:
# ollama pull qwen2.5:14b
```

**Saya akan modify `src/stages/translate.py` supaya support Ollama**
sebagai alternatif provider LLM di iterasi berikutnya.

### Opsi B: Pakai OpenAI API (berbayar, kualitas tinggi)

```bash
pip install openai
export OPENAI_API_KEY="sk-..."
```

Model yang bagus untuk Jawa: `gpt-4o-mini` (murah) atau `gpt-4o` (kualitas tinggi).
**Saya akan tambah opsi OpenAI di translate.py**.

### Opsi C: Pakai Anthropic Claude API (berbayar, sangat bagus untuk Jawa)

```bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

Claude Haiku/Sonnet bagus untuk Jawa.
**Saya akan tambah opsi Claude**.

### Opsi D: Skip Stage 2, translate manual

Kalau kamu cuma mau coba pipeline stage 3+ (grammar fix, split, TTS):
1. Siapkan `work/translated.srt` secara manual (translate sendiri, atau pakai
   Google Translate untuk draft kasar)
2. Lanjut `python main.py --grammar` lalu `--split`

---

## Folder Penting di Mac Kamu

```
~/Projects/dub-jawa/
├── main.py                  # entry point
├── config.json              # setting (voice, cookies, dll)
├── kamus_jawa.json          # 430 entries (bisa di-expand)
├── requirements.txt
├── src/
│   ├── tui_app.py           # TUI textual
│   ├── reviewer.py
│   └── stages/
│       ├── fetch.py         # stage 1 (yt-dlp)
│       ├── detect.py        # auto-detect bahasa
│       ├── translate.py     # stage 2 (LLM, butuh provider alternatif di Mac)
│       ├── grammar.py       # stage 3 (instant, no LLM)
│       └── split.py         # stage 4 (instant, no LLM)
├── work/                    # file kerja per stage (auto-created)
│   ├── info.json
│   ├── source_video.zh-Hant.srt
│   ├── translated.srt       # hasil stage 2
│   ├── grammar_fixed.srt   # hasil stage 3
│   └── reports/             # laporan markdown per stage
└── output/                  # final deliverables
    ├── ngoko.srt
    └── krama.srt
```

## Troubleshooting Mac-specific

### Error: "z-ai: command not found"
Ini wajar - `z-ai` CLI hanya di sandbox. Lihat "Limitasi Stage 2" di atas.

### Error: "edge-tts: command not found"
Install via pip: `pip install edge-tts`. Kalau masih gagal, coba
`pip install --user edge-tts`.

### Error: "yt-dlp: command not found"
Sama: `pip install yt-dlp`.

### YouTube minta sign-in (bot detection)
Edit `config.json`, set `cookies_from_browser` ke browser tempat kamu login
YouTube di Mac:
```json
"cookies_from_browser": "safari"  // atau "chrome" / "firefox" / "brave"
```

### TUI tidak muncul / blank
Pastikan terminal support VT100/color. Pakai Terminal.app bawaan Mac atau
iTerm2. Kalau via SSH, pakai `TERM=xterm-256color python main.py`.

### Performance lambat
Untuk MacBook Pro M1 16GB, seharusnya lancar. Kalau translate (Stage 2)
lambat, kurangi `--batch-size 10` atau pakai model yang lebih kecil (kalau
pakai Ollama).

---

## Selanjutnya?

Setelah setup jalan, langkah saya selanjutnya (kalau kamu mau):
1. **Tambah provider LLM alternatif** (Ollama / OpenAI / Claude) di
   `src/stages/translate.py` supaya Stage 2 jalan di Mac.
2. **Stage 5 (TTS)** dengan edge-tts voice Dimas/Siti.
3. **Expand kamus** lebih jauh (~1000+ entries) dari sumber resmi.

Konfirmasi kalau mau salah satu dikerjakan duluan.

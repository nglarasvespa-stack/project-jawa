# Dub-Jawa

TUI Python ringan untuk dubbing film/drama internasional ke **Bahasa Jawa** (versi ngoko + krama), dengan **review gate** tiap stage dan **Edge-TTS** untuk audio.

## Status
- **Tahap 1** (saat ini): Stage 1 Fetch berfungsi, TUI 6-tab jalan, voice Jawa terdeteksi.
- Tahap 2: Stage 2 Translate (LLM GLM)
- Tahap 3: Stage 3 Grammar fix (kamus JSON)
- Tahap 4: Stage 4 Split ngoko/krama
- Tahap 5: Stage 5 TTS + output

## Install
```bash
cd /home/z/my-project/dub-jawa
pip install -r requirements.txt
```

## Jalankan
```bash
# mode TUI (default)
python main.py

# CLI mode: langsung fetch tanpa TUI
python main.py --fetch https://www.youtube.com/watch?v=XXXX

# list voice Edge-TTS untuk jv/id/su
python main.py --list-voices
```

## Hotkeys TUI
| Key | Aksi |
|-----|------|
| `Ctrl+→` / `Ctrl+←` | pindah antar tab stage |
| `Tab` / `Shift+Tab` | pindah fokus antar widget |
| `Enter` | mulai fetch (di tab Fetch) |
| `Y` | approve stage terakhir |
| `N` | reject stage |
| `E` | buka info.json di $EDITOR |
| `q` | quit |

## Voice tersedia
| Bahasa | Male | Female |
|---|---|---|
| Jawa (`jv-ID`) | `jv-ID-DimasNeural` | `jv-ID-SitiNeural` |
| Indonesia (`id-ID`) | `id-ID-ArdiNeural` | `id-ID-GadisNeural` |
| Sunda (`su-ID`) | `su-ID-JajangNeural` | `su-ID-TutiNeural` |

## Output final (setelah semua stage)
```
output/
├── ngoko.srt          # subtitle ngoko
├── ngoko.wav          # audio ngoko (edge-tts Dimas)
├── krama.srt          # subtitle krama
├── krama.wav          # audio krama (edge-tts Siti)
└── source_video.mp4   # video asli (untuk user mux sendiri)
```

User lalu mux sendiri di editor video (Premiere/CapCut/DaVinci/Resolve).

## Struktur project
```
dub-jawa/
├── main.py              # entry point
├── config.json          # setting: voice, format, preferensi bahasa
├── kamus_jawa.json      # kamus ngoko<->krama (sample, ganti untuk produksi)
├── requirements.txt
├── src/
│   ├── tui_app.py       # TUI textual 6-tab
│   ├── reviewer.py      # diff + report + approval gate
│   └── stages/
│       └── fetch.py     # stage 1 (yt-dlp)
├── work/                # file kerja per stage (auto-created)
└── output/              # final deliverables (auto-created)
```

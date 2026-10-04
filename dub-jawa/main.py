#!/usr/bin/env python3
"""Dub-Jawa: TUI app untuk dubbing multi-bahasa ke Jawa (ngoko + krama).

Usage:
    python main.py                # jalankan TUI
    python main.py --fetch URL    # CLI mode: langsung fetch tanpa TUI

Tahap 1 (saat ini):
  - Stage 1 (Fetch) berfungsi
  - Stage 2-5: placeholder, akan diimplement di Tahap berikutnya
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def cmd_tui() -> int:
    from src.tui_app import run as run_tui
    run_tui()
    return 0


def cmd_fetch(url: str) -> int:
    from src.stages.fetch import fetch_video
    work_dir = Path("work")
    print(f"[+] Fetching: {url}")
    r = fetch_video(
        url,
        work_dir,
        progress_callback=lambda d: print(
            f"  {d.get('status','?')} {d.get('_percent_str','').strip()}",
            end="\r",
            flush=True,
        ),
    )
    print()
    print(f"[+] Title: {r.title}")
    print(f"[+] Duration: {r.duration_sec}s")
    print(f"[+] Video: {r.video_path}")
    print(f"[+] SRT: {r.srt_path} ({r.subtitle_lang})")
    print(f"[+] Available subs: {', '.join(r.available_subs)}")
    return 0


def cmd_list_voices() -> int:
    """List voice Edge-TTS yang tersedia untuk jv/id/su."""
    import subprocess
    result = subprocess.run(
        ["edge-tts", "--list-voices"], capture_output=True, text=True, check=True
    )
    print("Voices Edge-TTS (jv/id/su):")
    for line in result.stdout.splitlines():
        if line.startswith(("jv-", "id-", "su-")) or line.startswith(("jv-ID", "id-ID", "su-ID")):
            print(f"  {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dub-Jawa: TUI untuk dubbing multi-bahasa -> Jawa (ngoko + krama)"
    )
    parser.add_argument("--fetch", metavar="URL", help="CLI mode: langsung fetch URL tanpa TUI")
    parser.add_argument("--list-voices", action="store_true", help="List voice Edge-TTS jv/id/su")
    parser.add_argument("--tui", action="store_true", help="Jalankan TUI (default)")
    args = parser.parse_args()

    if args.list_voices:
        return cmd_list_voices()
    if args.fetch:
        return cmd_fetch(args.fetch)
    # default: TUI
    return cmd_tui()


if __name__ == "__main__":
    sys.exit(main())

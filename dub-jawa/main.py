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
from typing import Optional


def cmd_tui() -> int:
    from src.tui_app import run as run_tui
    run_tui()
    return 0


def cmd_fetch(url: str, srt_path: Optional[str] = None) -> int:
    from src.stages.fetch import fetch_video
    work_dir = Path("work")

    # tentukan mode
    if srt_path and not url:
        print(f"[+] Mode 3: SRT only - {srt_path}")
        srt = Path(srt_path)
    elif srt_path and url:
        print(f"[+] Mode 2: URL + local SRT - {url} + {srt_path}")
        srt = Path(srt_path)
    else:
        print(f"[+] Mode 1: URL only - {url}")
        srt = None

    # read cookies from config
    import json
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    cookies = config.get("cookies_from_browser")

    def progress(d):
        status = d.get("status")
        if status == "downloading":
            print(f"  ... {d.get('_percent_str','').strip()} {d.get('_speed_str','').strip()} eta {d.get('_eta_str','').strip()}", end="\r", flush=True)
        elif status == "finished":
            print(f"  [done] {d.get('filename','')}")

    try:
        r = fetch_video(
            url,
            work_dir,
            progress_callback=progress,
            cookies_from_browser=cookies,
            local_srt_path=srt,
        )
    except Exception as e:
        print(f"[!] ERROR: {e}")
        return 1

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
    parser.add_argument("--srt", metavar="PATH", help="Path SRT lokal (downsub.com). Pakai dengan --fetch, atau sendiri untuk mode SRT-only")
    parser.add_argument("--list-voices", action="store_true", help="List voice Edge-TTS jv/id/su")
    parser.add_argument("--tui", action="store_true", help="Jalankan TUI (default)")
    args = parser.parse_args()

    if args.list_voices:
        return cmd_list_voices()
    if args.fetch or args.srt:
        return cmd_fetch(args.fetch or "", args.srt)
    # default: TUI
    return cmd_tui()


if __name__ == "__main__":
    sys.exit(main())

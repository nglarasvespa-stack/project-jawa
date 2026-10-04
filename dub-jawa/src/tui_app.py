"""TUI Dub-Jawa - Terminal User Interface dengan tab navigation.

Hotkeys:
  Tab / Shift+Tab      : pindah fokus antar widget
  Ctrl+Tab / Ctrl+Shift+Tab : pindah antar tab stage
  q                    : keluar
  Enter di input URL   : mulai fetch
  Y                    : approve stage terakhir (jika ada)
  N                    : reject, balik ke stage sebelumnya
  E                    : edit file kerja manual (buka $EDITOR)

Layout:
  +------------------------------------------+
  | Header: Dub-Jawa v0.1                    |
  +------------------------------------------+
  | [1.Fetch][2.Translate][3.Grammar][...]   |  <- tab stage
  +------------------------------------------+
  | Stage 1: Fetch YouTube                   |
  | URL: [_____________________________]     |
  | [Fetch] [Approve(Y)] [Reject(N)] [Edit]  |
  |                                          |
  | Log:                                     |
  |  > Downloading...                        |
  |  > Done. Duration: 45m 12s               |
  |                                          |
  | Report:                                  |
  |  - Title: ...                            |
  +------------------------------------------+
  | Footer: q Quit | Ctrl+Tab pindah tab     |
  +------------------------------------------+
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Static,
    TabbedContent,
    TabPane,
    MarkdownViewer,
)
from textual.reactive import reactive


# Project root (file ini ada di src/)
ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = ROOT / "work"
OUTPUT_DIR = ROOT / "output"
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


CONFIG = load_config()


class StagePane(Vertical):
    """Base class untuk pane tiap stage. Subclass harus implement compose()."""

    def __init__(self, stage_id: str, stage_name: str):
        super().__init__()
        self.stage_id = stage_id
        self.stage_name = stage_name

    def compose(self) -> ComposeResult:
        yield Static(f"Stage {self.stage_id}: {self.stage_name}", classes="stage-title")
        yield Static("(coming soon)", classes="stage-placeholder")


class FetchPane(StagePane):
    """Stage 1: Fetch YouTube video + SRT (atau SRT lokal)."""

    def __init__(self):
        super().__init__("1", "Fetch YouTube")

    def compose(self) -> ComposeResult:
        yield Static("Stage 1: Fetch Video + Subtitle", classes="stage-title")
        yield Static(
            "3 mode input:\n"
            "  1. URL saja -> yt-dlp download video + subtitle\n"
            "  2. URL + SRT lokal -> yt-dlp download video saja, subtitle dari lokal\n"
            "  3. SRT lokal saja -> skip video, untuk testing stage 2+\n"
            "Mode 3 paling cepat untuk coba pipeline tanpa download video besar.",
            classes="hint",
        )
        yield Horizontal(
            Label("URL:", classes="field-label"),
            Input(placeholder="(opsional) https://www.youtube.com/watch?v=...", id="yt-url"),
            classes="row",
        )
        yield Horizontal(
            Label("SRT:", classes="field-label"),
            Input(placeholder="(opsional) /path/ke/file.srt dari downsub.com", id="srt-path"),
            classes="row",
        )
        yield Horizontal(
            Button("Fetch / Load", id="fetch-btn", variant="primary"),
            Button("Approve (Y)", id="approve-btn", variant="success"),
            Button("Reject (N)", id="reject-btn", variant="error"),
            Button("Edit info.json", id="edit-btn", variant="default"),
            classes="row",
        )
        yield Label("Log:")
        yield Log(id="fetch-log", max_lines=200, classes="log")
        yield Label("Report:")
        yield Static(id="fetch-report", classes="report-box")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fetch-btn":
            asyncio.run(self._do_fetch())
        elif event.button.id == "approve-btn":
            self._approve()
        elif event.button.id == "reject-btn":
            self._reject()
        elif event.button.id == "edit-btn":
            self._edit_info()

    async def _do_fetch(self) -> None:
        url_input = self.query_one("#yt-url", Input)
        srt_input = self.query_one("#srt-path", Input)
        log_widget = self.query_one("#fetch-log", Log)
        url = url_input.value.strip()
        srt_path_str = srt_input.value.strip()

        if not url and not srt_path_str:
            log_widget.write_line("[!] Isi minimal salah satu: URL atau path SRT.")
            return

        # deteksi mode
        if srt_path_str and not url:
            mode = "3 (SRT only)"
        elif srt_path_str and url:
            mode = "2 (URL + local SRT)"
        else:
            mode = "1 (URL only - yt-dlp)"

        if url and "youtube.com" not in url and "youtu.be" not in url:
            log_widget.write_line("[!] URL tidak valid (harus youtube.com atau youtu.be).")
            return

        srt_path = Path(srt_path_str) if srt_path_str else None
        if srt_path and not srt_path.exists():
            log_widget.write_line(f"[!] File SRT tidak ditemukan: {srt_path}")
            return

        log_widget.write_line(f"[+] Mode: {mode}")
        if url:
            log_widget.write_line(f"    URL: {url}")
        if srt_path:
            log_widget.write_line(f"    SRT: {srt_path}")

        cookies = CONFIG.get("cookies_from_browser")
        if cookies and url:
            log_widget.write_line(f"    (pakai cookies dari browser: {cookies})")

        import threading

        def _run():
            from src.stages.fetch import fetch_video
            try:
                def cb(d):
                    status = d.get("status")
                    if status == "downloading":
                        pct = d.get("_percent_str", "").strip()
                        speed = d.get("_speed_str", "").strip()
                        eta = d.get("_eta_str", "").strip()
                        log_widget.write_line(f"  ... {pct} {speed} eta {eta}")
                    elif status == "finished":
                        log_widget.write_line(f"  [done] {d.get('filename','')}")

                result = fetch_video(
                    url,
                    WORK_DIR,
                    progress_callback=cb,
                    cookies_from_browser=cookies,
                    local_srt_path=srt_path,
                )
                log_widget.write_line(f"[+] Title: {result.title}")
                log_widget.write_line(f"[+] Duration: {result.duration_sec}s")
                log_widget.write_line(f"[+] Video: {result.video_path}")
                log_widget.write_line(f"[+] SRT:   {result.srt_path} ({result.subtitle_lang})")
                log_widget.write_line("[+] Available subs: " + ", ".join(result.available_subs))

                # tampilkan report
                report_path = WORK_DIR / "reports" / "stage1_report.md"
                if report_path.exists():
                    self.query_one("#fetch-report", Static).update(
                        report_path.read_text(encoding="utf-8")
                    )
            except Exception as e:
                log_widget.write_line(f"[!] ERROR: {e}")
                err_msg = str(e)
                if "Sign in to confirm" in err_msg or "cookies" in err_msg.lower():
                    log_widget.write_line(
                        "[i] YouTube minta sign-in. Edit config.json, "
                        "set 'cookies_from_browser' ke 'chrome' atau 'firefox' "
                        "(browser tempat kamu login YouTube). Atau gunakan mode 3 (SRT only)."
                    )

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _approve(self) -> None:
        log = self.query_one("#fetch-log", Log)
        log.write_line("[Y] Stage 1 approved. Lanjut ke Stage 2 (Translate) - belum diimplement.")
        # TODO: unlock tab 2

    def _reject(self) -> None:
        log = self.query_one("#fetch-log", Log)
        log.write_line("[N] Stage 1 ditolak. Perbaiki URL / setting lalu ulang fetch.")

    def _edit_info(self) -> None:
        info_path = WORK_DIR / "info.json"
        if not info_path.exists():
            self.query_one("#fetch-log", Log).write_line("[!] info.json belum ada. Fetch dulu.")
            return
        editor = os.environ.get("EDITOR", "nano")
        try:
            subprocess.run([editor, str(info_path)], check=False)
        except Exception as e:
            self.query_one("#fetch-log", Log).write_line(f"[!] Tidak bisa buka editor: {e}")


class TranslatePane(StagePane):
    def __init__(self):
        super().__init__("2", "Translate to Jawa")
    def compose(self) -> ComposeResult:
        yield Static("Stage 2: Translate SRT (auto-detect source lang -> Jawa standar)", classes="stage-title")
        yield Static("Coming in Tahap 2. Akan pakai LLM (GLM) untuk translate multi-source.", classes="stage-placeholder")


class GrammarPane(StagePane):
    def __init__(self):
        super().__init__("3", "Grammar Fix")
    def compose(self) -> ComposeResult:
        yield Static("Stage 3: Fix typo, tata bahasa, tanda baca (kamus JSON + pysrt)", classes="stage-title")
        yield Static("Coming in Tahap 3.", classes="stage-placeholder")


class SplitPane(StagePane):
    def __init__(self):
        super().__init__("4", "Split ngoko/krama")
    def compose(self) -> ComposeResult:
        yield Static("Stage 4: Pisahkan jadi 2 file - ngoko.srt + krama.srt", classes="stage-title")
        yield Static("Coming in Tahap 4.", classes="stage-placeholder")


class TTSPane(StagePane):
    def __init__(self):
        super().__init__("5", "Generate Audio (Edge-TTS)")
    def compose(self) -> ComposeResult:
        yield Static("Stage 5: Edge-TTS untuk ngoko + krama (voice: Dimas/Siti)", classes="stage-title")
        yield Static("Coming in Tahap 5.", classes="stage-placeholder")
        # tampilkan daftar voice yang tersedia
        voices_md = "**Voices terdeteksi (dari config.json):**\n"
        for key, val in CONFIG.get("voices", {}).items():
            voices_md += f"- `{key}`: `{val}`\n"
        yield Static(voices_md, classes="hint")


class DonePane(StagePane):
    def __init__(self):
        super().__init__("6", "Output")
    def compose(self) -> ComposeResult:
        yield Static("Stage 6: Final output files", classes="stage-title")
        yield Static(
            "Output yang dihasilkan (setelah semua stage):\n"
            "- output/ngoko.srt\n"
            "- output/ngoko.wav\n"
            "- output/krama.srt\n"
            "- output/krama.wav\n"
            "- output/source_video.mp4\n\n"
            "User lalu mux sendiri di editor video (Premiere/CapCut/DaVinci).",
            classes="hint",
        )


class DubJawaApp(App):
    """Main TUI app untuk dub-jawa."""

    CSS = """
    Screen {
        background: $surface;
    }
    .stage-title {
        text-style: bold;
        color: $text;
        padding: 0 0 1 0;
    }
    .stage-placeholder {
        color: $text-muted;
        padding: 1 0;
    }
    .hint {
        color: $text-muted;
        padding: 0 0 1 0;
    }
    .row {
        layout: horizontal;
        height: auto;
        padding: 0 0 1 0;
    }
    .field-label {
        width: 8;
        height: 3;
        padding: 1 1 0 0;
    }
    .log {
        height: 12;
        border: solid $primary;
        padding: 0 1;
    }
    .report-box {
        border: solid $accent;
        padding: 0 1;
        max-height: 20;
        overflow: auto;
    }
    TabbedContent {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+right", "next_tab", "Next stage"),
        Binding("ctrl+left", "prev_tab", "Prev stage"),
        Binding("y", "approve", "Approve"),
        Binding("n", "reject", "Reject"),
        Binding("e", "edit_current", "Edit file"),
    ]

    TITLE = "Dub-Jawa"
    SUB_TITLE = f"v0.1 - Jawa Dubbing Pipeline"

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("1. Fetch", id="fetch-tab"):
                yield FetchPane()
            with TabPane("2. Translate", id="translate-tab"):
                yield TranslatePane()
            with TabPane("3. Grammar", id="grammar-tab"):
                yield GrammarPane()
            with TabPane("4. Split", id="split-tab"):
                yield SplitPane()
            with TabPane("5. TTS", id="tts-tab"):
                yield TTSPane()
            with TabPane("6. Done", id="done-tab"):
                yield DonePane()
        yield Footer()

    def action_next_tab(self) -> None:
        tc = self.query_one(TabbedContent)
        tc.next_tab()

    def action_prev_tab(self) -> None:
        tc = self.query_one(TabbedContent)
        tc.previous_tab()

    def action_approve(self) -> None:
        # cari pane aktif, panggil _approve kalau ada
        active = self._active_pane()
        if active and hasattr(active, "_approve"):
            active._approve()

    def action_reject(self) -> None:
        active = self._active_pane()
        if active and hasattr(active, "_reject"):
            active._reject()

    def action_edit_current(self) -> None:
        active = self._active_pane()
        if active and hasattr(active, "_edit_info"):
            active._edit_info()

    def _active_pane(self):
        tc = self.query_one(TabbedContent)
        active_id = tc.active
        if not active_id:
            return None
        # tab pane = parent dari stage pane
        try:
            tab_pane = self.query_one(f"#{active_id}", TabPane)
            # anak pertama biasanya stage pane
            for child in tab_pane.children:
                if isinstance(child, StagePane):
                    return child
        except Exception:
            return None
        return None


def run() -> None:
    """Entry point: jalankan TUI."""
    app = DubJawaApp()
    app.run()


if __name__ == "__main__":
    run()

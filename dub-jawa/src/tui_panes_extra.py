"""TUI Panes Extra - 3 pane tambahan untuk Dub-Jawa TUI.

Panenya:
  - ReviewPane     : Tab 7 - Inline subtitle editor (edit ngoko/krama per sub)
  - UncoveredPane  : Tab 8 - Uncovered words + tambah ke kamus
  - KamusStatsPane : Tab 9 - Kamus stats + coverage analysis

Dipisah dari tui_app.py untuk maintainability (file induk sudah 670+ baris).
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Optional

import pysrt
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    Log,
    Static,
    ListView,
    ListItem,
)

# Project paths
ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = ROOT / "work"
OUTPUT_DIR = ROOT / "output"
KAMUS_PATH = ROOT / "kamus_jawa.json"


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _load_kamus() -> dict:
    if not KAMUS_PATH.exists():
        return {"typo_corrections": {}, "ngoko_to_krama": {}, "meta": {}}
    return json.loads(KAMUS_PATH.read_text(encoding="utf-8"))


# ============================================================================
# Pane 7: Review (Inline Subtitle Editor)
# ============================================================================
class ReviewPane(Vertical):
    """Tab 7: Inline subtitle editor.

    User bisa navigasi per-subtitle, lihat Indonesian source + Ngoko + Krama,
    edit ngoko/krama langsung di TUI, save back ke .srt.
    """

    PAGE_SIZE = 25  # 25 subs per page (keeps UI responsive)

    def __init__(self):
        super().__init__()
        self.current_page = 0
        self.ngoko_subs: list[pysrt.SubItem] = []
        self.krama_subs: list[pysrt.SubItem] = []
        self.source_subs: list[pysrt.SubItem] = []
        self.selected_idx: int = 0  # index global, bukan per-page

    def compose(self) -> ComposeResult:
        yield Static("Tab 7: Inline Subtitle Editor", classes="stage-title")
        yield Static(
            "Navigasi per-subtitle, edit teks ngoko + krama langsung di TUI. "
            "Save menulis perubahan kembali ke output/ngoko.srt & output/krama.srt. "
            f"Pagination: {self.PAGE_SIZE} subs per page.",
            classes="hint",
        )
        yield Horizontal(
            Button("Load SRT", id="rv-load-btn", variant="primary"),
            Button("Prev Page", id="rv-prev-btn", variant="default"),
            Button("Next Page", id="rv-next-btn", variant="default"),
            Button("Save All", id="rv-save-btn", variant="success"),
            classes="row",
        )
        yield Static(id="rv-page-info", classes="hint")
        yield Label("Subtitle list (Indonesian → Ngoko → Krama):")
        yield ListView(id="rv-subtitle-list", classes="subtitle-list")
        yield Label("Edit selected subtitle:")
        yield Horizontal(
            Label("Ngoko:", classes="field-label"),
            Input(placeholder="(pilih subtitle dulu)", id="rv-ngoko-input"),
            classes="row",
        )
        yield Horizontal(
            Label("Krama:", classes="field-label"),
            Input(placeholder="(pilih subtitle dulu)", id="rv-krama-input"),
            classes="row",
        )
        yield Horizontal(
            Button("Apply to selected", id="rv-apply-btn", variant="primary"),
            Button("Revert selected", id="rv-revert-btn", variant="default"),
            classes="row",
        )
        yield Label("Log:")
        yield Log(id="rv-log", max_lines=100, classes="log")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rv-load-btn":
            self._load_srt()
        elif event.button.id == "rv-prev-btn":
            self._prev_page()
        elif event.button.id == "rv-next-btn":
            self._next_page()
        elif event.button.id == "rv-save-btn":
            self._save_all()
        elif event.button.id == "rv-apply-btn":
            self._apply_edit()
        elif event.button.id == "rv-revert-btn":
            self._revert_edit()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Index global dari list item
        item_idx = event.list_view.index
        if item_idx is None:
            return
        page_start = self.current_page * self.PAGE_SIZE
        global_idx = page_start + item_idx
        if global_idx >= len(self.ngoko_subs):
            return
        self.selected_idx = global_idx
        self._load_selected_to_inputs()

    def _load_srt(self) -> None:
        log = self.query_one("#rv-log", Log)
        ngoko_path = OUTPUT_DIR / "ngoko.srt"
        krama_path = OUTPUT_DIR / "krama.srt"
        source_path = WORK_DIR / "source_video.id.srt"

        if not ngoko_path.exists() or not krama_path.exists():
            log.write_line("[!] output/ngoko.srt atau output/krama.srt belum ada.")
            log.write_line("    Run Stage 3 (Grammar) + Stage 4 (Split) dulu.")
            return

        try:
            self.ngoko_subs = list(pysrt.open(ngoko_path))
            self.krama_subs = list(pysrt.open(krama_path))
            if source_path.exists():
                self.source_subs = list(pysrt.open(source_path))
            else:
                self.source_subs = []
            log.write_line(
                f"[+] Loaded: {len(self.ngoko_subs)} ngoko, "
                f"{len(self.krama_subs)} krama, "
                f"{len(self.source_subs)} source subs."
            )
            self.current_page = 0
            self._render_page()
        except Exception as e:
            log.write_line(f"[!] ERROR loading SRT: {e}")

    def _render_page(self) -> None:
        list_view = self.query_one("#rv-subtitle-list", ListView)
        list_view.clear()
        if not self.ngoko_subs:
            self.query_one("#rv-page-info", Static).update("(no subs loaded)")
            return
        page_start = self.current_page * self.PAGE_SIZE
        page_end = min(page_start + self.PAGE_SIZE, len(self.ngoko_subs))
        for i in range(page_start, page_end):
            ngo = self.ngoko_subs[i].text.replace("\n", " ")[:50]
            if self.source_subs and i < len(self.source_subs):
                src = self.source_subs[i].text.replace("\n", " ")[:30]
            else:
                src = "-"
            label = f"[{i+1}] {src}  →  {ngo}"
            list_view.append(ListItem(Label(label)))
        total_pages = (len(self.ngoko_subs) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        self.query_one("#rv-page-info", Static).update(
            f"Page {self.current_page + 1} / {total_pages}  "
            f"(subs {page_start + 1}–{page_end} of {len(self.ngoko_subs)})"
        )

    def _prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def _next_page(self) -> None:
        total_pages = max(1, (len(self.ngoko_subs) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_page()

    def _load_selected_to_inputs(self) -> None:
        if self.selected_idx >= len(self.ngoko_subs):
            return
        ngo_input = self.query_one("#rv-ngoko-input", Input)
        kra_input = self.query_one("#rv-krama-input", Input)
        ngo_input.value = self.ngoko_subs[self.selected_idx].text.replace("\n", " ")
        if self.selected_idx < len(self.krama_subs):
            kra_input.value = self.krama_subs[self.selected_idx].text.replace("\n", " ")

    def _apply_edit(self) -> None:
        log = self.query_one("#rv-log", Log)
        if self.selected_idx >= len(self.ngoko_subs):
            log.write_line("[!] Pilih subtitle dulu dari list.")
            return
        ngo_input = self.query_one("#rv-ngoko-input", Input)
        kra_input = self.query_one("#rv-krama-input", Input)
        self.ngoko_subs[self.selected_idx].text = ngo_input.value
        if self.selected_idx < len(self.krama_subs):
            self.krama_subs[self.selected_idx].text = kra_input.value
        log.write_line(
            f"[+] Applied edit to sub [{self.selected_idx + 1}]. "
            "Klik 'Save All' untuk tulis ke file."
        )
        # Re-render page untuk update label
        self._render_page()

    def _revert_edit(self) -> None:
        log = self.query_one("#rv-log", Log)
        if not self.ngoko_subs:
            return
        self._load_selected_to_inputs()
        log.write_line(f"[i] Reverted input fields to current sub [{self.selected_idx + 1}].")

    def _save_all(self) -> None:
        log = self.query_one("#rv-log", Log)
        if not self.ngoko_subs:
            log.write_line("[!] Belum load SRT.")
            return
        try:
            ngoko_srt = pysrt.SubRipFile()
            for sub in self.ngoko_subs:
                ngoko_srt.append(sub)
            ngoko_srt.save(OUTPUT_DIR / "ngoko.srt", encoding="utf-8")
            krama_srt = pysrt.SubRipFile()
            for sub in self.krama_subs:
                krama_srt.append(sub)
            krama_srt.save(OUTPUT_DIR / "krama.srt", encoding="utf-8")
            log.write_line(
                f"[+] Saved {len(self.ngoko_subs)} ngoko + "
                f"{len(self.krama_subs)} krama subs ke output/."
            )
        except Exception as e:
            log.write_line(f"[!] ERROR saving: {e}")


# ============================================================================
# Pane 8: Uncovered Words (Add to Kamus)
# ============================================================================
class UncoveredPane(Vertical):
    """Tab 8: Uncovered words + add to kamus.

    Scan source SRT (Indonesian) untuk kata yang belum ada di kamus.
    Tampilkan top-N by frequency. User input Jawa translation.
    Save ke kamus_jawa.json.
    """

    TOP_N = 30

    def __init__(self):
        super().__init__()
        self.uncovered: list[tuple[str, int]] = []  # [(word, freq)]
        self.selected_word_idx: int = -1

    def compose(self) -> ComposeResult:
        yield Static("Tab 8: Uncovered Words → Add to Kamus", classes="stage-title")
        yield Static(
            "Scan work/source_video.id.srt untuk kata Indonesian yang belum "
            f"ter-cover kamus. Top-{self.TOP_N} by frequency. "
            "Tambahkan translation → save langsung ke kamus_jawa.json.",
            classes="hint",
        )
        yield Horizontal(
            Button("Scan", id="uc-scan-btn", variant="primary"),
            Button("Add to kamus", id="uc-add-btn", variant="success"),
            Button("Clear", id="uc-clear-btn", variant="default"),
            classes="row",
        )
        yield Static(id="uc-stats", classes="hint")
        yield Label("Uncovered words (click to select):")
        yield ListView(id="uc-word-list", classes="word-list")
        yield Label("Add Jawa translation for selected word:")
        yield Horizontal(
            Label("Word:", classes="field-label"),
            Input(placeholder="(auto-filled)", id="uc-word-input", disabled=True),
            classes="row",
        )
        yield Horizontal(
            Label("Jawa:", classes="field-label"),
            Input(placeholder="jawa ngoko translation (e.g., jaran, wedi, dadi)", id="uc-jawa-input"),
            classes="row",
        )
        yield Horizontal(
            Label("Krama:", classes="field-label"),
            Input(placeholder="(opsional) krama form, kalau beda", id="uc-krama-input"),
            classes="row",
        )
        yield Label("Log:")
        yield Log(id="uc-log", max_lines=100, classes="log")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "uc-scan-btn":
            self._scan()
        elif event.button.id == "uc-add-btn":
            self._add_to_kamus()
        elif event.button.id == "uc-clear-btn":
            self._clear()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_idx = event.list_view.index
        if item_idx is None or item_idx >= len(self.uncovered):
            return
        self.selected_word_idx = item_idx
        word = self.uncovered[item_idx][0]
        self.query_one("#uc-word-input", Input).value = word
        self.query_one("#uc-jawa-input", Input).value = ""
        self.query_one("#uc-krama-input", Input).value = ""

    def _scan(self) -> None:
        log = self.query_one("#uc-log", Log)
        src_path = WORK_DIR / "source_video.id.srt"
        if not src_path.exists():
            log.write_line(f"[!] {src_path} tidak ada. Run Stage 1 (Fetch) dulu.")
            return

        log.write_line("[+] Scanning source SRT...")
        k = _load_kamus()
        id2ng = k.get("typo_corrections", {})
        n2k = k.get("ngoko_to_krama", {})

        with open(src_path, encoding="utf-8") as f:
            srt_text = f.read()

        # Extract text lines (skip number + timestamp)
        text_lines = []
        for line in srt_text.split("\n"):
            if not line.strip():
                continue
            if re.match(r"^\d+$", line.strip()):
                continue
            if "-->" in line:
                continue
            text_lines.append(line)

        text = " ".join(text_lines).lower()
        tokens_raw = re.findall(r"[a-zà-ÿ-]+", text)
        tokens = [t for t in tokens_raw if len(t) >= 2 and t.replace("-", "").isalpha()]

        total = len(tokens)
        uncovered_counter = Counter(t for t in tokens if t not in id2ng and t not in n2k)
        self.uncovered = uncovered_counter.most_common(self.TOP_N)

        covered = total - sum(c for w, c in uncovered_counter.items() if w not in id2ng and w not in n2k)
        log.write_line(f"[+] Total tokens: {total}")
        log.write_line(f"[+] Unique uncovered: {len(uncovered_counter)}")
        log.write_line(f"[+] Top-{self.TOP_N} loaded. Click word untuk select.")

        self.query_one("#uc-stats", Static).update(
            f"Coverage: {covered}/{total} ({covered * 100 / total:.1f}%)  •  "
            f"Showing top-{self.TOP_N} of {len(uncovered_counter)} uncovered"
        )
        self._render_word_list()

    def _render_word_list(self) -> None:
        list_view = self.query_one("#uc-word-list", ListView)
        list_view.clear()
        for word, freq in self.uncovered:
            label = f"{word}  ({freq}x)"
            list_view.append(ListItem(Label(label)))

    def _add_to_kamus(self) -> None:
        log = self.query_one("#uc-log", Log)
        if self.selected_word_idx < 0 or self.selected_word_idx >= len(self.uncovered):
            log.write_line("[!] Pilih word dari list dulu.")
            return
        word = self.query_one("#uc-word-input", Input).value.strip().lower()
        jawa = self.query_one("#uc-jawa-input", Input).value.strip()
        krama = self.query_one("#uc-krama-input", Input).value.strip()
        if not word or not jawa:
            log.write_line("[!] Word & Jawa translation harus diisi.")
            return

        word_norm = _strip_accents(word)
        jawa_norm = _strip_accents(jawa)

        k = _load_kamus()
        id2ng = k.get("typo_corrections", {})
        n2k = k.get("ngoko_to_krama", {})

        if word_norm in id2ng:
            existing = id2ng[word_norm]
            if existing == jawa_norm:
                log.write_line(f"[i] '{word}' -> '{jawa}' sudah ada di kamus (no-op).")
                return
            else:
                log.write_line(
                    f"[!] CONFLICT: '{word}' existing='{existing}', "
                    f"proposed='{jawa_norm}'. Skip untuk safety."
                )
                return

        id2ng[word_norm] = jawa_norm

        # Krama (opsional)
        if krama:
            krama_norm = _strip_accents(krama)
            n2k[jawa_norm] = krama_norm
            log.write_line(f"[+] n2k: {jawa_norm} -> {krama_norm}")

        # Update meta
        k["typo_corrections"] = id2ng
        k["ngoko_to_krama"] = n2k
        meta = k.get("meta", {})
        meta["version"] = meta.get("version", "0.0.0")
        meta["typo_corrections_count"] = len(id2ng)
        meta["ngoko_to_krama_count"] = len(n2k)
        meta["note"] = (
            f"v{meta['version']}: +manual entry from TUI Uncovered pane: "
            f"'{word_norm}' -> '{jawa_norm}'"
        )
        k["meta"] = meta

        KAMUS_PATH.write_text(
            json.dumps(k, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.write_line(
            f"[+] Added to kamus: '{word}' -> '{jawa}' (typo_corrections)."
        )
        # Re-scan untuk update list (kata yang barusan di-add akan hilang dari list)
        self._scan()

    def _clear(self) -> None:
        self.uncovered = []
        self.selected_word_idx = -1
        self.query_one("#uc-word-list", ListView).clear()
        self.query_one("#uc-stats", Static).update("(no scan yet)")
        self.query_one("#uc-word-input", Input).value = ""
        self.query_one("#uc-jawa-input", Input).value = ""
        self.query_one("#uc-krama-input", Input).value = ""
        self.query_one("#uc-log", Log).clear()


# ============================================================================
# Pane 9: Kamus Stats
# ============================================================================
class KamusStatsPane(Vertical):
    """Tab 9: Kamus statistics + coverage analysis."""

    def compose(self) -> ComposeResult:
        yield Static("Tab 9: Kamus Statistics", classes="stage-title")
        yield Static(
            "Statistik kamus_jawa.json + coverage analysis pada SRT "
            "yang sedang di-proses.",
            classes="hint",
        )
        yield Horizontal(
            Button("Reload kamus", id="ks-reload-btn", variant="default"),
            Button("Run coverage analysis", id="ks-cov-btn", variant="primary"),
            classes="row",
        )
        yield Label("Kamus info:")
        yield Static(id="ks-kamus-info", classes="report-box")
        yield Label("Coverage analysis:")
        yield Static(id="ks-coverage", classes="report-box")
        yield Label("Log:")
        yield Log(id="ks-log", max_lines=100, classes="log")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ks-reload-btn":
            self._reload()
        elif event.button.id == "ks-cov-btn":
            self._run_coverage()

    def on_mount(self) -> None:
        self._reload()

    def _reload(self) -> None:
        log = self.query_one("#ks-log", Log)
        k = _load_kamus()
        meta = k.get("meta", {})
        id2ng = k.get("typo_corrections", {})
        n2k = k.get("ngoko_to_krama", {})
        n2ki = k.get("ngoko_to_krama_inggil", {})

        sources = meta.get("sources", [])
        sources_md = "\n".join(f"- {s}" for s in sources) if sources else "(none)"

        info_md = (
            f"**Version:** {meta.get('version', '?')}\n"
            f"**Last updated:** {meta.get('last_updated', '?')}\n"
            f"**typo_corrections:** {len(id2ng):,} entries\n"
            f"**ngoko_to_krama:** {len(n2k):,} entries\n"
            f"**ngoko_to_krama_inggil:** {len(n2ki):,} entries\n"
            f"**File size:** {KAMUS_PATH.stat().st_size:,} bytes\n"
            f"\n**Sources:**\n{sources_md}\n"
            f"\n**Note:** {meta.get('note', '(none)')}"
        )
        self.query_one("#ks-kamus-info", Static).update(info_md)
        log.write_line(
            f"[+] Reloaded kamus v{meta.get('version', '?')}: "
            f"{len(id2ng)} + {len(n2k)}"
        )

    def _run_coverage(self) -> None:
        log = self.query_one("#ks-log", Log)
        src_path = WORK_DIR / "source_video.id.srt"
        if not src_path.exists():
            log.write_line(f"[!] {src_path} tidak ada. Run Stage 1 (Fetch) dulu.")
            return

        log.write_line("[+] Running coverage analysis...")
        k = _load_kamus()
        id2ng = k.get("typo_corrections", {})
        n2k = k.get("ngoko_to_krama", {})

        with open(src_path, encoding="utf-8") as f:
            srt_text = f.read()
        text_lines = []
        for line in srt_text.split("\n"):
            if not line.strip() or re.match(r"^\d+$", line.strip()) or "-->" in line:
                continue
            text_lines.append(line)
        text = " ".join(text_lines).lower()
        tokens_raw = re.findall(r"[a-zà-ÿ-]+", text)
        tokens = [t for t in tokens_raw if len(t) >= 2 and t.replace("-", "").isalpha()]

        total = len(tokens)
        covered = sum(1 for t in tokens if t in id2ng or t in n2k)
        pct = covered * 100 / total if total else 0

        uncovered_counter = Counter(
            t for t in tokens if t not in id2ng and t not in n2k
        )
        top_uncovered = uncovered_counter.most_common(15)
        top_md = "\n".join(
            f"  {i+1}. `{w}` ({c}x)" for i, (w, c) in enumerate(top_uncovered)
        )

        cov_md = (
            f"**Source:** `{src_path.name}`\n\n"
            f"**Total tokens:** {total:,}\n"
            f"**Covered:** {covered:,} ({pct:.1f}%)\n"
            f"**Uncovered:** {total - covered:,} ({100 - pct:.1f}%)\n"
            f"**Unique uncovered:** {len(uncovered_counter):,}\n\n"
            f"**Top 15 uncovered:**\n{top_md}"
        )
        self.query_one("#ks-coverage", Static).update(cov_md)
        log.write_line(f"[+] Coverage: {pct:.1f}% ({covered}/{total})")

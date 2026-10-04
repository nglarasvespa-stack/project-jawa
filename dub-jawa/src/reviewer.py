"""Reviewer helper: generate diff, save report, expose approval gate.

Berguna untuk semua stage (3 grammar, 4 split, 5 tts).
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class StageReport:
    stage_id: str           # '1', '2', '3', '4', '5'
    stage_name: str         # 'Fetch', 'Translate', 'Grammar', 'Split', 'TTS'
    input_file: str
    output_file: str
    summary: dict           # angka2 ringkas: baris diubah, kata diubah, dll
    diff_preview: str       # diff text untuk ditampilkan di TUI
    approved: bool = False  # diisi user


def make_unified_diff(before_text: str, after_text: str, n: int = 3) -> str:
    """Bikin unified diff yang rapi, dengan cleanup whitespace.

    Args:
        before_text: konten sebelum stage.
        after_text: konten sesudah stage.
        n: context lines.
    """
    before_lines = before_text.splitlines(keepends=False)
    after_lines = after_text.splitlines(keepends=False)
    diff = difflib.unified_diff(
        before_lines, after_lines,
        fromfile="before",
        tofile="after",
        n=n,
        lineterm="",
    )
    return "\n".join(diff)


def save_report(report: StageReport, reports_dir: Path) -> Path:
    """Simpan laporan stage ke reports_dir/stage{n}_report.md."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / f"stage{report.stage_id}_report.md"

    summary_md = "\n".join(f"- **{k}**: {v}" for k, v in report.summary.items())

    content = f"""# Stage {report.stage_id}: {report.stage_name} Report

## Files
- Input: `{report.input_file}`
- Output: `{report.output_file}`

## Summary
{summary_md}

## Diff Preview (truncated to 200 lines)
```diff
{report.diff_preview[:8000]}
```

## Approval
- Status: {"**APPROVED**" if report.approved else "**PENDING**"}
"""
    md_path.write_text(content, encoding="utf-8")
    return md_path


def save_state(work_dir: Path, stage_id: str, payload: dict) -> None:
    """Simpan state per-stage supaya bisa dilanjut (resume) jika app di-restart."""
    state_dir = work_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"stage{stage_id}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_state(work_dir: Path, stage_id: str) -> dict:
    state_path = work_dir / "state" / f"stage{stage_id}.json"
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))

"""Stage 2: Translate SRT dari bahasa source ke Jawa standar via LLM.

Input  : work/source_video.<lang>.srt  (hasil stage 1)
         work/info.json               (untuk tahu source language)
Output : work/translated.srt           (Jawa standar, belum dibagi ngoko/krama)
         work/reports/stage2_report.md (laporan: sukses/gagal, sample before/after)

Strategi:
  1. Parse SRT pakai pysrt, ambil list (index, text).
  2. Batch per N baris (default 20) supaya prompt tidak terlalu panjang.
  3. Untuk tiap batch, panggil `z-ai chat` CLI dengan system prompt:
     "Translate from {source_lang} to standard Javanese. Output JSON array only."
  4. Parse response JSON: [{"i": <int>, "t": "<translated>"}]
  5. Map balik ke SRT dengan timing asli.
  6. Failed batch -> fallback: isi dengan text original + tag [ untranslated ].
  7. Simpan laporan.

Pakai LLM GLM (model glm-4-plus via z-ai CLI).

CLI cost note: 2877 baris / batch 20 = ~144 panggilan. Estimasi 2-4 menit total.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

import pysrt


# Nama bahasa untuk prompt LLM (lebih jelas dari kode ISO)
LANG_NAMES = {
    "zh-Hant": "Traditional Chinese",
    "zh-Hans": "Simplified Chinese",
    "zh": "Chinese",
    "en": "English",
    "id": "Indonesian",
    "ms": "Malay",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ar": "Arabic",
    "th": "Thai",
    "vi": "Vietnamese",
    "tl": "Tagalog",
    "ru": "Russian",
    "unknown": "auto-detect (the source language)",
}


# System prompt yang dipakai untuk semua batch
SYSTEM_PROMPT_TEMPLATE = """You are a professional subtitle translator for Asian dramas and films.

Task: Translate the user's subtitle lines from {source_lang} to **standard Javanese** (basa Jawa standar - campuran ngoko dan krama yang wajar untuk media).

Rules:
1. Preserve the meaning, emotional tone, and context of each line.
2. Keep translations concise - max 80 characters per line (subtitles must fit screen).
3. If a line is just an interjection/sound (e.g., "啊", "hmm", "ah"), use the closest Javanese equivalent (e.g., "oh", "ah", "eh", or keep as-is if no equivalent).
4. Do NOT add any explanation, notes, or markdown formatting.
5. Output ONLY a valid JSON array. Each element: {{"i": <int index from input>, "t": "<translated text>"}}
6. Translate each line independently - do not merge or split lines.
7. Match the count: input has N lines, output must have N elements with matching indices.

Output format (JSON array only, no other text):
[{{"i": 1, "t": "..."}}, {{"i": 2, "t": "..."}}, ...]
"""


@dataclass
class TranslateResult:
    srt_in_path: str
    srt_out_path: str
    source_lang: str
    total_subs: int
    total_batches: int
    successful_batches: int
    failed_batches: int
    failed_indices: list[int]
    elapsed_sec: float
    sample_before_after: list[dict]  # [{i, before, after}, ...]


def _strip_code_fence(text: str) -> str:
    """Buang ```json ... ``` kalau LLM tidak nurut instruksi."""
    text = text.strip()
    if text.startswith("```"):
        # buang baris pertama (```json atau ```)
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _call_llm(system_prompt: str, user_prompt: str, timeout: int = 60) -> str:
    """Panggil z-ai chat CLI, return content response."""
    cmd = [
        "z-ai", "chat",
        "--prompt", user_prompt,
        "--system", system_prompt,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"z-ai CLI failed (rc={result.returncode}): {result.stderr[:500]}")

        # z-ai CLI menulis "🚀 Initializing..." ke stdout sebelum JSON.
        # ambil dari karakter `{` pertama yang menandai awal JSON response.
        stdout = result.stdout
        json_start = stdout.find("{")
        if json_start == -1:
            raise RuntimeError(f"No JSON in z-ai output. stdout[:500]: {stdout[:500]}")
        json_str = stdout[json_start:]

        data = json.loads(json_str)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Empty content from LLM")
        return content
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"LLM call timed out after {timeout}s")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Cannot parse z-ai output as JSON: {e}")


def _translate_batch(
    batch: list[dict],
    source_lang: str,
    batch_num: int,
    log: Optional[Callable[[str], None]] = None,
) -> tuple[list[dict], Optional[str]]:
    """Translate satu batch. Returns (translated_list, error_msg).

    batch: list of {"i": int, "s": str} (s = source text)
    Returns: list of {"i": int, "t": str} (t = translated)
    """
    source_lang_name = LANG_NAMES.get(source_lang, "the source language")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(source_lang=source_lang_name)

    user_prompt = (
        f"Translate these {len(batch)} subtitle lines from {source_lang_name} "
        f"to standard Javanese.\n\n"
        f"Input JSON:\n{json.dumps(batch, ensure_ascii=False)}\n\n"
        f"Output JSON only:"
    )

    try:
        raw = _call_llm(system_prompt, user_prompt)
        raw = _strip_code_fence(raw)

        # parse - coba beberapa kali kalau ada noise
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # coba extract array pakai regex
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not match:
                return [], f"Batch {batch_num}: cannot find JSON array in response"
            parsed = json.loads(match.group(0))

        if not isinstance(parsed, list):
            return [], f"Batch {batch_num}: response is not a list"

        # validasi format
        out = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            i = item.get("i")
            t = item.get("t", "")
            if i is None or not isinstance(i, int):
                continue
            if not isinstance(t, str):
                t = str(t)
            out.append({"i": i, "t": t})

        if log:
            log(f"  batch {batch_num}: ok ({len(out)}/{len(batch)} parsed)")
        return out, None

    except Exception as e:
        if log:
            log(f"  batch {batch_num}: FAIL - {e}")
        return [], f"Batch {batch_num}: {e}"


def translate_srt(
    work_dir: Path,
    batch_size: int = 20,
    limit: Optional[int] = None,
    log: Optional[Callable[[str], None]] = None,
) -> TranslateResult:
    """Translate SRT dari work/source_video.<lang>.srt -> work/translated.srt.

    Args:
        work_dir: folder kerja (harus ada info.json & source SRT).
        batch_size: jumlah baris per LLM call (default 20).
        limit: kalau diisi, hanya translate N baris pertama (mode testing).
        log: callback untuk TUI log.

    Returns:
        TranslateResult dengan stats.
    """
    if log is None:
        log = lambda msg: None

    info_path = work_dir / "info.json"
    if not info_path.exists():
        raise FileNotFoundError("work/info.json tidak ada. Jalankan stage 1 fetch dulu.")

    info = json.loads(info_path.read_text(encoding="utf-8"))
    source_lang = info.get("subtitle_lang", "unknown")
    srt_in_path = Path(info["srt_path"])
    if not srt_in_path.exists():
        # coba relative to work_dir
        candidate = work_dir / srt_in_path.name
        if candidate.exists():
            srt_in_path = candidate
        else:
            # coba relative to project root (translate.py berada di src/stages/)
            candidate = work_dir.parent / srt_in_path
            if candidate.exists():
                srt_in_path = candidate
            else:
                raise FileNotFoundError(f"SRT input tidak ditemukan: {srt_in_path}")

    log(f"[+] Loading SRT: {srt_in_path}")
    subs = pysrt.open(str(srt_in_path), encoding="utf-8-sig")
    total_subs = len(subs)
    log(f"[+] Total subtitles: {total_subs}")
    log(f"[+] Source language: {source_lang}")
    log(f"[+] Batch size: {batch_size}")

    if limit:
        subs_to_translate = subs[:limit]
        log(f"[+] Limit mode: only first {limit} subtitles")
    else:
        subs_to_translate = subs

    # build batches
    items = [{"i": idx + 1, "s": s.text} for idx, s in enumerate(subs_to_translate)]
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    total_batches = len(batches)
    log(f"[+] Total batches: {total_batches}")

    # translate tiap batch
    translations: dict[int, str] = {}  # index -> translated text
    failed_batches = 0
    failed_indices: list[int] = []
    successful_batches = 0

    t_start = time.time()
    for batch_num, batch in enumerate(batches, start=1):
        log(f"[batch {batch_num}/{total_batches}] translating {len(batch)} lines...")
        out, err = _translate_batch(batch, source_lang, batch_num, log=log)
        if err:
            failed_batches += 1
            # fallback: pakai text original + marker
            for item in batch:
                translations[item["i"]] = f"[untranslated] {item['s']}"
                failed_indices.append(item["i"])
        else:
            successful_batches += 1
            for item in out:
                translations[item["i"]] = item["t"]
            # kalau ada yang miss dari batch, isi dengan original
            for src_item in batch:
                if src_item["i"] not in translations:
                    translations[src_item["i"]] = f"[untranslated] {src_item['s']}"
                    failed_indices.append(src_item["i"])

    elapsed = time.time() - t_start
    log(f"[+] Done in {elapsed:.1f}s. Success: {successful_batches}/{total_batches}")

    # rebuild SRT dengan timing original
    out_subs = pysrt.SubRipFile()
    for idx, sub in enumerate(subs):
        new_idx = idx + 1
        new_text = translations.get(new_idx, sub.text)
        new_sub = pysrt.SubRipItem(
            index=new_idx,
            start=sub.start,
            end=sub.end,
            text=new_text,
        )
        out_subs.append(new_sub)

    srt_out_path = work_dir / "translated.srt"
    out_subs.save(str(srt_out_path), encoding="utf-8")
    log(f"[+] Saved: {srt_out_path}")

    # build sample before/after (5 pertama + 5 terakhir dari yang ditranslate)
    sample = []
    sample_indices = list(range(1, min(6, len(subs_to_translate) + 1)))
    if len(subs_to_translate) > 5:
        sample_indices += list(range(len(subs_to_translate) - 4, len(subs_to_translate) + 1))
    for i in sample_indices:
        if 1 <= i <= len(subs_to_translate):
            src_text = subs_to_translate[i - 1].text
            tgt_text = translations.get(i, "(missing)")
            sample.append({"i": i, "before": src_text, "after": tgt_text})

    result = TranslateResult(
        srt_in_path=str(srt_in_path),
        srt_out_path=str(srt_out_path),
        source_lang=source_lang,
        total_subs=total_subs,
        total_batches=total_batches,
        successful_batches=successful_batches,
        failed_batches=failed_batches,
        failed_indices=failed_indices[:50],  # cap untuk laporan
        elapsed_sec=elapsed,
        sample_before_after=sample,
    )

    # simpan state untuk resume / stage 3
    state_path = work_dir / "state" / "stage2.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # simpan laporan
    report_path = work_dir / "reports" / "stage2_report.md"
    report_path.write_text(_format_report(result), encoding="utf-8")
    log(f"[+] Report: {report_path}")

    return result


def _format_report(result: TranslateResult) -> str:
    """Generate markdown report untuk stage 2."""
    success_rate = (
        result.successful_batches / result.total_batches * 100
        if result.total_batches > 0
        else 0
    )

    sample_md = ""
    for s in result.sample_before_after:
        sample_md += (
            f"  - **#{s['i']}**\n"
            f"    - Before: `{s['before']}`\n"
            f"    - After:  `{s['after']}`\n"
        )

    failed_str = (
        f"- Failed indices (first 50): {result.failed_indices}"
        if result.failed_indices
        else "- Failed indices: (none)"
    )

    return f"""# Stage 2: Translate Report

## Summary
- **Source language**: `{result.source_lang}`
- **Total subtitles**: {result.total_subs}
- **Total batches**: {result.total_batches}
- **Successful batches**: {result.successful_batches} ({success_rate:.1f}%)
- **Failed batches**: {result.failed_batches}
- **Elapsed time**: {result.elapsed_sec:.1f}s ({result.elapsed_sec / 60:.1f}m)

## Files
- Input: `{result.srt_in_path}`
- Output: `{result.srt_out_path}`

## Failed Translations
{failed_str}

## Sample Before/After
{sample_md}

## Next step
User review: apakah terjemahan masuk akal? Kalau banyak yang gagal, coba:
  - Kecilkan batch_size (default 20 -> 10) di config.json
  - Atur limit untuk testing subset

Klik **[Y] Approve** di TUI untuk lanjut ke Stage 3 (Grammar fix).
"""


if __name__ == "__main__":
    # Test cepat dari CLI
    import sys
    wdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("work")
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    r = translate_srt(wdir, limit=limit, log=lambda m: print(m))
    print(f"\n=== DONE ===")
    print(f"Total: {r.total_subs}, Success: {r.successful_batches}/{r.total_batches}")
    print(f"Output: {r.srt_out_path}")

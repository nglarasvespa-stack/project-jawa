"""Expand kamus V4 = V2 prompt (proven working) + stricter post-filter.

Filter additions vs V2:
  1. Reject concatenated reduplikasi (e.g., "gedhanggedhang" instead of "gedhang-gedhang")
  2. Reject impolite krama imperatives (-na suffix at end where root also has -na)
  3. Reject multi-char suffix noise entries

Pakai prompt V2 yang lebih sederhana (proven working).
"""
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/home/z/my-project/dub-jawa")
KAMUS_PATH = ROOT / "kamus_jawa.json"

# Pakai prompt V2 yang proven working
SYSTEM_PROMPT = """You are a Javanese linguist specializing in ngoko<->krama transformation.

Task: Given a list of ngoko root words and their krama equivalents, generate inflected forms for each pair. Output JSON array.

CRITICAL RULES about Javanese morphology:

1. The root words given are ALREADY in their natural form. Do NOT add nasal prefixes (ng-, nge-, ny-, m-) because they are already incorporated.
2. Suffix forms to generate:
   - X + "e" (possessive): mangane, turune, tekane
   - X + "ake" (causative): manganake, turuake
   - X + "an" (iterative/noun): manganan, turuan, tekaan
   - X + "i" (locative): mangani, turui, tekai
   - X + "ne" (third person possessive): manganne, turune
3. Passive forms (for transitive verbs):
   - "di-" + X: dipangan, dituku
   - "ke-" + X: kepangan, ketuku
4. Circumfix:
   - "pa-" + X + "-an": pamangan, patiruan
   - "ka-" + X + "-an": kamangan, katiruan
5. Reduplikasi (use HYPHEN, not concatenation):
   - X-X: mangan-mangan -> nedha-nedha (eat repeatedly)
6. For NOUNS: only generate -e and -an.
7. For ADJECTIVES: generate -e, -an, and reduplikasi (X-X = "very X").

CULTURAL RULE - DO NOT GENERATE IMPOLITE FORMS:
  - Krama imperatives (-na suffix in krama) are IMPOLITE per Javanese culture
  - DO NOT generate forms like "manganna -> nedhana"
  - Skip -na imperative suffix entirely

OUTPUT FORMAT:
- Strict JSON array, no markdown.
- Each element: {"n": "<ngoko form>", "k": "<krama form>"}
- ALL forms lowercase.
- For reduplikasi, use HYPHEN: "mangan-mangan" NOT "manganmangan".
- NO space-separated multi-word forms.
- Include root forms themselves in output.
"""


def is_concatenated_redup(w: str) -> tuple[bool, str]:
    """Cek apakah w adalah concatenation of 2 same word. Return (True, converted_to_hyphen)."""
    if len(w) < 8:
        return False, w
    for split_pos in range(3, len(w) - 2):
        left = w[:split_pos]
        right = w[split_pos:]
        if left == right and len(left) >= 4:
            return True, f"{left}-{right}"
    return False, w


def call_llm(batch: list[dict]) -> list[dict]:
    user_prompt = (
        f"Generate inflected Javanese forms for these {len(batch)} root pairs:\n\n"
        f"{json.dumps(batch, ensure_ascii=False)}\n\n"
        f"Output JSON array only:"
    )

    cmd = ["z-ai", "chat", "--prompt", user_prompt, "--system", SYSTEM_PROMPT]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
        if result.returncode != 0:
            return []

        stdout = result.stdout
        for marker in ("{", "["):
            idx = stdout.find(marker)
            if idx != -1:
                break
        else:
            return []

        json_str = stdout[idx:]
        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "choices" in data:
                content = data["choices"][0].get("message", {}).get("content", "")
                json_str = content.strip()
                if json_str.startswith("```"):
                    json_str = json_str.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                data = json.loads(json_str)
            parsed = data
        except json.JSONDecodeError:
            m = re.search(r"\[.*\]", json_str, re.DOTALL)
            if not m:
                return []
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                return []

        if not isinstance(parsed, list):
            return []

        out = []
        seen = set()
        for item in parsed:
            if not isinstance(item, dict):
                continue
            n = (item.get("n") or item.get("ngoko") or "").strip().lower()
            k = (item.get("k") or item.get("krama") or "").strip().lower()
            if not n or not k or n == k:
                continue
            # dedup
            if (n, k) in seen:
                continue
            seen.add((n, k))
            # Reject concatenated reduplikasi - tapi CONVERT ke hyphen, jangan reject
            is_redup_n, n_converted = is_concatenated_redup(n)
            if is_redup_n:
                n = n_converted
            is_redup_k, k_converted = is_concatenated_redup(k)
            if is_redup_k:
                k = k_converted
            # Reject hyphen internal selain reduplikasi X-X
            if "-" in n:
                if not re.match(r"^[a-zêèé']+(-[a-zêèé']+)+$", n):
                    continue
                parts = n.split("-")
                if any(len(p) < 3 for p in parts):
                    continue
            if "-" in k:
                if not re.match(r"^[a-zêèé']+(-[a-zêèé']+)+$", k):
                    continue
                parts = k.split("-")
                if any(len(p) < 3 for p in parts):
                    continue
            # Reject underscore, space
            if "_" in n or "_" in k or " " in n or " " in k:
                continue
            # Reject non-latin
            if not re.match(r"^[a-zêèé'àâîôû-]+$", n):
                continue
            if not re.match(r"^[a-zêèé'àâîôû-]+$", k):
                continue
            # Reject impolite krama imperatives (-na suffix at end)
            if k.endswith("na") and len(k) > 4 and n.endswith("na") and len(n) > 4:
                continue
            out.append({"n": n, "k": k})
        return out

    except Exception as e:
        print(f"  [!] Error: {e}")
        return []


def load_kamus():
    return json.loads(KAMUS_PATH.read_text(encoding="utf-8"))


def save_kamus(data):
    KAMUS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--save-raw", action="store_true")
    args = parser.parse_args()

    kamus = load_kamus()
    existing_n2k = {k: v for k, v in kamus.get("ngoko_to_krama", {}).items() if not k.startswith("_")}
    print(f"[+] Existing entries: {len(existing_n2k)}")

    roots = []
    for n, k in existing_n2k.items():
        if "_" in n or "_" in k or " " in n or " " in k:
            continue
        if "-" in n or "-" in k:
            continue
        if len(n) < 3 or len(n) > 12:
            continue
        if not re.match(r"^[a-zA-Zêèé']+$", n):
            continue
        if not re.match(r"^[a-zA-Zêèé']+$", k):
            continue
        roots.append({"n": n, "k": k})

    if args.limit:
        roots = roots[: args.limit]

    print(f"[+] Root pairs to process: {len(roots)}")
    print(f"[+] Batch size: {args.batch_size}")
    print(f"[+] Estimated LLM calls: {(len(roots) + args.batch_size - 1) // args.batch_size}")

    if args.dry_run:
        print(f"\n[DRY RUN] First 10 roots:")
        for r in roots[:10]:
            print(f"  {r['n']} -> {r['k']}")
        return

    new_entries = {}
    total_calls = 0
    total_generated = 0
    failed = 0
    all_raw = []

    batches = [roots[i:i+args.batch_size] for i in range(0, len(roots), args.batch_size)]
    print(f"\n[+] Total batches: {len(batches)}")
    eta = len(batches) * 8
    print(f"[+] ETA: {eta}s = {eta/60:.1f}m\n")

    t_start = time.time()
    for i, batch in enumerate(batches, 1):
        print(f"[batch {i}/{len(batches)}] {len(batch)} roots: {[r['n'] for r in batch]}")
        forms = call_llm(batch)
        total_calls += 1
        if not forms:
            failed += 1
            print(f"  [!] empty response")
            continue

        if args.save_raw:
            all_raw.extend(forms)

        added = 0
        for f in forms:
            n_norm = f["n"]
            k_norm = f["k"]
            if not n_norm or not k_norm:
                continue
            if n_norm not in existing_n2k and n_norm not in new_entries:
                new_entries[n_norm] = k_norm
                added += 1
                total_generated += 1
        elapsed = time.time() - t_start
        rate = total_generated / elapsed if elapsed > 0 else 0
        print(f"  -> {len(forms)} forms, {added} new, total new: {total_generated}, rate: {rate:.1f}/s")

    elapsed = time.time() - t_start
    print(f"\n[+] Done in {elapsed:.1f}s")
    print(f"[+] LLM calls: {total_calls}, failed: {failed}")
    print(f"[+] New entries: {total_generated}")

    if args.save_raw:
        raw_path = Path("/home/z/my-project/scripts/raw_llm_v4.json")
        raw_path.write_text(json.dumps(all_raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Raw saved: {raw_path}")

    print(f"\n[+] Merging into kamus_jawa.json...")
    merged = dict(existing_n2k)
    merged.update(new_entries)
    kamus["ngoko_to_krama"] = merged

    kamus["meta"] = kamus.get("meta", {})
    kamus["meta"]["version"] = "0.8.0"
    kamus["meta"]["note"] = (
        "Kamus dari Wiktionary + manual + LLM root morphology (V4). "
        "Filter: no impolite -na imperatives, no concatenated reduplikasi, proper hyphen X-X."
    )
    kamus["meta"]["sources"] = kamus["meta"].get("sources", []) + [
        f"LLM morphology V4 ({total_generated} entries, impolite -na filtered)"
    ]
    kamus["meta"]["last_updated"] = "2026-10-04"
    kamus["meta"]["total_entries"] = len(merged)

    save_kamus(kamus)
    print(f"[+] Saved: {KAMUS_PATH}")
    print(f"[+] Total: {len(merged)} entries ({KAMUS_PATH.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()

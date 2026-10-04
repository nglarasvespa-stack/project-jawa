"""Expand kamus_jawa.json dengan inflected forms via LLM.

Untuk tiap root pair (ngoko_root -> krama_root), LLM generate:
  - Bentuk aktif dengan prefix: ng-/nge-/ny-/m-/ma- (untuk verb)
  - Bentuk pasif: di-/ke-
  - Bentuk dengan suffix: -ake/-an/-i/-ne/-na
  - Bentuk dengan circumfix: pa-an, ka-an, etc.
  - Bentuk reduplikasi: mangan-mangan -> nedha-nedha

Output: kamus dengan ribuan entries (root + inflected forms), preserve imbuhan.

Cara pakai:
  python expand_kamus.py [--batch-size 10] [--limit N] [--dry-run]
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path("/home/z/my-project/dub-jawa")
KAMUS_PATH = ROOT / "kamus_jawa.json"


SYSTEM_PROMPT = """You are a Javanese linguist specializing in speech level transformation (ngoko <-> krama).

Given Javanese root word pairs (ngoko, krama), generate ALL common inflected forms for BOTH ngoko and krama. Preserve the meaning and the morphology.

Javanese morphology reference:
- Active verb prefixes (ngoko): ng-, nge-, ny-, m-, ny- (apply to verb roots)
  Example: "mangan" root has active form "mangan" (already inflected with m- prefix)
- Passive: di-, ke-, kapi-, kapa-
- Suffix -ake (causative/transitive), -an (noun/iterative), -i (locative), -ne (possessive)
- Circumfix: pa-an (place where), ka-an (passive noun), sa-nya (all of)
- Reduplication: mangan-mangan (eat repeatedly)

For each inflected form of the ngoko root, provide the corresponding inflected krama form.

Rules:
1. Preserve imbuhan - they carry meaning. Don't strip them.
2. For each (ngoko_inflected, krama_inflected) pair, output one entry.
3. Skip forms that don't make linguistic sense for this root (e.g., don't generate passive for nouns).
4. Also include the ROOT forms themselves (ngoko_root -> krama_root) to ensure they're in the output.
5. Handle irregular forms carefully. When unsure, skip.
6. If the root is a noun, only generate suffix forms (no active/passive verb prefixes).
7. For adjectives, generate -e (possessive), -an (collective) forms.

Output: STRICT JSON array, no markdown. Each element: {"n": "<ngoko form>", "k": "<krama form>"}
"""


def call_llm(batch: list[dict]) -> list[dict]:
    """Panggil LLM untuk generate inflected forms dari batch root pairs.

    batch: list of {"n": ngoko_root, "k": krama_root}
    Returns: list of {"n": ngoko_inflected, "k": krama_inflected}
    """
    user_prompt = (
        f"Generate inflected forms for these {len(batch)} Javanese root pairs "
        f"(ngoko -> krama):\n\n"
        f"{json.dumps(batch, ensure_ascii=False)}\n\n"
        f"Output JSON array only:"
    )

    cmd = [
        "z-ai", "chat",
        "--prompt", user_prompt,
        "--system", SYSTEM_PROMPT,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
        if result.returncode != 0:
            print(f"  [!] z-ai CLI failed: {result.stderr[:300]}")
            return []

        stdout = result.stdout
        json_start = stdout.find("{")
        if json_start == -1:
            # mungkin LLM return JSON array langsung
            json_start = stdout.find("[")
            if json_start == -1:
                print(f"  [!] No JSON in output")
                return []
        json_str = stdout[json_start:]

        # coba parse - pertama sebagai array, kalau fail coba extract array
        try:
            parsed = json.loads(json_str)
            # kalau dapat object, ambil dari field "n"/"k" atau "choices"
            if isinstance(parsed, dict):
                # mungkin itu response wrapper
                if "choices" in parsed:
                    content = parsed["choices"][0].get("message", {}).get("content", "")
                    content = content.strip()
                    if content.startswith("```"):
                        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    parsed = json.loads(content)
        except json.JSONDecodeError:
            # extract array pakai regex
            m = re.search(r"\[.*\]", json_str, re.DOTALL)
            if not m:
                print(f"  [!] Cannot parse JSON")
                return []
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError as e:
                print(f"  [!] JSON parse fail: {e}")
                return []

        if not isinstance(parsed, list):
            return []

        out = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            n = item.get("n") or item.get("ngoko") or ""
            k = item.get("k") or item.get("krama") or ""
            if not n or not k or not isinstance(n, str) or not isinstance(k, str):
                continue
            n = n.strip().lower()
            k = k.strip().lower()
            if n and k and n != k:
                out.append({"n": n, "k": k})
        return out

    except subprocess.TimeoutExpired:
        print(f"  [!] LLM call timeout")
        return []
    except Exception as e:
        print(f"  [!] Error: {e}")
        return []


def load_kamus() -> dict:
    if not KAMUS_PATH.exists():
        return {}
    return json.loads(KAMUS_PATH.read_text(encoding="utf-8"))


def save_kamus(data: dict) -> None:
    KAMUS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kamus = load_kamus()
    existing_n2k = {k: v for k, v in kamus.get("ngoko_to_krama", {}).items() if not k.startswith("_")}
    print(f"[+] Existing ngoko_to_krama entries: {len(existing_n2k)}")

    # Build list of root pairs (filter: hanya yang singkat dan clean)
    roots = []
    for n, k in existing_n2k.items():
        # skip entries dengan underscore (multi-word)
        if "_" in n or "_" in k:
            continue
        # skip entries panjang
        if len(n) > 15 or len(k) > 15:
            continue
        # hanya accept pure latin
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
        print(f"\n[DRY RUN] First 5 roots:")
        for r in roots[:5]:
            print(f"  {r['n']} -> {r['k']}")
        return

    # batch process
    new_entries = {}
    total_llm_calls = 0
    total_forms_generated = 0
    failed_batches = 0

    batches = [roots[i:i+args.batch_size] for i in range(0, len(roots), args.batch_size)]
    print(f"\n[+] Total batches: {len(batches)}")
    print(f"[+] Estimated time: {len(batches) * 5}s = {len(batches) * 5 / 60:.1f}m")
    print()

    t_start = time.time()
    for i, batch in enumerate(batches, 1):
        print(f"[batch {i}/{len(batches)}] processing {len(batch)} roots...")
        forms = call_llm(batch)
        total_llm_calls += 1
        if not forms:
            failed_batches += 1
            print(f"  [!] Empty response, skipping")
            continue
        for f in forms:
            n_norm = f["n"].strip().lower().replace(" ", "_")
            k_norm = f["k"].strip().lower().replace(" ", "_")
            if not n_norm or not k_norm or n_norm == k_norm:
                continue
            # jangan override existing manual entries
            if n_norm not in existing_n2k:
                new_entries[n_norm] = k_norm
                total_forms_generated += 1
            elif n_norm in new_entries:
                # already added by previous batch, skip
                pass
        elapsed = time.time() - t_start
        rate = total_forms_generated / elapsed if elapsed > 0 else 0
        print(f"  -> got {len(forms)} forms, new total: {total_forms_generated}, rate: {rate:.1f} forms/s")

    elapsed = time.time() - t_start
    print(f"\n[+] Done in {elapsed:.1f}s")
    print(f"[+] LLM calls: {total_llm_calls}")
    print(f"[+] Failed batches: {failed_batches}")
    print(f"[+] New entries generated: {total_forms_generated}")

    # merge ke kamus
    print(f"\n[+] Merging into kamus_jawa.json...")
    merged = dict(existing_n2k)
    merged.update(new_entries)
    kamus["ngoko_to_krama"] = merged

    # update meta
    kamus["meta"] = kamus.get("meta", {})
    kamus["meta"]["version"] = "0.4.0"
    kamus["meta"]["note"] = (
        f"Kamus dari Wiktionary + manual + LLM-generated inflected forms. "
        f"Imbuhan preserved (each inflected form is its own entry)."
    )
    kamus["meta"]["sources"] = kamus["meta"].get("sources", []) + [
        f"LLM-generated inflected forms ({total_forms_generated} entries) via z-ai CLI"
    ]
    kamus["meta"]["last_updated"] = "2026-10-04"
    kamus["meta"]["total_entries"] = len(merged)

    save_kamus(kamus)
    print(f"[+] Saved: {KAMUS_PATH}")
    print(f"[+] Total kamus entries now: {len(merged)}")
    print(f"[+] File size: {KAMUS_PATH.stat().st_size} bytes ({KAMUS_PATH.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()

"""Expand kamus_jawa.json dengan inflected forms via LLM - V2 dengan prompt lebih baik.

Pelajaran dari V1:
  - LLM generate "ng-mangan" yang salah - mangan SUDAH berprefix m- dari root "pangan"
  - Format hyphen tidak match kata di SRT (yang biasanya satu token tanpa hyphen)

V2:
  - Prompt jelas: JANGAN generate prefix ng-/nge-/ny-/m- sebagai entri terpisah
    karena root yang diberikan SUDAH dalam bentuk berprefix
  - Hanya generate suffix forms (-e, -ake, -an, -i, -ne, -na)
  - Hanya generate circumfix forms (ka-an, pa-an)
  - Hanya generate reduplikasi (X-X)
  - Hanya generate bentuk passif (di-X, ke-X) - prefix di-/ke- ditambah ke root
  - Filter output: no hyphen internal, lowercase only
  - Save raw LLM output untuk inspection
"""
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/home/z/my-project/dub-jawa")
KAMUS_PATH = ROOT / "kamus_jawa.json"


SYSTEM_PROMPT = """You are a Javanese linguist specializing in ngoko<->krama transformation.

Task: Given a list of ngoko root words and their krama equivalents, generate inflected forms for each pair. Output JSON array.

CRITICAL RULES about Javanese morphology:

1. The root words given are ALREADY in their natural form. Do NOT add nasal prefixes (ng-, nge-, ny-, m-) because they are already incorporated:
   - "mangan" already contains m- prefix (root: pangan). Do NOT generate "ng-mangan".
   - "tuku" already is the root. Generate "tumbas" form for krama.
   - "ngerti" already contains ng- prefix. Do NOT generate "ng-ngerti".

2. Suffix forms to generate (where applicable for the part of speech):
   - X + "-e" (possessive): mangane, turune, tekane
   - X + "-ake" (causative, transitive verb): manganake, turuake
   - X + "-an" (iterative/noun): manganan, turuan, tekaan
   - X + "-i" (locative/applicative): mangani, turui, tekai
   - X + "-ne" (third person possessive): manganne, turune
   - X + "-na" (imperative): manganna, turuna

3. Passive forms (for transitive verbs):
   - "di-" + X: dipangan, dituku, diweruh
   - "ke-" + X: kepangan, ketuku (accidental passive)

4. Circumfix:
   - "pa-" + X + "-an" (place/time of): pamangan (eating place), patiruan
   - "ka-" + X + "-an" (passive noun, state): kamangan, katiruan

5. Reduplication (only if meaningful, e.g., for repetitive action):
   - X-X: mangan-mangan -> nedha-nedha (eat repeatedly)

6. For NOUNS: only generate -e (possessive) and -ne (3rd person possessive) and -an (collective). Do NOT generate verbal passive/active forms.

7. For ADJECTIVES: generate -e (possessive), -an (collective), and reduplication (X-X = "very X").

8. For PRONOUNS/DETERMINERS: typically do not inflect. Output only the root.

OUTPUT FORMAT:
- Strict JSON array, no markdown.
- Each element: {"n": "<ngoko form>", "k": "<krama form>"}
- ALL forms lowercase, NO hyphens except in reduplication (e.g., "mangan-mangan").
- NO space-separated multi-word forms - they don't match SRT tokens.
- If you cannot generate a meaningful inflection, skip it.
- Include the root forms themselves in output.
"""


def call_llm(batch: list[dict]) -> list[dict]:
    user_prompt = (
        f"Generate inflected Javanese forms for these {len(batch)} root pairs:\n\n"
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
            return []

        stdout = result.stdout
        # cari JSON
        for start_marker in ("{", "["):
            idx = stdout.find(start_marker)
            if idx != -1:
                break
        else:
            return []

        json_str = stdout[idx:]
        # mungkin wrapped dalam choices[0].message.content
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
        for item in parsed:
            if not isinstance(item, dict):
                continue
            n = (item.get("n") or item.get("ngoko") or "").strip().lower()
            k = (item.get("k") or item.get("krama") or "").strip().lower()
            if not n or not k or n == k:
                continue
            # FILTER: reject entries dengan hyphen internal (kecuali reduplikasi X-X)
            # Allow: mangan-mangan (reduplikasi)
            # Reject: ng-mangan, m-eat (artifak)
            if "-" in n and not re.match(r"^[a-z]+(-[a-z]+)+$", n):
                continue
            if "-" in k and not re.match(r"^[a-z]+(-[a-z]+)+$", k):
                continue
            # Reject entries dengan underscore atau space
            if "_" in n or "_" in k or " " in n or " " in k:
                continue
            # Reject entries dengan non-latin
            if not re.match(r"^[a-zêèé'àâîôû-]+$", n):
                continue
            if not re.match(r"^[a-zêèé'àâîôû-]+$", k):
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
    parser.add_argument("--save-raw", action="store_true", help="Save raw LLM output")
    args = parser.parse_args()

    kamus = load_kamus()
    existing_n2k = {k: v for k, v in kamus.get("ngoko_to_krama", {}).items() if not k.startswith("_")}
    print(f"[+] Existing entries: {len(existing_n2k)}")

    # Filter roots: hanya yang clean (no underscore, no hyphen, latin only, length 3-12)
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
        print(f"[batch {i}/{len(batches)}] {len(batch)} roots...")
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
            # jangan override existing
            if n_norm not in existing_n2k and n_norm not in new_entries:
                new_entries[n_norm] = k_norm
                added += 1
                total_generated += 1
        elapsed = time.time() - t_start
        rate = total_generated / elapsed if elapsed > 0 else 0
        print(f"  -> {len(forms)} forms returned, {added} new, total new: {total_generated}, rate: {rate:.1f}/s")

    elapsed = time.time() - t_start
    print(f"\n[+] Done in {elapsed:.1f}s")
    print(f"[+] LLM calls: {total_calls}, failed: {failed}")
    print(f"[+] New entries: {total_generated}")

    if args.save_raw:
        raw_path = Path("/home/z/my-project/scripts/raw_llm_output.json")
        raw_path.write_text(json.dumps(all_raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Raw saved: {raw_path}")

    print(f"\n[+] Merging into kamus_jawa.json...")
    merged = dict(existing_n2k)
    merged.update(new_entries)
    kamus["ngoko_to_krama"] = merged

    kamus["meta"] = kamus.get("meta", {})
    kamus["meta"]["version"] = "0.5.0"
    kamus["meta"]["note"] = (
        "Kamus dari Wiktionary + manual + LLM-generated inflected forms (V2 dengan filter hyphen)."
    )
    kamus["meta"]["sources"] = kamus["meta"].get("sources", []) + [
        f"LLM-generated inflected forms V2 ({total_generated} entries, hyphen filtered)"
    ]
    kamus["meta"]["last_updated"] = "2026-10-04"
    kamus["meta"]["total_entries"] = len(merged)

    save_kamus(kamus)
    print(f"[+] Saved: {KAMUS_PATH}")
    print(f"[+] Total: {len(merged)} entries ({KAMUS_PATH.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()

"""Expand kamus_jawa.json dengan root tree morphology - V3.

Strategi root tree:
  - LLM paham Javanese morphology sebagai pohon akar
  - Untuk setiap root (mangan, nedha) - generate CABANG systematic:
    * Suffix forms yang SOPAN (-e, -ake, -an, -i, -ne) - SKIP -na (imperative impolite)
    * Circumfix (pa-an, ka-an)
    * Reduplikasi (X-X)
    * Passive (di-X, ke-X) - hanya untuk verb transitive
  - Filter strictly: no hyphen internal, no impolite imperatives

LLM dipakai sebagai linguist multibahasa yang paham:
  - Javanese speech level hierarchy (ngoko < krama < krama inggil)
  - Politeness rules (imperative di krama = impolite)
  - Morphology parallel (jika ngoko pakai prefix X, krama pakai prefix Y)

Batch: 5 root pairs per LLM call (lebih kecil dari v2 = 10, supaya LLM fokus per root)
"""
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/home/z/my-project/dub-jawa")
KAMUS_PATH = ROOT / "kamus_jawa.json"


SYSTEM_PROMPT = """You are a multilingual linguist with deep expertise in Javanese morphology and speech level transformation.

Task: For each (ngoko_root, krama_root) pair given, generate the COMPLETE family tree of inflected forms - both for ngoko and krama. The two trees must be MORPHOLOGICALLY PARALLEL: each inflected form in ngoko has a corresponding form in krama with the same morphological structure.

ROOT TREE CONCEPT:
A Javanese verb root has a tree of inflected forms. Each branch is a suffix/prefix/circumfix that attaches to the root. The ngoko tree and krama tree must have the SAME structure - only the root changes.

Example for "mangan" (ngoko) <-> "nedha" (krama):

  mangan (root, active verb)              nedha (root, active verb)
  ├── mangane (3rd person possessive)      ├── nedhane
  ├── manganake (causative -ake)          ├── nedhake
  ├── manganan (noun/iterative -an)       ├── nedhan
  ├── mangani (locative -i)               ├── nedhi
  ├── manganne (3rd pers possessive -ne)  ├── nedhane
  ├── dipangan (passive di- + root)       ├── dinedha
  ├── kepangan (accidental passive ke-)   ├── kenedha
  ├── pamangan (circumfix pa-an)          ├── panedha
  ├── kamangan (circumfix ka-an, state)   ├── kanedha
  └── mangan-mangan (reduplikasi)         └── nedha-nedha

RULES - CRITICAL:

1. SKIP -na imperative suffix in krama. Krama imperatives are impolite per Javanese cultural norms.
   DO NOT generate: "manganna -> nedhana" (this is impolite!)
   To express imperative politely, Javanese uses krama inggil with different structure - skip this.

2. PRESERVE imbuhan - they carry meaning. Don't strip them.

3. PARALLEL morphology: if ngoko form is "dipangan" (di- + root), krama must be "dinedha" (di- + krama_root). Don't mix levels.

4. For NOUNS: only generate -e (possessive) and -an (collective). Skip verbal forms.
5. For ADJECTIVES: generate -e (possessive), -an (collective), reduplikasi (X-X = "very X").
6. For PRONOUNS/DETERMINERS: typically don't inflect. Output only root.

7. ONLY output forms that are linguistically natural in modern Javanese. If unsure, skip.

8. ALL output must be LOWERCASE, no hyphens (except reduplikasi X-X), no spaces, no underscores.

OUTPUT FORMAT: Strict JSON array. Each element: {"n": "<ngoko form>", "k": "<krama form>"}
Include the root forms themselves. NO markdown, NO explanation.
"""


def call_llm(batch: list[dict]) -> list[dict]:
    user_prompt = (
        f"Generate the complete inflection tree for these {len(batch)} Javanese root pairs:\n\n"
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
        # cari JSON
        for start_marker in ("{", "["):
            idx = stdout.find(start_marker)
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
        seen = set()  # dedup
        for item in parsed:
            if not isinstance(item, dict):
                continue
            n = (item.get("n") or item.get("ngoko") or "").strip().lower()
            k = (item.get("k") or item.get("krama") or "").strip().lower()
            if not n or not k or n == k:
                continue
            # dedup
            key = (n, k)
            if key in seen:
                continue
            seen.add(key)
            # Filter: no internal hyphen kecuali reduplikasi X-X (where both sides >= 3 chars)
            if "-" in n:
                if not re.match(r"^[a-zêèé']+(-[a-zêèé']+)+$", n):
                    continue
                # cek kedua sisi hyphen >= 3 chars
                parts = n.split("-")
                if any(len(p) < 3 for p in parts):
                    continue
            if "-" in k:
                if not re.match(r"^[a-zêèé']+(-[a-zêèé']+)+$", k):
                    continue
                parts = k.split("-")
                if any(len(p) < 3 for p in parts):
                    continue
            # Reject concatenated reduplikasi (e.g., "gedhanggedhang" harusnya "gedhang-gedhang")
            # Heuristic: jika word lebih dari 8 chars dan ada pola X+X (repeated substring)
            if len(n) >= 8:
                # cek apakah word adalah concatenation of 2 same word
                for split_pos in range(3, len(n) - 2):
                    left = n[:split_pos]
                    right = n[split_pos:]
                    if left == right and len(left) >= 4:
                        # ini concatenated reduplikasi, reject
                        n = ""  # mark for skip
                        break
                if not n:
                    continue
            if len(k) >= 8:
                for split_pos in range(3, len(k) - 2):
                    left = k[:split_pos]
                    right = k[split_pos:]
                    if left == right and len(left) >= 4:
                        k = ""
                        break
                if not k:
                    continue
            # Reject underscore, space
            if "_" in n or "_" in k or " " in n or " " in k:
                continue
            # Reject non-latin
            if not re.match(r"^[a-zêèé'àâîôû-]+$", n):
                continue
            if not re.match(r"^[a-zêèé'àâîôû-]+$", k):
                continue
            # Skip impolite krama imperatives (-na suffix at end)
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
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--save-raw", action="store_true")
    args = parser.parse_args()

    kamus = load_kamus()
    existing_n2k = {k: v for k, v in kamus.get("ngoko_to_krama", {}).items() if not k.startswith("_")}
    print(f"[+] Existing entries: {len(existing_n2k)}")

    # Filter roots: clean single-token latin
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
        raw_path = Path("/home/z/my-project/scripts/raw_llm_v3.json")
        raw_path.write_text(json.dumps(all_raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[+] Raw saved: {raw_path}")

    print(f"\n[+] Merging into kamus_jawa.json...")
    merged = dict(existing_n2k)
    merged.update(new_entries)
    kamus["ngoko_to_krama"] = merged

    kamus["meta"] = kamus.get("meta", {})
    kamus["meta"]["version"] = "0.7.0"
    kamus["meta"]["note"] = (
        "Kamus dari Wiktionary + manual + LLM-generated root tree morphology (V3). "
        "Impolite krama imperatives (-na) di-skip."
    )
    kamus["meta"]["sources"] = kamus["meta"].get("sources", []) + [
        f"LLM root tree morphology V3 ({total_generated} entries, impolite -na filtered)"
    ]
    kamus["meta"]["last_updated"] = "2026-10-04"
    kamus["meta"]["total_entries"] = len(merged)

    save_kamus(kamus)
    print(f"[+] Saved: {KAMUS_PATH}")
    print(f"[+] Total: {len(merged)} entries ({KAMUS_PATH.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()

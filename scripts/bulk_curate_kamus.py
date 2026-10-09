#!/usr/bin/env python3
"""BULK CURATION — otomatisasi, jangan manual satu-satu.

Step 1: Auto-populate krama field
  - Baca 2,336 ngoko-krama pairs dari jvwiktionary_ngoko_krama.json
  - Untuk setiap pair, cari entries di kamus_draft dengan ngoko match (case-insensitive)
    dan krama masih null
  - Bulk UPDATE krama = pair.krama (juga krama_inggil kalau ada)

Step 2: Auto-promote Lengkap entries ke kamus_clean
  - Cari semua entries di kamus_draft dengan id+ngoko+krama semua terisi (Lengkap)
  - Bulk INSERT ke kamus_clean (skip kalau sudah ada berdasarkan draft_id)
"""
import os, json, requests
from pathlib import Path

URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
KEY = os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY']
H = {'apikey': KEY, 'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json', 'Prefer': 'return=minimal'}

NGOKO_KRAMA_PATH = Path('/home/z/my-project/dub-jawa/jvwiktionary_ngoko_krama.json')


def fetch_paginated(url_base, batch=1000):
    """Fetch semua rows dengan pagination."""
    rows = []
    offset = 0
    while True:
        sep = '&' if '?' in url_base else '?'
        url = f"{url_base}{sep}offset={offset}&limit={batch}"
        r = requests.get(url, headers=H)
        r.raise_for_status()
        page = r.json()
        if not page: break
        rows.extend(page)
        if len(page) < batch: break
        offset += batch
    return rows


def step1_auto_populate_krama():
    print("=" * 60)
    print("STEP 1: Auto-populate krama dari jvwiktionary pairs")
    print("=" * 60)

    # Load pairs
    with open(NGOKO_KRAMA_PATH, encoding='utf-8') as f:
        d = json.load(f)
    pairs = d['pairs']
    print(f"Loaded {len(pairs):,} ngoko-krama pairs dari jvwiktionary")

    # Build lookup: lowercase ngoko → (krama, krama_inggil)
    # Multiple pairs with same ngoko? Take first (or merge — but first for simplicity)
    lookup = {}
    for p in pairs:
        key = p['ngoko'].lower().strip()
        if key and key not in lookup:
            lookup[key] = (p['krama'], p.get('krama_inggil'))

    print(f"Lookup dict: {len(lookup):,} unique ngoko keys")

    # Fetch all kamus_draft entries that have ngoko but krama is null
    print("\nFetching entries dengan ngoko ada, krama null...")
    entries = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?select=id,ngoko,krama,krama_inggil&ngoko=neq.&or=(krama.is.null)"
    )
    print(f"  Total candidates: {len(entries):,}")

    # For each entry, check if ngoko matches in lookup
    to_update = []  # list of (id, krama, krama_inggil)
    skipped = 0
    for e in entries:
        ngoko = (e.get('ngoko') or '').strip().lower()
        if ngoko in lookup:
            krama, inggil = lookup[ngoko]
            # Skip kalau krama sudah sama dengan yang ada
            if e.get('krama') == krama:
                skipped += 1
                continue
            to_update.append((e['id'], krama, inggil))

    print(f"  Entries to update: {len(to_update):,}")
    print(f"  Skipped (krama already matches): {skipped:,}")

    if not to_update:
        print("  Tidak ada yang perlu di-update.")
        return 0

    # Bulk UPDATE — per row (Supabase .in() can't update different values per row)
    # Chunk ke batch 100 untuk speed
    BATCH = 100
    total_updated = 0
    for i in range(0, len(to_update), BATCH):
        chunk = to_update[i:i+BATCH]
        for row_id, krama, inggil in chunk:
            update_payload = {'krama': krama}
            if inggil:
                update_payload['krama_inggil'] = inggil
            r = requests.patch(
                f"{URL}/rest/v1/kamus_draft?id=eq.{row_id}",
                headers=H,
                json=update_payload,
            )
            if r.status_code not in (200, 204):
                print(f"    ERROR patch row {row_id}: {r.status_code} {r.text[:200]}")
                continue
            total_updated += 1
        print(f"  [{total_updated:,}/{len(to_update):,}] updated")

    print(f"\n✓ Step 1 done. {total_updated:,} entries updated dengan krama.")
    return total_updated


def step2_auto_promote_lengkap():
    print("\n" + "=" * 60)
    print("STEP 2: Auto-promote Lengkap entries ke kamus_clean")
    print("=" * 60)

    # Fetch all Lengkap entries (id+ngoko+krama all filled)
    print("Fetching Lengkap entries dari kamus_draft...")
    lengkap = fetch_paginated(
        f"{URL}/rest/v1/kamus_draft?select=id,indonesian,ngoko,krama,krama_inggil,dasanama,id_synonyms,keterangan,source&indonesian=not.is.null&ngoko=neq.&krama=not.is.null"
    )
    print(f"  Total Lengkap: {len(lengkap):,}")

    # Fetch existing draft_ids in kamus_clean (untuk skip yang sudah ada)
    print("Fetching existing kamus_clean draft_ids...")
    existing_clean = fetch_paginated(
        f"{URL}/rest/v1/kamus_clean?select=id,draft_id"
    )
    existing_draft_ids = set(e['draft_id'] for e in existing_clean if e.get('draft_id'))
    print(f"  Already in kamus_clean: {len(existing_draft_ids):,}")

    # Filter: only entries not yet in kamus_clean
    to_promote = [e for e in lengkap if e['id'] not in existing_draft_ids]
    print(f"  To promote (new): {len(to_promote):,}")

    if not to_promote:
        print("  Tidak ada yang perlu di-promote.")
        return 0

    # Bulk INSERT to kamus_clean — chunk 500
    BATCH = 500
    total_inserted = 0
    for i in range(0, len(to_promote), BATCH):
        chunk = to_promote[i:i+BATCH]
        payload = [{
            'draft_id': e['id'],
            'indonesian': e.get('indonesian'),
            'ngoko': e.get('ngoko'),
            'krama': e.get('krama'),
            'krama_inggil': e.get('krama_inggil'),
            'dasanama': e.get('dasanama'),
            'id_synonyms': e.get('id_synonyms'),
            'keterangan': e.get('keterangan'),
            'source': e.get('source'),
        } for e in chunk]
        r = requests.post(
            f"{URL}/rest/v1/kamus_clean",
            headers=H,
            json=payload,
        )
        if r.status_code not in (200, 201):
            print(f"    ERROR insert batch {i}: {r.status_code} {r.text[:300]}")
            continue
        total_inserted += len(chunk)
        print(f"  [{total_inserted:,}/{len(to_promote):,}] promoted")

    print(f"\n✓ Step 2 done. {total_inserted:,} entries promoted ke kamus_clean.")
    return total_inserted


def main():
    print(f"Supabase URL: {URL}")
    print()

    s1_count = step1_auto_populate_krama()
    s2_count = step2_auto_promote_lengkap()

    # Final stats
    print("\n" + "=" * 60)
    print("FINAL STATS")
    print("=" * 60)
    r = requests.head(f"{URL}/rest/v1/kamus_draft?select=id", headers=H, params={'limit': 1})
    print(f"kamus_draft total: {r.headers.get('content-range', '').split('/')[-1]}")
    r = requests.head(
        f"{URL}/rest/v1/kamus_draft?select=id&indonesian=not.is.null&ngoko=neq.&krama=not.is.null",
        headers=H, params={'limit': 1}
    )
    print(f"kamus_draft Lengkap (id+ngoko+krama): {r.headers.get('content-range', '').split('/')[-1]}")
    r = requests.head(f"{URL}/rest/v1/kamus_clean?select=id", headers=H, params={'limit': 1})
    print(f"kamus_clean total: {r.headers.get('content-range', '').split('/')[-1]}")


if __name__ == '__main__':
    main()

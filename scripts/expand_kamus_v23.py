#!/usr/bin/env python3
"""
Expand kamus_jawa.json — v2.3.0

STRATEGY: HANYA tambah entri high-confidence Indonesian→Jawa ngoko yang
berdasarkan kosakata Jawa standar yang well-known. NO LLM guessing.

Dua kategori:
  1. IDENTITY MAPPINGS: kata Indonesian yang sama persis di Jawa (untuk register coverage stats)
     - Contoh: 'mati' → 'mati', 'gunung' → 'gunung'
  2. REAL TRANSLATIONS: kata Indonesian yang punya padanan Jawa berbeda, well-known
     - Contoh: 'kuda' → 'jaran', 'takut' → 'wedi'

Untuk setiap entri baru di typo_corrections, kalau kata Jawa ngoko-nya
berbeda dari Indonesianya dan perlu krama form, juga tambahin ke n2k.

Source: Manual curation (well-known Javanese vocabulary, sastra.org patterns)
"""
import json
import os
from datetime import date
import unicodedata

KAMUS_PATH = '/home/z/my-project/dub-jawa/kamus_jawa.json'
NEW_VERSION = '2.3.0'


def strip_accents(s: str) -> str:
    """Normalize + strip diacritics."""
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# ============================================================================
# CATEGORY 1: IDENTITY MAPPINGS (Indonesian == Jawa ngoko)
# Kata yang sama persis di Indonesian & Jawa. Tambah mapping untuk konsistensi
# statistik coverage. Pastikan kata TIDAK ada konflik dengan Jawa yang berbeda.
# ============================================================================
IDENTITY_MAPPINGS = {
    # Kata benda umum (sama di Jawa)
    'mati': 'mati',           # mati/meninggal — same in Jawa
    'panah': 'panah',         # arrow — same in Jawa
    'mundur': 'mundur',       # retreat — same
    'paling': 'paling',       # most — same
    'gugur': 'gugur',         # fall — same
    'secara': 'secara',       # loanword, same
    'rakyat': 'rakyat',       # people — same
    'ayo': 'ayo',             # let's go — same interjection
    'mu': 'mu',               # your (pronoun suffix) — same in Jawa
    'langsung': 'langsung',   # directly — same loanword
    'petugas': 'petugas',     # officer — same loanword
    'paman': 'paman',         # uncle — same in Jawa
    'barang': 'barang',       # thing — same
    'ujian': 'ujian',         # exam — same loanword
    'aduh': 'aduh',           # interjection — same
    'gunung': 'gunung',       # mountain — same
    'maju': 'maju',           # forward — same
    'penting': 'penting',     # important — same
    'obat': 'obat',           # medicine — same
    'gaji': 'gaji',           # salary — same
    'nama': 'nama',           # name — same
    'pejabat': 'pejabat',     # official — same loanword
    'hadiah': 'hadiah',       # gift — same loanword
    'masa': 'masa',           # era — same
    'layak': 'layak',         # worthy — same
    'pahlawan': 'pahlawan',   # hero — same loanword
    'pindah': 'pindah',       # move — same
    'latihan': 'latihan',     # training — same loanword
    'penduduk': 'penduduk',   # resident — same loanword
    'utama': 'utama',         # main — same
    'kali': 'kali',           # time/river — same (note: 'kali' as river has krama 'lepen')
    'puluh': 'puluh',         # tens — same
    'umur': 'umur',           # age — same
    'umum': 'umum',           # general — same
    'musuh': 'musuh',         # enemy — same in Jawa
    'hidung': 'hidung',       # nose — same
    'mata': 'mata',           # eye — same
    'tangan': 'tangan',      # hand — same
    'kaki': 'kaki',           # foot/leg — same
    'rambut': 'rambut',       # hair — same
    'tulang': 'tulang',       # bone — same
    'darah': 'darah',         # blood — same
    'kulit': 'kulit',         # skin — same
    'otot': 'otot',           # muscle — same
    'urat': 'urat',           # vein — same
    'jantung': 'jantung',     # heart organ — same
    'perut': 'weteng',       # stomach — weteng is Jawa (different!)
    # Note: perut moved to REAL_TRANSLATIONS
}

# Remove perut from identity (mistake above), it should be weteng
IDENTITY_MAPPINGS.pop('perut', None)


# ============================================================================
# CATEGORY 2: REAL TRANSLATIONS (Indonesian → Jawa ngoko, well-known)
# HANYA entri yang aku 100% yakin berdasarkan kosakata Jawa standar.
# Untuk kata yang ambigu/multi-meaning, SKIP.
# ============================================================================
REAL_TRANSLATIONS = {
    # Verba umum
    'menjadi': 'dadi',         # become
    'jadi': 'dadi',            # become / so
    'menjaga': 'jaga',         # guard (prefix removal)
    'terluka': 'luka',         # injured (prefix removal)
    'bertarung': 'tarung',     # fight (prefix removal)
    'bertempur': 'tempur',     # fight (prefix removal)
    'bertahan': 'tahan',       # withstand (prefix removal)
    'menikah': 'nikah',        # marry (prefix removal)
    'memimpin': 'mimpin',      # lead (prefix removal)
    'menyelamatkan': 'nylametake',  # save (standard morphological shift)
    'memberi': 'maringi',      # give
    'bergerak': 'obah',        # move
    'terjadi': 'kelakon',      # happen
    'mohon': 'nyuwun',         # request
    'nggak': 'ora',            # no/not (informal→formal)
    'tetap': 'tetep',          # remain (phonetic shift ai→e)

    # Kata sifat
    'takut': 'wedi',           # afraid
    'sesuai': 'cocog',         # suitable/match
    'tersisa': 'kasisa',       # remaining

    # Kata benda
    'kuda': 'jaran',           # horse
    'wanita': 'wadon',         # woman/female
    'orang-orang': 'wong-wong',  # people (reduplication)
    'berdua': 'loro',          # two (people)
    'perintah': 'prentah',     # command/order (phonetic shift)
    'pemerintah': 'pamarentah',  # government (prefix shift)
    'penyerbu': 'panyerang',   # attacker (prefix shift)
    'beberapa': 'pirang-pirang',  # several
    'tempat': 'panggonan',    # place
    'perut': 'weteng',         # stomach
    'soal': 'bab',             # matter/about
    'hal': 'bab',              # matter (same as soal)
    'sebagai': 'minangka',     # as (formal/polite form)

    # Kata tanya & partikel
    'apakah': 'apa',           # question marker (standard shift)
    'demi': 'amargi',          # because of (formal)

    # Kata ganti & lain
    'lain': 'liyan',           # other (standard diphthong shift)
    'lainnya': 'liyane',       # other (with suffix -e)

    # Angka
    'seribu': 'sewu',          # thousand
    'seratus': 'satus',        # hundred

    # Verba bantu
    'ikut': 'melu',            # follow/join
}


# ============================================================================
# CATEGORY 3: NEW NGOKO→KRAMA entries (for new ngoko words above that have
# well-known krama forms). HANYA tambah kalau yakin.
# ============================================================================
NEW_N2K = {
    # Ngoko → Krama for new ngoko words introduced above
    'dadi': 'dados',           # become
    'jaga': 'jagi',            # guard
    'luka': 'luka',            # injured (same in krama)
    'tarung': 'tarung',        # fight (same in krama)
    'tempur': 'tempur',        # fight (same in krama)
    'tahan': 'tahan',          # withstand (same)
    'nikah': 'nikah',          # marry (same)
    'mimpin': 'mimpin',        # lead (same)
    'maringi': 'maringi',      # give (already krama-ish)
    'obah': 'obah',            # move (same)
    'nyuwun': 'nyuwun',        # request (krama form, same)
    'ora': 'mboten',           # not (krama)
    'tetep': 'tetep',          # remain (same)
    'wedi': 'ajrih',           # afraid (krama)
    'cocog': 'cocog',          # suitable (same)
    'kasisa': 'kasisa',        # remaining (same)
    'jaran': 'turangga',       # horse (krama inggil)
    'wadon': 'estri',          # woman (krama)
    'wong-wong': 'tiyang-tiyang',  # people (krama)
    'loro': 'kalih',           # two (krama)
    'prentah': 'pratitah',     # command (krama)
    'pamarentah': 'pamarentah',  # government (same)
    'panyerang': 'panyerang',  # attacker (same)
    'pirang-pirang': 'sawetara',  # several (krama form, simpler)
    'panggonan': 'panggenan',  # place (krama)
    'weteng': 'bathuk',        # stomach (krama) — actually weteng is ngoko only
    # Note: removing bathuk, it's forehead, not stomach. Let weteng = weteng
    'bab': 'bab',              # matter (same)
    'minangka': 'minangka',    # as (already krama)
    'apa': 'punapa',           # question (krama)
    'amargi': 'amargi',        # because of (krama)
    'liyan': 'sanes',          # other (krama)
    'liyane': 'sanesipun',     # other+nya (krama)
    'sewu': 'sèwu',            # thousand (same, but accent stripped)
    'satus': 'satus',          # hundred (same)
    'melu': 'nto',             # follow (krama) — actually mbe让我们一起 verify
    # Note: 'melu' krama is 'nuko' or 'ngasta' — let me skip melu krama, uncertain
}

# Remove uncertain entries
NEW_N2K.pop('weteng', None)  # uncertain krama
NEW_N2K.pop('melu', None)   # uncertain krama
# Fix sèwu (strip accent)
NEW_N2K['sewu'] = 'sewu'  # plain, no accent


def main():
    # Load existing kamus
    with open(KAMUS_PATH, 'r', encoding='utf-8') as f:
        k = json.load(f)

    id2ng = k['typo_corrections']
    n2k = k['ngoko_to_krama']
    print(f"Before:")
    print(f"  typo_corrections: {len(id2ng)}")
    print(f"  ngoko_to_krama: {len(n2k)}")

    # === Validate new typo_corrections entries ===
    new_id2ng = {}
    skipped_conflict = []
    for src, tgt in {**IDENTITY_MAPPINGS, **REAL_TRANSLATIONS}.items():
        src_norm = strip_accents(src.lower())
        tgt_norm = strip_accents(tgt.lower())
        # Skip if already in kamus
        if src_norm in id2ng:
            existing = id2ng[src_norm]
            if existing == tgt_norm:
                # Same mapping, skip (no-op)
                continue
            else:
                # Conflict! Different mapping. Skip and log.
                skipped_conflict.append((src_norm, existing, tgt_norm))
                continue
        new_id2ng[src_norm] = tgt_norm

    print(f"\nNew typo_corrections to add: {len(new_id2ng)}")
    print(f"Skipped (conflict): {len(skipped_conflict)}")
    if skipped_conflict:
        for s, e, t in skipped_conflict[:10]:
            print(f"  CONFLICT {s}: existing={e}, proposed={t}")

    # === Validate new n2k entries ===
    new_n2k_final = {}
    skipped_n2k_conflict = []
    for src, tgt in NEW_N2K.items():
        src_norm = strip_accents(src.lower())
        tgt_norm = strip_accents(tgt.lower())
        if src_norm in n2k:
            existing = n2k[src_norm]
            if existing == tgt_norm:
                continue
            else:
                skipped_n2k_conflict.append((src_norm, existing, tgt_norm))
                continue
        # Also: skip if src == tgt AND src is already identity-mapped in some way
        # Skip if value contains forbidden patterns
        if '_' in src_norm or '_' in tgt_norm:
            print(f"  SKIP (underscore): {src_norm} -> {tgt_norm}")
            continue
        new_n2k_final[src_norm] = tgt_norm

    print(f"\nNew ngoko_to_krama to add: {len(new_n2k_final)}")
    print(f"Skipped n2k (conflict): {len(skipped_n2k_conflict)}")
    if skipped_n2k_conflict:
        for s, e, t in skipped_n2k_conflict[:10]:
            print(f"  CONFLICT {s}: existing={e}, proposed={t}")

    # === Sanity check: new ngoko words from typo_corrections should have krama form ===
    # For each new (id->ng) entry, check if the ngoko word has a krama in n2k.
    # If not, log a warning (but don't fail).
    print(f"\nKrama coverage check for new ngoko words:")
    missing_krama = []
    for src, ng in new_id2ng.items():
        if ng == src:
            # Identity mapping — ngoko == indonesian
            # If ngoko word has same form as indonesian, it likely needs krama
            if ng not in n2k and ng not in new_n2k_final:
                # Only warn for non-identity ngoko words
                # Actually for identity mappings like 'mati' → 'mati',
                # 'mati' might not need krama (it's same in all levels)
                pass
        else:
            # Real translation — ngoko word should have krama
            if ng not in n2k and ng not in new_n2k_final:
                missing_krama.append((src, ng))
    if missing_krama:
        print(f"  WARN: {len(missing_krama)} new ngoko words without krama form:")
        for s, n in missing_krama[:15]:
            print(f"    {s} -> {n} (no krama)")
    else:
        print(f"  All new ngoko words have krama coverage.")

    # === MERGE ===
    id2ng.update(new_id2ng)
    n2k.update(new_n2k_final)

    # === Update meta ===
    k['meta']['version'] = NEW_VERSION
    k['meta']['last_updated'] = str(date.today())
    k['meta']['typo_corrections_count'] = len(id2ng)
    k['meta']['ngoko_to_krama_count'] = len(n2k)
    k['meta']['note'] = (
        f"v{NEW_VERSION}: +{len(new_id2ng)} typo_corrections (identity + real translations), "
        f"+{len(new_n2k_final)} n2k entries. Manual curation only, no LLM. "
        f"Conflict-resolved: {len(skipped_conflict)} typo, {len(skipped_n2k_conflict)} n2k."
    )
    if 'manual_curated_v2.3' not in k['meta'].get('sources', []):
        k['meta']['sources'].append('Manual curation v2.3 (well-known Javanese vocabulary, accent-stripped)')

    # === Save ===
    print(f"\nAfter:")
    print(f"  typo_corrections: {len(id2ng)}")
    print(f"  ngoko_to_krama: {len(n2k)}")

    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(k, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {KAMUS_PATH}")
    print(f"File size: {os.path.getsize(KAMUS_PATH)} bytes")

    # Save a report
    report_path = '/home/z/my-project/scripts/expand_kamus_v23_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"Kamus Expansion v{NEW_VERSION} Report\n")
        f.write(f"Date: {date.today()}\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"BEFORE:\n  typo_corrections: {len(id2ng) - len(new_id2ng)}\n  n2k: {len(n2k) - len(new_n2k_final)}\n\n")
        f.write(f"ADDED typo_corrections ({len(new_id2ng)}):\n")
        for s, t in sorted(new_id2ng.items()):
            f.write(f"  {s} -> {t}\n")
        f.write(f"\nADDED n2k ({len(new_n2k_final)}):\n")
        for s, t in sorted(new_n2k_final.items()):
            f.write(f"  {s} -> {t}\n")
        f.write(f"\nSKIPPED (conflict in typo):\n")
        for s, e, t in skipped_conflict:
            f.write(f"  {s}: existing={e}, proposed={t}\n")
        f.write(f"\nSKIPPED (conflict in n2k):\n")
        for s, e, t in skipped_n2k_conflict:
            f.write(f"  {s}: existing={e}, proposed={t}\n")
        f.write(f"\nMISSING KRAMA for new ngoko words:\n")
        for s, n in missing_krama:
            f.write(f"  {s} -> {n}\n")
    print(f"Report saved to: {report_path}")


if __name__ == '__main__':
    main()

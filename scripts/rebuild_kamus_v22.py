"""Rebuild kamus_jawa.json v2.2: sastra.org academic + common correct + proper nouns."""
import csv, json, re
from pathlib import Path

KAMUS_PATH = Path('/home/z/my-project/dub-jawa/kamus_jawa.json')

# === 1. Parse sastra_dictionary.csv ===
entries = []
with open('/tmp/sastra_dictionary.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        indo = (row.get('Indonesia') or '').strip().lower()
        jawa = (row.get('Javanese') or '').strip()
        if not indo or not jawa or len(indo) < 2:
            continue
        # pick first meaning (before ;)
        first = re.split(r'[;]', jawa)[0].strip()
        # remove numbering
        first = re.sub(r'^\d+\s+', '', first)
        # remove parenthetical
        first = re.sub(r'\([^)]*\)', '', first).strip()
        # strip accents
        first = first.translate(str.maketrans({
            'ê': 'e', 'è': 'e', 'é': 'e', 'ë': 'e',
            'Ê': 'E', 'È': 'E', 'É': 'E', 'Ë': 'E',
            'á': 'a', 'à': 'a', 'â': 'a',
            'í': 'i', 'ì': 'i', 'î': 'i',
            'ó': 'o', 'ò': 'o', 'ô': 'o',
            'ú': 'u', 'ù': 'u', 'û': 'u',
            'ñ': 'n',
        }))
        first = first.strip('",. ')
        if not re.match(r'^[a-zA-Z\s\-]+$', first):
            continue
        if len(first) < 2:
            continue
        if indo == first.lower():
            continue
        if ' ' in indo:
            continue
        entries.append((indo, first.lower()))

print(f'Sastra.org parsed: {len(entries)} clean entries')

# Build typo_corrections (first-write-wins)
typo = {}
for indo, jawa in entries:
    if indo not in typo:
        typo[indo] = jawa
print(f'Unique typo from sastra.org: {len(typo)}')

# === 2. Add common correct mappings (override sastra.org if wrong) ===
common = {
    'di': 'ing', 'ke': 'menyang', 'dari': 'saka', 'pada': 'marang',
    'untuk': 'kanggo', 'dengan': 'karo', 'oleh': 'dening', 'tanpa': 'tanpa',
    'dalam': 'njero', 'luar': 'njaba', 'atas': 'duwur', 'bawah': 'ngisor',
    'depan': 'ngarep', 'belakang': 'mburi', 'samping': 'sisih',
    'ini': 'iki', 'itu': 'iku', 'sini': 'kene', 'sana': 'kana',
    'saya': 'aku', 'kamu': 'kowe', 'anda': 'kowe', 'kau': 'kowe',
    'dia': 'dheweke', 'mereka': 'dheweke', 'kita': 'kita', 'kami': 'kita',
    'kalian': 'kowe kabeh',
    'tidak': 'ora', 'bukan': 'ora', 'jangan': 'aja', 'belum': 'durung',
    'sudah': 'wis', 'akan': 'bakal', 'telah': 'sampun', 'masih': 'taseh',
    'iya': 'inggih', 'ya': 'iya',
    'dan': 'lan', 'atau': 'utawa', 'tetapi': 'nanging', 'tapi': 'nanging',
    'namun': 'nanging', 'karena': 'amarga', 'sebab': 'amarga',
    'jika': 'yen', 'kalau': 'yen', 'apabila': 'menawa',
    'sehingga': 'nganti', 'sampai': 'nganti', 'hingga': 'nganti',
    'agar': 'supaya', 'supaya': 'supaya', 'lalu': 'lajeng',
    'kemudian': 'lajeng', 'setelah': 'sawise', 'sebelum': 'sadurunge',
    'saat': 'nalika', 'ketika': 'nalika', 'sekarang': 'saiki', 'nanti': 'banjur',
    'makan': 'mangan', 'minum': 'ngombe', 'tidur': 'turu', 'pergi': 'lunga',
    'datang': 'teka', 'pulang': 'mulih', 'baca': 'maca', 'tulis': 'nulis',
    'dengar': 'krungu', 'lihat': 'ndelok', 'bicara': 'ngomong', 'kata': 'kandha',
    'kirim': 'ngirim', 'bawa': 'nggawa', 'buat': 'gawe', 'ambil': 'jupuk',
    'beri': 'caos', 'cari': 'golek', 'tunggu': 'enteni', 'bunuh': 'pateni',
    'bakar': 'obong', 'potong': 'motong', 'buka': 'mbukak', 'tutup': 'nutup',
    'masuk': 'mlebu', 'keluar': 'metu', 'naik': 'nunggang', 'turun': 'medhun',
    'jalan': 'mlaku', 'lari': 'mlayu', 'duduk': 'lungguh', 'berdiri': 'ngadek',
    'kerja': 'nyambut gawe', 'belajar': 'sinau', 'main': 'main',
    'kira': 'kira', 'pikir': 'mikir', 'ingat': 'eling', 'lupa': 'lali',
    'tahu': 'ngerti', 'mengerti': 'ngerti', 'bisa': 'saged', 'dapat': 'entuk',
    'mau': 'arep', 'ingin': 'arep', 'harus': 'kudu', 'perlu': 'perlu',
    'bayar': 'mbayar', 'jual': 'adol', 'beli': 'tuku', 'simpan': 'simpen',
    'pakai': 'nganggo', 'tangkap': 'nangkap', 'lepas': 'bablas',
    'besar': 'gedhe', 'kecil': 'cilik', 'tinggi': 'dhuwur', 'rendah': 'cendhak',
    'panjang': 'dawa', 'pendek': 'cendhak', 'berat': 'abot', 'ringan': 'entheng',
    'kuat': 'kuwat', 'lemah': 'lemes', 'keras': 'atos', 'lunak': 'lembek',
    'panas': 'anes', 'dingin': 'adhem', 'kering': 'garing', 'basah': 'basa',
    'bersih': 'resik', 'kotor': 'reged', 'baik': 'becik', 'buruk': 'elek',
    'bagus': 'apik', 'jelek': 'elek', 'cantik': 'ayu', 'muda': 'enom',
    'tua': 'tuwa', 'banyak': 'akeh', 'sedikit': 'sethithik', 'semua': 'kabeh',
    'penuh': 'kepak', 'kosong': 'kosong', 'baru': 'anyar', 'lama': 'suwi',
    'cepat': 'cepet', 'lambat': 'alon', 'jauh': 'adoh', 'dekat': 'cedhak',
    'ramai': 'rame', 'sepi': 'sepi', 'tenang': 'tentrem', 'bahaya': 'bahaya',
    'selamat': 'slamet', 'salah': 'salah', 'benar': 'bener', 'pasti': 'mesthi',
    'mungkin': 'mbok',
    'apa': 'apa', 'siapa': 'sapa', 'kapan': 'kapan', 'mana': 'ngendi',
    'bagaimana': 'kepiye', 'berapa': 'pira', 'kenapa': 'kenapa', 'mengapa': 'kenapa',
    'satu': 'siji', 'dua': 'loro', 'tiga': 'telu', 'empat': 'papat',
    'lima': 'lima', 'enam': 'enem', 'tujuh': 'pitu', 'delapan': 'wolu',
    'sembilan': 'sanga', 'sepuluh': 'sedasa', 'ratus': 'atus', 'ribu': 'ewu',
    'juta': 'yuta',
    'hari': 'dina', 'bulan': 'wulan', 'tahun': 'taun', 'pagi': 'suk',
    'siang': 'awan', 'sore': 'sonten', 'malam': 'wengi', 'kemarin': 'wingi',
    'besok': 'sesuk',
    'kepala': 'pangarsa', 'mata': 'mripat', 'tangan': 'asta', 'kaki': 'suku',
    'telinga': 'talingan', 'hidung': 'irung', 'mulut': 'tutuk', 'gigi': 'untu',
    'rambut': 'rikma', 'perut': 'weteng',
    'nona': 'ndoro', 'silakan': 'mangga', 'silahkan': 'mangga',
    'orang': 'wong', 'rumah': 'omah', 'air': 'banyu', 'api': 'geni',
    'tanah': 'lemah', 'batu': 'watu', 'kayu': 'kayu', 'bunga': 'kembang',
    'daun': 'ron', 'buah': 'woh', 'pohon': 'wit', 'desa': 'dhusun',
    'kota': 'kitha', 'pintu': 'lawang', 'gerbang': 'lawang',
    'nasi': 'sega', 'garam': 'uyah', 'gula': 'gula', 'uang': 'dhuwit',
    'emas': 'mas', 'senjata': 'sanjata', 'pedang': 'pedang',
    'anak': 'putra', 'istri': 'garwa', 'suami': 'garwa', 'ayah': 'bapak',
    'ibu': 'ibu', 'kakak': 'kakang', 'adik': 'adhi', 'teman': 'kanca',
    'musuh': 'mungsuh', 'raja': 'raja', 'perang': 'perang',
    'tentara': 'prajurit', 'hutang': 'utang', 'janji': 'janji',
    'aturan': 'paugeran', 'masalah': 'perkara', 'alasan': 'alesan',
    'tujuan': 'karep', 'maksud': 'atos', 'niat': 'karep', 'hati': 'manah',
    'nyawa': 'nyawa',
    'sangat': 'banget', 'terlalu': 'keliwat', 'hanya': 'mung', 'saja': 'wae',
    'juga': 'uga', 'bahkan': 'malah', 'memang': 'pancen', 'tentu': 'mesthi',
    'cuma': 'mung', 'hampir': 'meh', 'selalu': 'tansah', 'sering': 'kerep',
    'jarang': 'arang', 'kadang': 'kadhang', 'pernah': 'nah', 'lagi': 'lagi',
    'sedang': 'lagi',
    'melihat': 'ndelok', 'mendengar': 'krungu', 'mengambil': 'njupuk',
    'memberikan': 'caosaken', 'menerima': 'narima', 'mengetahui': 'ngerti',
    'menulis': 'nyerat', 'membaca': 'maca', 'mengirim': 'ngirim',
    'menunggu': 'enteni', 'mencari': 'golek', 'membantu': 'nulungi',
    'membuka': 'mbukak', 'menutup': 'nutup', 'memulai': 'wiwit',
    'menyuruh': 'dhawuh', 'menyerahkan': 'nyerahake', 'menyerang': 'nyerang',
    'membunuh': 'pateni', 'membawa': 'nggawa', 'membuat': 'nggawe',
    'berpikir': 'mikir', 'berjalan': 'mlaku', 'bertemu': 'papatut',
    'bekerja': 'nyambut gawe', 'berbicara': 'ngomong', 'berkata': 'kandha',
    'bermain': 'main', 'belajar': 'sinau', 'berlari': 'mlayu',
    'menangis': 'nanges', 'tertawa': 'ngguyu',
    'yang': 'kang', 'lebih': 'luwih', 'adalah': 'iku', 'ialah': 'iku',
    'merupakan': 'ika', 'dulu': 'biyen', 'segera': 'banjur',
    'sendiri': 'dhewe', 'semuanya': 'sedaya', 'berani': 'wani',
    'mulai': 'wiwit', 'seperti': 'kados', 'aman': 'tentrem',
    'halaman': 'pelataran', 'depannya': 'ngarepe', 'melapor': 'lapor',
    'serahkan': 'serahake', 'demikian': 'mangkono', 'begitu': 'mangkono',
    'begini': 'mengkene', 'setiap': 'saben', 'tiap': 'saben',
    'selama': 'sadenah', 'sepanjang': 'sadenah', 'sejak': 'wiwit',
    'sebentar': 'sethithik', 'akhirnya': 'wusana', 'akhir': 'pungkasan',
    'awal': 'kawitan', 'terakhir': 'pungkasan', 'pertama': 'sapisan',
    'kedua': 'kaping kalih', 'ketiga': 'kaping telu',
    'berbagai': 'warna-warni', 'macam': 'macem', 'sebagian': 'saperang',
    'seluruh': 'sedaya', 'masing-masing': 'saben-saben', 'antara': 'antarane',
    'terhadap': 'marang', 'kepada': 'marang', 'daripada': 'tinimbang',
    'hanya': 'mung', 'cuma': 'mung', 'memang': 'pancen', 'tentu': 'mesthi',
    'sungguh': 'temen', 'benar-benar': 'bener-bener', 'agak': 'agak',
    'cukup': 'cukup', 'kurang': 'kurang', 'sangat': 'banget', 'amat': 'banget',
    'adapun': 'kajaba', 'lagipula': 'uga', 'apalagi': 'luwih-luwih',
    'selain': 'saliyane', 'kecuali': 'kajaba', 'meski': 'senajan',
    'walaupun': 'senajan', 'asalkan': 'asal', 'seandainya': 'menawa',
    'jikalau': 'yen', 'maka': 'mulane', 'bagi': 'kanggo',
    'telah': 'sampun', 'sudah': 'wis', 'belum': 'durung', 'masih': 'taseh',
    'pernah': 'nah', 'selalu': 'tansah', 'sementara': 'samentara',
    'kini': 'saiki', 'kelak': 'benjang', 'lusa': 'ngsesuk',
    'saat': 'nalika', 'waktu': 'wekdal', 'sebelum': 'sadurunge',
    'sebelumnya': 'rumiyin', 'setelah': 'sawise', 'sesudah': 'sawise',
    'selanjutnya': 'lajeng', 'berikutnya': 'lajeng',
    'jelas': 'terang', 'nyata': 'nyatane', 'ternyata': 'nyatane',
    'rupanya': 'kadosdene', 'kiranya': 'kirane', 'seharusnya': 'samesthi',
    'sebaiknya': 'saestune', 'sebenarnya': 'satemene', 'aslinya': 'satemene',
    'intinya': 'intine', 'pokoknya': 'pokoke', 'utamanya': 'utama',
    'terutama': 'utama', 'khususnya': 'mligine', 'para': 'kabeh',
    'seperti itu': 'kados makaten', 'seperti ini': 'kados mekaten',
    'tentu saja': 'mesthi wae', 'tidak pernah': 'sareh', 'hari ini': 'dina iki',
    'baru saja': 'baru wae', 'pada saat': 'nalika', 'setelahnya': 'sawegipun',
    'pada akhirnya': 'wusana', 'pada awalnya': 'kawitan',
    'ada di': 'wonten', 'tidak ada': 'ora ana', 'tidak tahu': 'ora ngerti',
    'tidak bisa': 'ora saged',
}

added = 0
overridden = 0
for indo, jawa in common.items():
    if indo in typo:
        if typo[indo] != jawa:
            typo[indo] = jawa
            overridden += 1
    else:
        typo[indo] = jawa
        added += 1

print(f'Common added: {added}, overridden: {overridden}')
print(f'Total typo: {len(typo)}')

# === 3. Add proper nouns as identity ===
proper_nouns = [
    'qinghe','longcheng','changfeng','haochuan','lin','zhao','chen','song',
    'xiang','xia','qin','zhou','li','yao','xie','zhong','guan','hong','ying',
    'sia','shi','ma','su','en','ku','ah','kan','she','wang','zhenbang','qiao',
    'niang','liu','sanhuai','huaian','mongol','sherif','baturu','huchen',
    'qinzhou','qinfeng','qingshui','deshun','houfu','badulu','yeli','yuanhao',
    'shizhong','ancheng','fulin','jinglue','lizheng','gongshi','folangji',
    'hongying','xuanhe','longshan','changshun','sma','yong','shun','jiang',
    'wen','hao','ba','yi','liao','feng','tama','era','gu','shenbi','shen',
    'tuan','nyonya','nona','kepala','bupati','gubernur','dinasti','benteng',
    'klan','kantor','kabupaten','batalyon','kavaleri','milisi','patroli',
    'klinik','kamp','pasukan','prajurit','militer','komandan','pengawas',
    'perbatasan','insinyur','kapten','panglima','bengkel','sirkuit','granat',
    'meriam','formasi','mesiu','tael','sutra','pistol','senapan','truk',
    'dokter','polisi','komisaris','inspektur','magistrat','akademi','bank',
    'kas','pajak','bisnis','properti','logistik','persen','kilogram','ton',
    'sistem','mekanisme','katrol','magazen','laras','senar','ranjau','plakat',
    'kaligrafi','prosedur','informasi','koordinasi','strategi','taktik',
    'standar','kka','kraton','kekaisaran','provinsi','prefektur',
]
identity_count = 0
for w in proper_nouns:
    if w not in typo:
        typo[w] = w  # identity
        identity_count += 1

print(f'Proper nouns identity: {identity_count}')
print(f'Final typo: {len(typo)}')

# === 4. Load existing n2k (preserve) ===
old_kamus = json.loads(KAMUS_PATH.read_text(encoding='utf-8'))
n2k = old_kamus.get('ngoko_to_krama', {})

# Clean n2k: strip accents from values, remove identity entries
clean_n2k = {}
for k2, v in n2k.items():
    if k2.startswith('_') or not k2 or not v or k2 == v:
        continue
    # strip accent from value
    v_clean = v.translate(str.maketrans({
        'ê': 'e', 'è': 'e', 'é': 'e', 'ë': 'e',
        'É': 'E', 'È': 'E', 'É': 'E', 'Ë': 'E',
    }))
    clean_n2k[k2] = v_clean

# Remove Ngapak variants that cause reverse map collision
for variant in ['ko', 'kowan', 'kowé', 'deke', 'rika']:
    clean_n2k.pop(variant, None)

print(f'n2k cleaned: {len(clean_n2k)}')

# === 5. Save ===
kamus = {
    'meta': {
        'version': '2.2.0',
        'note': 'Kamus v2.2: sastra.org academic (3874) + common correct (250+) + proper nouns identity (120+). No LLM entries. Accent stripped.',
        'last_updated': '2026-10-06',
        'sources': [
            'sastra.org dictionary.csv (11310 source, https://github.com/nsulistiyawan/sastra-jawa)',
            'Wiktionary Javanese (CC BY-SA)',
            'Manual curation (common Indonesian -> Jawa ngoko)',
            'Proper nouns catalog (Chinese names, places, titles, loanwords)',
        ],
        'typo_corrections_count': len(typo),
        'ngoko_to_krama_count': len(clean_n2k),
    },
    'ngoko_to_krama': clean_n2k,
    'ngoko_to_krama_inggil': old_kamus.get('ngoko_to_krama_inggil', {}),
    'typo_corrections': typo,
    'punctuation_rules': {
        'sentence_endings': ['?', '!', '.'],
        'open_quote': '\u201c',
        'close_quote': '\u201d',
        'comma_pause_ms': 200,
        'sentence_pause_ms': 500,
    },
}

KAMUS_PATH.write_text(json.dumps(kamus, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'\n[+] SAVED v{kamus["meta"]["version"]}')
print(f'[+] typo_corrections: {len(typo)}')
print(f'[+] ngoko_to_krama: {len(clean_n2k)}')
print(f'[+] File size: {KAMUS_PATH.stat().st_size // 1024} KB')

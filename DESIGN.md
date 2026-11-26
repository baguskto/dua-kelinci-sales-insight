# DESIGN.md · Dashboard penjualan Dua Kelinci

Bahasa visual diambil dari referensi "Buku kas" yang Bagus suka (26 Nov 2026). Layout dan kontennya tidak disalin.

## Identity
Alat kerja harian untuk Commercial Director dan Head of Sales: buka, lihat angka, putuskan. Rasanya tenang dan presisi,
seperti instrumen ukur, bukan poster. Angka dibaca duluan, dekorasi hampir nol, kata-kata seminimal mungkin
(tanpa headline, tanpa paragraf).

## Palette
- Canvas: abu dingin terang #E8E8EC. Card: putih #FFFFFF. Tanpa krem, tanpa gradien.
- Ink #16181D untuk angka dan judul. Muted #5E6470 untuk label dan meta (5,9:1 di putih, 4,9:1 di canvas).
- Garis: hairline #E6E8EC, pemisah putus-putus #D5D9DF.
- Primary: merah Dua Kelinci #DC2B2D (keputusan Bagus, 26 Nov) untuk logo, seri data utama (periode berjalan), tick
  meter yang terisi, chip terpilih, dan satu tombol utama per layar (teks putih 4,7:1). Tint #FBE3E3 untuk tick yang
  belum terisi.
- Periode pembanding (September): abu #A3A9B3, hanya sebagai isi bentuk, tidak pernah teks.
- Kategori (hanya isi chart, tidak pernah teks): kuning #F7C531, biru batu #4C6A92; sisanya abu.
- Semantik: naik hijau #15803D, turun oranye tua #B54708 (5,4:1). Delta = teks berwarna + tanda ▲▼ atau +/−, tanpa
  pill.
- Alasan: merah sudah jadi warna brand dan aksi, jadi "turun" memakai oranye tua + ▼ supaya merah di layar tidak punya
  dua arti.

## Typography
- 1 keluarga: Plus Jakarta Sans (sudah lokal di repo, offline; huruf yang dibuat untuk Jakarta, cocok untuk produk
  Indonesia). Tanpa serif, tanpa monospace.
- Angka utama 40 sampai 44px, weight 400, tracking −0,02em. Satuan ("jt", "hari", "%") di baris yang sama, 18px,
  weight 400, muted.
- Angka sekunder 24px weight 400. Judul card 16px weight 500. Baris data 15px weight 400. Label dan meta 13px muted,
  sentence case. Hanya weight 400 dan 500; angka tidak pernah bold.
- Tabular figures (tnum) di semua angka. Format: Rp 162,4 jt · Rp 6.000.000 · 21 hari · −Rp 2 rb (tanda minus asli).
- Alasan: angka besar weight normal terbaca sebagai ukuran, bukan teriakan.

## Komponen
- Card: putih, radius 12px, hairline 1px, tanpa bayangan, padding 16px. Kepala card: ikon kecil + judul di kiri, meta
  muted di kanan. Satu angka utama per card. Pemisah antar bagian = garis putus-putus.
- Tick meter (motif identitas): deretan pill vertikal tipis (lebar 3px, jarak 3px, tinggi 24px untuk progres, 14px
  untuk baris), terisi merah, sisanya tint merah; kelompok "lainnya" pakai ink. Persen di kanan, tabular.
- Bar komposisi: 2 sampai 3 segmen dengan jarak 4px, tinggi 5px, ujung bulat; legenda = titik 8px + label + nilai + %.
- Dot plot: track abu 4px, titik 10px (ink untuk normal, oranye tua untuk turun, hijau untuk naik), garis acuan vertikal putus-putus
  dengan label kecil di bawah, garis titik-titik ke angka di kanan.
- Line chart: garis 2px + area tint muda, gridline vertikal putus-putus saja, label sumbu jarang, titik terakhir
  berupa cincin + garis jatuh, tooltip chip putih (satu-satunya elemen berbayangan).
- Bar chart: track abu, bar aktif merah dengan angka di dalam, bar lain abu.
- Tabel: tanpa border luar, pemisah baris hairline, nominal rata kanan, status = teks berwarna (bukan pill), aksi baris
  = tombol sekunder abu.
- Tombol: utama merah #DC2B2D teks putih, radius 10px, tinggi 44px, maksimal satu per layar. Sekunder: isi abu
  #EEF0F3, teks ink, radius 8px. Chip/tile: abu, yang terpilih merah dengan teks putih.
- Ikon: garis 16px stroke 1,75 (setebal huruf Plus Jakarta Sans), hanya di kepala card, tiap ikon punya alasan
  relevansi tertulis. Override antislop R-04 (gaya ikon garis ala Lucide): keep, diputuskan 26 Nov karena referensi
  memakai gaya ini dan tiap ikon punya alasan.

## Density
Banyak card kecil, tiap card menjawab 1 pertanyaan: 1 angka utama + 1 visual kecil + paling banyak 5 baris. Jarak antar
card 12px. Penjelasan ada di balik ikon info, bukan di layar. Di ponsel: satu kolom, urutan sama, tidak ada scroll
horizontal.

## Dials
ENERGY 2 · RHYTHM 2 · MOTION 1
- ENERGY 2: warna hidup lewat data (merah, tick meter), bukan lewat dekorasi.
- RHYTHM 2: sistem card konsisten, variasi datang dari isi card (meter, dot plot, line, tabel).
- MOTION 1: hanya hover, focus, dan tooltip; tanpa animasi masuk.

### Relevansi ikon (per glyph, Lucide ISC, vendored di `static/vendor/lucide/`)
receipt = net dan invoice · boxes = karton · map-pin = region · tag = brand · package = cek stock-loading ·
store / warehouse / shopping-basket / house = tipe outlet (Minimarket / Grosir / Toko Kelontong / Warung) ·
triangle-alert = catatan data · calendar-plus = jadwalkan kunjungan (.ics) · calendar = hari kerja · copy = salin tugas ·
send = ringkasan Telegram · message-circle = tanya data · shield-check = kualitas data · info = penjelasan ·
printer = cetak · trending-down = region turun.

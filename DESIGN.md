# DESIGN.md · Dashboard penjualan Dua Kelinci

Bahasa visual diambil dari referensi "Buku kas" yang Bagus suka (26 Nov 2026). Layout dan kontennya tidak disalin.

## Identity
Alat kerja harian untuk Commercial Director dan Head of Sales: buka, lihat angka, putuskan. Rasanya tenang dan presisi,
seperti instrumen ukur, bukan poster. Angka dibaca duluan, dekorasi hampir nol, kata-kata seminimal mungkin
(tanpa headline, tanpa paragraf).

## Palette
Tailwind zinc + 1 aksen (keputusan Bagus, 26 Nov). Tidak ada warna lain.
- Canvas zinc-100 #F4F4F5. Card putih #FFFFFF. Garis zinc-200 #E4E4E7, pemisah putus-putus zinc-300 #D4D4D8.
- Ink zinc-900 #18181B untuk angka dan judul. Muted zinc-500 #71717A hanya di atas putih (4,8:1); di atas canvas
  pakai zinc-600 #52525B (7,0:1).
- Bentuk data netral: zinc-800 #27272A (naik / seri penting), zinc-400 #A1A1AA (periode pembanding, turun),
  zinc-200 #E4E4E7 (track, tick belum terisi). zinc-400 tidak pernah dipakai untuk teks.
- Aksen tunggal: merah Dua Kelinci #DC2B2D untuk logo, seri periode berjalan (Oct), titik highlight, tick meter terisi,
  chip terpilih, dan tombol utama (teks putih 4,7:1). Tidak dipakai untuk hal lain.
- Delta naik/turun dibedakan lewat ▲▼ + tanda, teks zinc-900, tanpa warna hijau/oranye dan tanpa pill.
- Alasan: abu netral membuat satu-satunya merah selalu menunjuk "periode ini / aksi ini".

## Typography
- 1 keluarga sans saja: Plus Jakarta Sans (sudah lokal di repo, offline; huruf yang dibuat untuk Jakarta, cocok untuk
  produk Indonesia). Tidak ada serif di mana pun, termasuk teks di dalam SVG chart (font-family wajib diset).
- Angka utama 40 sampai 44px, weight 400, tracking −0,02em. Satuan ("jt", "hari", "%") di baris yang sama, 18px,
  weight 400, muted.
- Angka sekunder 24px weight 400. Judul card 16px weight 500. Baris data 15px weight 400. Label dan meta 13px muted,
  sentence case. Hanya weight 400 dan 500; angka tidak pernah bold.
- Bahasa UI: English (keputusan Bagus, 26 Nov). Tabular figures (tnum) di semua angka. Format English: Rp 878.4M ·
  Rp 6,000,000 · 4,427 cartons · 27 days · −Rp 2.2M (tanda minus asli), bulan Sep / Oct.
- Alasan: angka besar weight normal terbaca sebagai ukuran, bukan teriakan.

## Komponen
- Card: putih, radius 12px, hairline 1px zinc-200, tanpa bayangan, padding 16px. Kepala card: ikon kecil + judul di kiri, meta
  muted di kanan. Satu angka utama per card. Pemisah antar bagian = garis putus-putus.
- Tick meter (motif identitas): deretan pill vertikal tipis (lebar 3px, jarak 3px, tinggi 24px untuk progres, 14px
  untuk baris), terisi merah, sisanya zinc-200; kelompok "lainnya" pakai zinc-800. Persen di kanan, tabular.
- Bar komposisi: 2 sampai 3 segmen (merah, zinc-800, zinc-300) dengan jarak 4px, tinggi 5px, ujung bulat; legenda = titik
  8px + label + nilai + %.
- Dot plot: track zinc-200 4px, titik 10px (zinc-800 naik, zinc-400 turun, merah untuk yang disorot), garis acuan putus-putus
  dengan label kecil di bawah, garis titik-titik ke angka di kanan.
- Line chart: garis 2px merah (Oct) dan zinc-400 (Sep), band muda di bawah garis Oct (merah 8% opacity), gridline
  vertikal putus-putus saja, label sumbu jarang, satu titik highlight berupa cincin merah + garis jatuh, tooltip chip
  putih yang tampil di titik highlight dan mengikuti hover/focus (satu-satunya elemen berbayangan).
- Bar chart: track zinc-200, bar aktif merah dengan angka di dalam, bar lain zinc-400.
- Tabel: tanpa border luar, pemisah baris hairline, nominal rata kanan, status = teks berwarna (bukan pill), aksi baris
  = tombol sekunder abu.
- Tombol: utama merah #DC2B2D teks putih, radius 10px, tinggi 44px, maksimal satu per layar. Sekunder: isi zinc-100,
  teks zinc-900, radius 8px. Chip/tile: zinc-100, yang terpilih merah dengan teks putih. Label CTA maksimal 2 kata.
- Ikon: garis 16px stroke 1,75 (setebal huruf Plus Jakarta Sans), hanya di kepala card, tiap ikon punya alasan
  relevansi tertulis. Override antislop R-04 (gaya ikon garis ala Lucide): keep, diputuskan 26 Nov karena referensi
  memakai gaya ini dan tiap ikon punya alasan.

## Density
Banyak card kecil, tiap card menjawab 1 pertanyaan: 1 angka utama + 1 visual kecil + paling banyak 5 baris. Jarak antar
card 16px. Penjelasan ada di balik ikon info, bukan di layar. Di ponsel: satu kolom, urutan sama, tidak ada scroll
horizontal.

## Dials
ENERGY 2 · RHYTHM 2 · MOTION 1
- ENERGY 2: satu merah di antara abu netral memberi titik fokus; hidup lewat data (tick meter, line), bukan dekorasi.
- RHYTHM 2: sistem card konsisten, variasi datang dari isi card (meter, dot plot, line, tabel).
- MOTION 1: hanya hover, focus, dan tooltip; tanpa animasi masuk.

### Relevansi ikon (per glyph, Lucide ISC, vendored di `static/vendor/lucide/`)
receipt = net dan invoice · boxes = karton · map-pin = region · tag = brand · package = cek stock-loading ·
store / warehouse / shopping-basket / house = tipe outlet (Minimarket / Grosir / Toko Kelontong / Warung) ·
triangle-alert = catatan data · calendar-plus = jadwalkan kunjungan (.ics) · calendar = hari kerja · copy = salin tugas ·
send = ringkasan Telegram · message-circle = tanya data · shield-check = kualitas data · info = penjelasan ·
printer = cetak · trending-down = region turun.

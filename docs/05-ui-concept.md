# 05 Konsep UI dashboard

## Untuk siapa dan pertanyaan apa

Pengguna utama: sales manager (Head of Sales atau Head of Region). Dia membuka halaman ini di pagi hari, lima menit sebelum briefing tim. Halaman menjawab empat pertanyaan, berurutan dari kiri atas ke kanan bawah:

1. Bagaimana penjualan kita? (angka utama di kiri atas, lalu tren mingguan dan perubahan dari bulan lalu)
2. Di mana naik dan turun? (region, brand, dan kombinasi region x brand)
3. Siapa yang perlu perhatian? (5 outlet terlemah dibanding outlet sejenis)
4. Apa yang saya sampaikan ke tim? (paragraf Telegram yang siap disalin atau dikirim)

Setiap bagian dibuka dengan satu kalimat yang dihitung dari data, misalnya "Jawa Timur naik 92,4% dari September, tertinggi di antara region; Jawa Barat turun 13,9%." Grafik di bawahnya membuktikan kalimat itu.

## Prinsip

- Paling banyak 6 KPI, dan setiap KPI mengarah ke tindakan. Net penjualan (dengan perubahan dan sparkline mingguan), karton, outlet aktif dan jumlah order, rata-rata nilai invoice, diskon sebagai persen dari gross, retur.
- Bar horizontal yang diurutkan untuk region, brand dan peringkat outlet: nama terbaca, tidak ada label miring. Region memakai dumbbell September ke Oktober dengan label perubahan di ujungnya. Kombinasi region x brand memakai heatmap satu warna (terang = kecil, gelap = besar) dengan angka di setiap sel. Outlet lemah memakai bullet bar: nilai outlet dibanding garis median outlet bertipe sama.
- Tidak ada pie, donut, gauge, 3D atau radar.
- Warna: UI netral, satu warna aksen (biru tua). Besaran memakai satu hue biru dari terang ke gelap. Perubahan memakai pasangan aman buta warna: biru naik, oranye turun, selalu dengan panah dan tanda plus/minus. Merah hanya untuk peringatan: outlet lemah dan catatan kualitas data. Kontras teks memenuhi WCAG AA.
- Angka: format Indonesia (Rp1,73 miliar, Rp878,4 juta, 8.745 karton, 3,6%), angka tabular, satuan selalu tertulis, periode selalu terlihat di header dan di judul setiap bagian.
- Interaksi yang berguna saja: pilihan periode Sep / Okt / Sep-Okt; klik bar region, bar brand atau sel heatmap untuk memfilter seluruh halaman, dengan chip filter yang bisa dihapus; tooltip nilai persis; "Lihat tabel" di bawah setiap grafik (juga untuk pembaca layar); unduh CSV yang aman dari formula injection.
- Tanpa garis grid yang tidak perlu, label langsung di bar menggantikan legenda, ruang kosong yang cukup.

## Wireframe desktop (1280 px ke atas)

```
+--------------------------------------------------------------------------------------------------+
| Penjualan Dua Kelinci   [Sep-Okt][Sep][Okt]   Filter: (Jawa Barat x)   Data 25 Nov 09:12   [DQ: 1.888 bersih, 3 duplikat] |
+--------------------------------------------------------------------------------------------------+
| Penjualan Sep-Okt 2026 Rp1,73 miliar; Oktober naik 3,6% dari September.                          |
| +-----------------------+ +-------------+ +----------------+ +---------------+ +-------------+   |
| | NET SETELAH RETUR     | | KARTON      | | OUTLET / ORDER | | RATA2 INVOICE | | DISKON      |   |
| | Rp1,73 miliar  +3,6%  | | 8.745       | | 52 / 823       | | Rp2,1 juta    | | 1,7% gross  |   |
| | ~~~ sparkline minggu  | | ~~~         | | ~~~            | | ~~~           | | retur -528rb|   |
| +-----------------------+ +-------------+ +----------------+ +---------------+ +-------------+   |
+------------------------------------------------------------+-------------------------------------+
| PENJUALAN PER REGION (Sep -> Okt)                          | PENJUALAN PER BRAND                 |
| Jawa Timur naik 92,4%, tertinggi; Jawa Barat turun 13,9%.  | Kacang Dua Kelinci 42,9% dari total.|
|  Jabodetabek  o-------->o  +7,5%                           |  Kacang Dua Kelinci ########## 42,9%|
|  Sumatera     o<-----o     -8,9%                           |  Tos Tos            ####       16,6%|
|  ...                                    [Lihat tabel]      |  ...                     [Lihat tabel]|
|------------------------------------------------------------|                                     |
| REGION x BRAND (heatmap, angka di sel, klik = filter)      |                                     |
|            Kacang  Tos Tos  Sukro  Tic Tac ...             |                                     |
| Jabodetabek [213]  [ 85 ]  [ 77 ]  [ 52 ]                  |                                     |
| ...                                     [Lihat tabel]      |                                     |
+------------------------------------------------------------+-------------------------------------+
| 5 OUTLET TERLEMAH (dibanding median outlet sejenis)        | RINGKASAN UNTUK TELEGRAM            |
| 5 outlet di bawah 10% median; semuanya invoice di luar     |  +-------------------------------+  |
| urutan, cek input ke admin.                                |  | (bubble chat seperti Telegram)|  |
| +--------------------------------------------------------+ |  | Ringkasan penjualan ...       |  |
| | 1 Toko Sinar Abadi  OUT1003  Toko Kelontong, Jkt Barat | |  +-------------------------------+  |
| |   [##|.................] Rp564rb vs median Rp14,8 jt   | |  759 karakter  [Salin] [Kirim]      |
| |   3 order, terakhir 31 Okt. Alasan... Saran...         | |  [Cetak]                            |
| |   (!) Nomor invoice di luar urutan  (!) Master ganda   | |                                     |
| +--------------------------------------------------------+ |                                     |
+------------------------------------------------------------+-------------------------------------+
                                                               [ Tanya data ]  <- tombol melayang
Laci kanan "Tanya data": chip pertanyaan, jawaban + chip sumber + tabel kecil.
Laci kanan "Kualitas data": aturan dan jumlah, duplikat yang dikarantina, retur, salesman yang
diisi, kemungkinan master ganda, tabel rekonsiliasi mentah ke bersih, unggah file lain (admin).
```

## Wireframe ponsel (390 px)

```
+------------------------------+
| Penjualan Dua Kelinci   [DQ] |
| [Sep-Okt][Sep][Okt]          |
+------------------------------+
| kalimat utama                |
| KPI 1 (besar) | KPI 2        |
| KPI 3         | KPI 4        |
+------------------------------+
| 5 outlet terlemah (kartu)    |
+------------------------------+
| Ringkasan Telegram           |
+------------------------------+
| Region (dumbbell)            |
| Brand (bar)                  |
| Heatmap (geser horizontal,   |
|  kolom region tetap)         |
+------------------------------+
| [Tanya data] layar penuh     |
+------------------------------+
```

## Keadaan dan detail

- Memuat: kerangka abu-abu di tempat grafik sampai grafik siap.
- Kosong: bila filter atau akses membuat data kosong, tampil penjelasan dan tombol "Hapus filter".
- Galat unggah: pesan menyebut kolom yang hilang atau masalah file; data yang tampil tidak berubah.
- Unggah: bar progres selama file dikirim, lalu hasil pemeriksaan.
- Keyboard: semua tombol, chip, bar (lewat tabel) dan laci bisa dipakai dengan keyboard; fokus terlihat; laci memakai elemen dialog dengan judul dan tombol tutup.
- Cetak: halaman ringkasan punya tampilan cetak tanpa navigasi.

## Teknis

- Grafik: Apache ECharts 5.6.0 disimpan lokal di `src/dk_sales/web/static/vendor/` (tanpa CDN, berjalan tanpa internet). Tooltip memakai mode rich text agar CSP ketat (tanpa inline style) tetap berlaku.
- Data grafik dikirim sebagai JSON di elemen `<script type="application/json">` yang di-escape oleh template; tidak ada skrip inline.
- Bullet bar outlet dan sparkline KPI digambar dengan SVG dari server, jadi tetap tampil walau JavaScript mati.

# 05 Konsep UI dashboard

Versi 2 (25 November 2026): desain ulang dengan brand Dua Kelinci. Versi pertama (UI netral dengan satu aksen biru tua, heatmap region x brand, garis mingguan) tersimpan di riwayat git dan di `docs/img/before-dashboard-desktop.png`.

## Untuk siapa dan pertanyaan apa

Pengguna utama: sales manager (Head of Sales atau Head of Region). Dia membuka halaman ini di pagi hari, lima menit sebelum briefing tim, sering dari ponsel. Halaman menjawab empat pertanyaan:

1. Bagaimana penjualan kita? (sapaan, satu kalimat judul, kartu angka utama, grafik kumulatif September vs Oktober)
2. Di mana naik dan turun? (dumbbell region, daftar region dengan bar, bar brand, alur region ke brand)
3. Siapa yang perlu dikunjungi? (5 kartu outlet dengan alasan, saran, dan aksi)
4. Apa yang saya sampaikan ke tim? (pesan bot Telegram yang siap disalin atau dikirim)

## Konsep yang dipilih: A + E + G, dengan dumbbell dari B

Bagus melihat delapan moodboard (A sampai H) dan memilih gabungan tiga, ditambah satu grafik dari B.

| Papan | Yang diambil | Alasan |
|---|---|---|
| A, Kelinci Lembut | Rail hitam di kiri dengan logo putih di lingkaran merah, sapaan per peran, pilihan periode berbentuk pil hitam, kartu KPI berwarna lembut, alur (sankey) region ke brand, panel kanan abu hangat | Paling terasa "Dua Kelinci" tanpa berteriak. Warna lembut membuat angka besar mudah dibaca, dan rail memberi navigasi yang tetap terlihat. |
| E, Kumulatif | Grafik kumulatif per tanggal September (abu) vs Oktober (merah) dengan label di ujung garis, daftar region dengan bar | Garis harian di versi lama berisik. Kumulatif menjawab pertanyaan manajer secara langsung: "apakah bulan ini sudah melewati bulan lalu, dan sejak kapan?" |
| G, Ponsel | Kartu merah besar dengan nilai Oktober dan sparkline, kartu outlet dengan aksi, pratinjau bot Telegram dengan tombol inline | Manajer membuka ini di ponsel. Kartu outlet G mengubah daftar menjadi tugas: alasan, saran, lalu tombol. |
| B, Merah Berani | Dumbbell September ke Oktober per region dengan label perubahan | Perubahan per region terbaca dalam satu pandang, dan arah naik/turun terlihat dari warna dan panah. |

## Yang tidak dipakai

- **C, Ruang kontrol gelap.** Tema gelap bagus untuk layar dinding, tetapi kontras angka kecil di ponsel pada pagi hari lebih buruk, dan tidak cocok dengan warna brand putih-merah.
- **F, Poster Baloo.** Huruf bulat besar dan piktogram karton lucu untuk materi promosi, tetapi terlalu ramai untuk alat kerja harian dan memakan ruang yang dibutuhkan angka.
- **H, Asisten AI di depan.** Menaruh chat sebagai pusat halaman membuat manajer harus bertanya dulu sebelum melihat angka. Chat tetap ada sebagai laci "Tanya data", bukan halaman utama.
- **D (koran) dan sisa B (petak peta).** Tipografi serif D enak dibaca tetapi lambat dipindai; peta petak B butuh legenda tambahan dan tidak menambah informasi dibanding daftar region.
- **Treemap brand dari E.** Petak kecil (Roni, Usagi) tidak terbaca di ponsel. Brand memakai bar terurut dengan porsi dan perubahan, yang tetap terbaca di semua ukuran.

## Arti warna

| Warna | Arti | Dipakai di |
|---|---|---|
| Merah `#DC2B2D` | Brand, satu tombol utama, penurunan, peringatan | Logo, tombol "Salin ringkasan" atau "Kirim ke Telegram" (tepat satu di halaman), garis Oktober, titik dan label region yang turun, kartu outlet, catatan "Cek data" |
| Merah tua `#A51D20` | Teks merah di atas latar merah muda (kontras AA 6,2:1) | Label "Prioritas", angka turun di kartu tinted |
| Hitam `#161616` | Teks, rail, kenaikan | Teks utama, rail, pil periode aktif, titik dan label region yang naik (selalu dengan ▲ dan tanda +) |
| Netral hangat `#F4F1EE`, `#ECE8E4`, `#FCE4E4`, `#FFF1DC` | Latar dan kartu KPI | Latar halaman, panel kanan, kartu KPI |
| Abu `#BDB4AC`, `#8A8580` | Pembanding dan besaran | Garis September, bar region dan brand, pita sankey yang tidak disorot |

Aturan: region yang tumbuh tidak pernah diberi warna merah (Jawa Timur +92,4% tampil hitam). Setiap perubahan selalu punya panah dan tanda, jadi tidak bergantung pada warna. Teks memenuhi kontras WCAG AA; putih di atas merah brand 4,7:1.

## Tata letak desktop (1280 sampai 1600 px)

```
+------+------------------------------------------------------------------------------------------+
| RAIL | Selamat pagi, Head of Sales                       [1.888 baris bersih] [Salin ringkasan]  |
| (o)  | Oktober naik 3,6% · 5 outlet perlu dikunjungi                                          |
|  ⌂   | [Sep][Okt][Sep–Okt]  [Semua region v] [Semua brand v]    Semua region · data dimuat ... |
|  ▣   +------------------------------------------------------------+-----------------------------+
|  ➤   | [Penjualan neto ] [Karton ] [Outlet aktif] [Diskon]        | Ringkasan untuk Telegram    |
|  ☐   | [Rp1,73 miliar  ] [8.745  ] [52          ] [1,7%  ]        |  (o) Dua Kelinci Sales Bot  |
|  ✓   +------------------------------------------------------------+  [pesan ringkasan  09.12]  |
|      | Penjualan neto kumulatif per tanggal         — Sep — Okt   |  [Buka dashboard][5 outlet] |
|      | "Sampai tanggal 30 Oktober masih Rp6,9 juta di bawah ..."  |  [Region saya][Tanya data]  |
|      |   Sep abu, Okt merah, label di ujung                       |  [Salin] [Cetak]            |
|      +-------------------------------+----------------------------+-----------------------------+
|      | Dumbbell region Sep -> Okt    | Region (bar + perubahan)   | 5 outlet perlu dikunjungi   |
|      +-------------------------------+----------------------------+  [Prioritas 1 Toko ...]     |
|      | Brand: bar terurut, porsi, perubahan                       |   bullet vs median          |
|      +------------------------------------------------------------+   order, bulan terakhir     |
|      | Alur region ke brand (sankey), region disorot  [badge]     |   catatan data, alasan      |
|      |   "Sorot region [Jawa Timur v]"                            |   saran                     |
|      +------------------------------------------------------------+  [Jadwalkan] [Salin tugas]  |
+------+------------------------------------------------------------+-----------------------------+
```

- **Rail**: Ringkasan, Outlet, Telegram (menggulir ke bagiannya), Tanya data dan Kualitas data (membuka laci). Setiap tombol punya label teks yang dibaca pembaca layar dan muncul sebagai tooltip saat hover atau fokus keyboard.
- **Header**: sapaan dari peran yang masuk ("Selamat pagi, Head of Region"), atau judul netral "Penjualan Dua Kelinci" di mode lokal tanpa login. Kalimat judul dihitung dari data. Tepat satu tombol merah: "Kirim ke Telegram" bila Telegram diatur, selain itu "Salin ringkasan".
- **Kartu KPI**: angka dan satuan dipisah ("Rp1,73" besar, "miliar" kecil) sehingga satuan boleh turun ke baris baru tetapi angka tidak pernah terpotong atau menimpa teks lain. Test e2e memeriksanya di 390, 1280, 1440 dan 1600 px.
- **Kumulatif**: hari tanpa penjualan meneruskan angka hari sebelumnya. Kalimat di atas grafik dihitung server, misalnya "Sampai tanggal 30 Oktober masih Rp6,9 juta di bawah September; tanggal 31, yang tidak ada di September, membuat Oktober menutup bulan Rp30,9 juta di atas September." Untuk Jabodetabek kalimatnya "Oktober menyalip September pada tanggal 13 ...".
- **Sankey**: pita terang untuk semua region, region terpilih disorot. Bawaan: region dengan perubahan absolut terbesar (Jawa Timur, +Rp66,8 juta). Klik nama region di grafik, pilih di "Sorot region", atau pasang filter region untuk mengganti sorotan. Tabel region x brand tetap ada di "Lihat tabel".
- **Pratinjau bot Telegram**: avatar bot (logo putih di lingkaran merah), jam, jumlah karakter, dan empat tombol mirip tombol inline Telegram yang di sini berfungsi sebagai pintasan di aplikasi (gulir ke dashboard, ke outlet, ke region atau filter region milik Head of Region, buka Tanya data). Tombol Kirim hanya muncul bila `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` diisi.
- **Kartu outlet**: peringkat, nama, id, tipe, cabang, bullet bar nilai outlet vs median outlet sejenis (garis hitam = median), jumlah order, nilai bulan terakhir, catatan data singkat (detail lengkap di "Cek data"), alasan satu baris, saran. Aksi yang benar-benar jalan tanpa server tambahan: "Jadwalkan kunjungan" mengunduh file `.ics` (acara sehari penuh di hari kerja berikutnya, bisa diimpor ke Google Calendar, Outlook atau kalender ponsel), "Salin tugas" menyalin teks tugas singkat untuk salesman.

## Ponsel (390 px)

Mengikuti papan G. Rail berubah menjadi bar bawah dengan ikon dan label. Urutan: header (logo, sapaan, kalimat judul, tombol utama, periode, filter), kartu merah nilai Oktober dengan sparkline harian, daftar region dengan bar, kartu outlet dengan aksi, pratinjau Telegram, kartu KPI, lalu grafik (dumbbell, kumulatif, brand, sankey). Tanya data dan laci lain terbuka sebagai lembar layar penuh. Tidak ada gulir horizontal halaman.

## Yang tetap dari versi 1

- Angka format Indonesia (Rp1,73 miliar, Rp878,4 juta, 8.745 karton, 3,6%), angka tabular, periode selalu tertulis.
- Pilihan periode, filter region dan brand (pilihan di header atau klik bar dan baris region), chip filter yang bisa dihapus.
- "Lihat tabel" untuk setiap grafik, juga untuk pembaca layar; unduh CSV aman formula.
- Laci Tanya data dengan guardrail angka, laci Kualitas data dengan unggah (admin), RBAC di lapisan data.
- Tampilan cetak ringkasan tanpa navigasi (`/summary/print`, dan `@media print` di dashboard).
- Fokus keyboard terlihat (garis kuning), laci memakai elemen `dialog` dengan judul dan tombol tutup, tautan "Langsung ke isi".

## Teknis

- Grafik: Apache ECharts 5.6.0 lokal di `static/vendor/`, renderer SVG, tooltip mode rich text agar CSP ketat (tanpa inline script dan inline style) tetap berlaku.
- Huruf: Plus Jakarta Sans variable (subset latin, woff2) di `static/fonts/` dengan lisensi SIL OFL (`OFL.txt`). Tidak ada Google Fonts atau CDN saat aplikasi berjalan. Grafik digambar setelah `document.fonts.ready` agar lebar label dihitung dengan huruf yang benar.
- Logo: `static/img/logo-white.png` dan `logo-red.png`. Logo dan nama Dua Kelinci milik PT Dua Kelinci, dipakai hanya untuk keperluan tes rekrutmen; kalimat ini juga tampil di footer setiap halaman.
- Bar region, bullet bar outlet dan sparkline ponsel digambar dengan SVG dari server (atribut, bukan style), jadi tetap tampil tanpa JavaScript dan tanpa melanggar CSP.
- Data grafik dikirim sebagai JSON di `<script type="application/json">` yang di-escape template.

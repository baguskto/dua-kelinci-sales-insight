# 06 Definisi angka

Semua angka dihitung di satu tempat (`src/dk_sales/analytics.py`) dan dipakai sama oleh halaman, API, ekspor CSV, ringkasan Telegram dan chat.

| Angka | Definisi |
|---|---|
| Net setelah retur | Jumlah `net_sales_idr` semua baris bersih, termasuk retur (bernilai negatif). Ini angka utama di semua tampilan. |
| Net penjualan | Jumlah `net_sales_idr` baris penjualan saja (tanpa retur). |
| Gross | Jumlah `gross_sales_idr` baris penjualan. |
| Diskon % | Diskon dibagi gross, baris penjualan. |
| Karton | Jumlah `qty_carton`, retur mengurangi. |
| Outlet aktif | Jumlah outlet yang punya minimal satu invoice penjualan pada periode. |
| Order | Jumlah nomor invoice penjualan (INV) yang berbeda. |
| Rata-rata nilai invoice | Net penjualan dibagi jumlah invoice penjualan. |
| Perubahan bulan | (bulan terakhir di data - bulan sebelumnya) / bulan sebelumnya. Selalu Oktober vs September untuk file ini, apa pun periode yang dipilih. |
| Hari kerja | Jumlah hari kalender Senin-Sabtu pada bulan itu, dihitung dari kalender (`calendar.monthrange`), bukan dari data. Minggu dikeluarkan karena file tidak punya penjualan rutin di hari Minggu; satu baris Minggu yang ada (INV500813, 27 September) adalah anomali urutan invoice yang sudah tercatat di `docs/01-dq-audit.md`, bukan hari kerja. September 2026 punya 26 hari kerja, Oktober 27. |
| Perubahan per hari kerja | (net bulan terakhir / hari kerja bulan terakhir - net bulan sebelumnya / hari kerja bulan sebelumnya) / (net bulan sebelumnya / hari kerja bulan sebelumnya). Membandingkan laju harian, bukan total bulan, jadi menunjukkan apakah kenaikan bulanan datang dari penjualan yang lebih kuat atau dari jumlah hari yang lebih banyak. Untuk file ini: Oktober naik 3,6% secara total tetapi -0,2% per hari kerja (Rp32,6 juta/hari di September vs Rp32,5 juta/hari di Oktober), karena Oktober punya satu hari kerja lebih banyak (27 vs 26). |
| Porsi | Nilai anggota dibagi total pada periode dan filter yang sama. |
| Periode | Sep-Okt (semua bulan), September, atau Oktober. Periode tampil di setiap judul bagian dan di setiap KPI. |

## Outlet terlemah

Pertanyaan yang dijawab: outlet mana yang paling perlu dikunjungi, kalau ukurannya adil.

1. Hitung net setelah retur per outlet pada periode yang dipilih. Outlet yang pernah muncul di data tetapi tidak order di periode itu ikut dengan nilai 0.
2. Kelompok pembanding = tipe outlet (Grosir, Minimarket, Toko Kelontong, Warung). Grosir membeli 4 sampai 15 karton per baris, tipe lain 1 sampai 4 karton, jadi membandingkan Warung dengan Grosir tidak adil.
3. Indeks = net outlet / median net outlet bertipe sama, dalam persen. Indeks terendah = terlemah.
4. Hanya outlet di bawah median yang masuk daftar, dan kelompok tipe harus punya minimal 2 outlet dalam akses pengguna.
5. Seri: net lebih kecil dulu, lalu outlet_id.

Jumlah order, order terakhir, perubahan bulan dan variasi SKU tidak mengubah urutan. Angka itu dipakai untuk menulis alasan dan memilih saran:

- 0 order di periode: pastikan outlet masih aktif dan masuk rute.
- Order kurang dari separuh median tipe: jadwalkan kunjungan rutin.
- Bulan terakhir turun 30% atau lebih: kunjungi minggu ini dan tanyakan penyebabnya.
- Selain itu: nilai per order kecil, tawarkan paket.
- Setiap saran ditambah dua SKU terlaris di tipe outlet yang sama yang belum pernah dibeli outlet itu.

Hasil di file ini (Sep-Okt): OUT1003, OUT1026, OUT1045, OUT1042, OUT1035, semuanya di bawah 10% median tipenya. Kelimanya hanya muncul di blok invoice INV500799-INV500823 (lihat `docs/01-dq-audit.md`). Sesuai keputusan Bagus, mereka tetap dihitung dan tampil dengan catatan "Cek data" sebagai konteks, bukan disembunyikan. OUT1001 dan OUT1003 (Toko Sinar Abadi, Jakarta Barat) tetap dua outlet karena id master berbeda, dengan catatan kemungkinan data master ganda.

Alternatif yang ditimbang dan tidak dipakai sebagai default:

- Net terendah apa adanya: selalu memilih Warung kecil, tidak membantu.
- Penurunan bulan ke bulan terbesar: outlet yang order sekali sebulan terlihat turun 100% secara acak.
- Skor gabungan berbobot: sulit dijelaskan ke tim sales dan sulit dicek dengan tangan.

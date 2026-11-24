# 09 Yang akan saya bangun berikutnya untuk Dua Kelinci

Urutan berdasarkan dampak untuk tim sales dan usaha yang dibutuhkan.

1. **Ambil langsung dari export QAD.** Pemetaan kolom QAD (sales order line, customer master, item master) ke kontrak 15 kolom, dijalankan terjadwal dari folder SharePoint atau share jaringan. Aturan DQ yang sama berjalan otomatis, dan baris yang dikarantina dikirim ke admin sales untuk dibetulkan di sumbernya. Data master outlet dari QAD akan menjawab pertanyaan OUT1001/OUT1003 secara permanen.
2. **Ringkasan harian per manajer lewat Teams dan Telegram.** Setiap Head of Region menerima paragraf untuk regionnya pukul 07.00, Head of Sales menerima ringkasan nasional, Brand Manager menerima brand-nya. Isinya dibangun dengan `summary.py` dan scope yang sama, jadi tidak ada angka yang bocor ke region lain. Teams lewat Incoming Webhook atau Graph API dengan akun Entra yang sudah dipakai untuk login.
3. **Alert yang bisa ditindaklanjuti.** Contoh: outlet yang biasanya order mingguan tidak order 14 hari, region turun lebih dari 10% dari rata-rata 4 minggu, duplikat atau retur besar di export hari ini. Dikirim ke orang yang memegang outlet atau region itu, bukan ke semua orang.
4. **Target dan budget.** Begitu file target per salesman dan per brand tersedia, KPI utama berubah menjadi pencapaian vs target, dan "outlet terlemah" bisa memakai potensi outlet, bukan median tipe.
5. **Rute salesman.** Daftar outlet lemah dijadikan usulan rute kunjungan per salesman per hari, dengan tombol "sudah dikunjungi" untuk mengukur apakah kunjungan menaikkan order.
6. **Penyimpanan historis.** DuckDB atau Postgres untuk data bertahun-tahun, dengan tabel fakta yang sama, supaya perbandingan tahun ke tahun dan musiman (Lebaran, akhir tahun) bisa dihitung.

Yang tidak saya bangun sebelum ada pengguna yang memintanya: prediksi penjualan, chatbot bebas di luar data, dan dashboard per SKU yang detail. Saya akan duduk dulu dengan satu Head of Region selama satu minggu untuk melihat keputusan apa yang sebenarnya dia ambil setiap pagi.

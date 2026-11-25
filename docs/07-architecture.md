# 07 Arsitektur

## Alur data

```
sales.csv / unggahan .csv .xlsx
        |
        v
[io]        baca sebagai teks: deteksi encoding (UTF-8, BOM, UTF-16, cp1252) dan pemisah (, ; tab |)
        |
[dataset]   cek unggahan: ekstensi, ukuran, isi file (sniffing), batas baris, xlsx tanpa macro dan bukan zip bomb
        |
[clean]     27 aturan DQ: perbaiki, isi dengan bukti, tandai, atau karantina; semua tercatat di DQ log
        |
[model]     fact_sales_line + dim_outlet, dim_product, dim_salesman, dim_geo, dim_date (kontrak pandera)
        |
[analytics] satu-satunya tempat angka dihitung; scope akses diterapkan di sini
        |
  +-----+-----------+---------------+------------------+
  |                 |               |                  |
[web: halaman]  [API JSON]   [summary: Telegram]  [chat: tool baca-saja]
  |                                 |                  |
  ECharts lokal               [guard: cek angka] <-----+  (mode LLM opsional: Claude + tool calling)
```

## Komponen

| Modul | Tugas |
|---|---|
| `dk_sales/io.py` | Membaca CSV dan xlsx menjadi tabel teks. |
| `dk_sales/clean.py`, `rules.py` | Aturan kualitas data, DQ log, karantina. |
| `dk_sales/model.py`, `contract.py` | Model bintang dan kontrak data. |
| `dk_sales/pipeline.py`, `profile.py`, `reconcile.py`, `docs.py` | Build fase 1 (`make data`): profiling, dokumen, rekonsiliasi. |
| `dk_sales/analytics.py` | Total, breakdown, perubahan bulan, matriks region x brand, kumulatif per tanggal, KPI mingguan, outlet terlemah, kalimat judul. |
| `dk_sales/summary.py`, `guard.py`, `fmt.py` | Ringkasan Telegram, cek angka, format angka Indonesia. |
| `dk_sales/chat/` | Tool baca-saja, parser intent offline, engine (offline dan LLM), set evaluasi. |
| `dk_sales/web/` | FastAPI: pengaturan, autentikasi dan RBAC, keamanan HTTP, telemetri, penyimpanan dataset, rute, template, aset statis (ECharts, huruf Plus Jakarta Sans, logo; semua lokal). |
| `dk_sales/web/views.py` | Geometri SVG, sapaan per peran, teks tugas kunjungan, file kalender .ics, data grafik. |

## Keputusan desain

- **Satu proses, tanpa database.** 1.891 baris muat di memori dan dihitung ulang dalam sekitar 1,5 detik. Untuk data harian QAD bertahun-tahun, langkah berikutnya adalah DuckDB atau Postgres di belakang `analytics.py` tanpa mengubah UI.
- **Server merender HTML, JavaScript hanya untuk grafik dan interaksi.** Halaman tetap terbaca tanpa JavaScript (tabel "Lihat tabel", sparkline dan bullet bar SVG dari server). Tidak ada build step frontend.
- **Offline dulu.** Semua fitur jalan tanpa internet dan tanpa kunci API. Claude, Telegram, Entra ID dan Langfuse hanya aktif bila variabel lingkungannya diisi.
- **Unggahan memakai kontrak dan aturan yang sama** dengan `sales.csv`. File yang ditolak tidak pernah mengganti data yang sedang tampil. File yang diterima disimpan di `DATA_DIR/uploads/<sha256>` dan tetap aktif setelah restart.
- **Akses di lapisan data.** `Scope.apply` dijalankan sebelum angka apa pun dihitung, untuk halaman, API, ekspor, ringkasan dan chat.

## Endpoint

| Metode dan path | Akses | Isi |
|---|---|---|
| GET `/` | semua peran | Dashboard; parameter `period`, `region`, `brand` |
| GET `/outlet/{id}` | semua peran, dalam scope | Detail outlet |
| GET `/outlet/{id}/kunjungan.ics` | semua peran, dalam scope | Acara kalender kunjungan untuk outlet yang perlu dikunjungi (filter dan periode sama dengan dashboard) |
| GET `/api/overview`, `/api/sales`, `/api/summary` | semua peran | JSON untuk integrasi |
| POST `/api/chat` | semua peran, CSRF | Tanya data |
| POST `/api/telegram/send` | semua peran, CSRF, audit | Kirim ringkasan (uji kirim bila belum diatur; tombol Kirim di UI hanya muncul bila Telegram diatur) |
| GET `/summary/print` | semua peran | Ringkasan untuk dicetak |
| GET `/export/{region,brand,weakest}.csv` | semua peran | CSV aman formula |
| GET `/export/quarantine.csv` | admin | Baris karantina |
| POST `/upload`, `/dataset/reset` | admin, CSRF, audit | Ganti data |
| GET `/login`, POST `/login`, GET `/auth/entra/*`, POST `/logout` | publik | Masuk dan keluar |
| GET `/health` | publik | Status tanpa detail sensitif |
| GET `/metrics` | token `METRICS_TOKEN` (dev: hanya localhost) | Metrik Prometheus |

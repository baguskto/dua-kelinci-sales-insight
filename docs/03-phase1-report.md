# 03 Laporan fase 1: profiling, audit kualitas data, cleaning

Tanggal: 25 November 2026.

## Ringkasan

- Input: `data/raw/sales_raw.csv`, 1.891 baris, 15 kolom, 1 September sampai 31 Oktober 2026. File tidak diubah; sha256 dicatat di kontrak dan dicek oleh test.
- Hasil: 1.888 baris bersih (1.887 penjualan, 1 retur), 3 baris dikarantina. Tidak ada baris yang hilang tanpa catatan.
- Net penjualan bersih Rp1.726.494.000; retur -Rp528.000; net setelah retur Rp1.725.966.000.
- 27 aturan kualitas data (DQ-01 sampai DQ-27). 14 aturan menemukan sesuatu di file ini (3 di antaranya, DQ-19, DQ-20 dan DQ-22, hanya akibat DQ-03/04/05); 13 lainnya lolos tetapi tetap dijalankan untuk file berikutnya.
- Rekonsiliasi mentah ke bersih per bulan dan region selisih 0 rupiah di semua ukuran.
- 55 test lulus, cakupan kode 95%.

## Temuan

| id | Temuan | Jumlah | Keputusan |
|---|---|---:|---|
| DQ-03 | Region tidak baku: Jabar 4, JAWA BARAT 4, JABODETABEK 1, JAWA TIMUR 1 | 10 baris | Diperbaiki ke nama baku |
| DQ-04 | Spasi di akhir outlet_name (Grosir Berkah, Toko Murah Meriah, Toko Sumber Rejeki) | 4 baris | Diperbaiki |
| DQ-05 | Salesman kosong | 5 baris | Diisi dari baris lain di invoice yang sama; ditandai `dq_salesman_inferred` |
| DQ-06 | Duplikat persis di INV500201, INV500386, INV500791 | 3 baris | Dikarantina (net Rp2.070.900) |
| DQ-07 | Retur RTR900001, OUT1049, Tos Tos Tortilla BBQ 140g, -2 karton | 1 baris | Disimpan sebagai retur, dipisah dari penjualan |
| DQ-08 | Retur 2 karton, padahal outlet itu baru membeli 1 karton SKU tersebut di periode data | 1 baris | Ditandai; kemungkinan barang dari sebelum September |
| DQ-09 | INV500799 sampai INV500823 bernomor di luar urutan tanggal | 25 invoice, 25 baris | Ditandai, tetap dihitung |
| DQ-10 | OUT1003, OUT1026, OUT1035, OUT1042, OUT1045 hanya muncul di blok itu | 5 outlet | Ditandai `dq_suspect_outlet` |
| DQ-11 | Transaksi hari Minggu 27 September (INV500813, bagian dari blok DQ-09) | 1 baris | Ditandai |
| DQ-12 | Toko Sinar Abadi memakai OUT1001 dan OUT1003 di cabang Jakarta Barat | 2 outlet | Ditandai, tidak digabung |
| DQ-13 | 8 nama outlet dipakai 18 outlet_id di cabang berbeda | 18 outlet | Dianggap outlet berbeda, dicatat di dim_outlet |
| DQ-19, DQ-20, DQ-22 | Atribut outlet, region per cabang dan header invoice tidak konsisten | 10 outlet, 19 invoice | Semuanya akibat DQ-03/04/05; setelah perbaikan 0 sisa |

Yang dicek dan bersih: aritmetika gross dan net (0 selisih), pola diskon (semua baris cocok dengan 0/2/3/5% dibulatkan ke Rp100; nilai seperti 1,99% hanya efek pembulatan), satu harga dan satu brand per SKU, salesman hanya di satu cabang, tanda qty sesuai jenis dokumen, tidak ada hari Senin-Sabtu yang kosong, semua tanggal di dalam periode.

### Blok invoice di luar urutan

Nomor invoice reguler (INV500001 sampai INV500798) naik mengikuti tanggal tanpa pengecualian. 25 invoice setelahnya bertanggal mundur, dari 5 September sampai 31 Oktober. Ciri-cirinya seragam: 1 baris, 1 karton, tanpa diskon (pada baris reguler 1 karton, hanya 53% yang tanpa diskon), nomor dikelompokkan per outlet, dan di file mentah setiap baris ini ada di posisi terakhir tanggalnya. Kelima outlet tidak pernah muncul di invoice reguler. Satu-satunya transaksi hari Minggu juga ada di blok ini.

Kesimpulan: baris ini ditambahkan setelah export reguler, entah input susulan dari nota manual atau baris yang disisipkan ke data contoh. Nilainya kecil (Rp4.908.000, 0,28% dari net). Baris tetap dihitung karena angkanya konsisten, tetapi bisa dikecualikan lewat tanda.

### Hari Minggu

7 dari 8 hari Minggu tidak punya transaksi sama sekali. Senin sampai Sabtu selalu ada transaksi. Jadi hari Minggu memang hari tidak berdagang, dan satu transaksi di Minggu 27 September adalah anomali. Tidak ada libur nasional di September-Oktober 2026.

## Model data

`data/processed/` berisi `fact_sales_line` dan 5 dimensi (`dim_outlet`, `dim_product`, `dim_salesman`, `dim_geo`, `dim_date`) dalam Parquet dan CSV, plus `dq_log.csv` (100 entri), `quarantine_lines.csv`, `reconciliation_bridge.csv` dan `dq_summary.json`. Kamus data: `docs/02-data-dictionary.md`. Kontrak: `docs/02-data-contract.md` dan `contracts/sales_data_contract.json`.

## Rekonsiliasi

| Ukuran | Mentah | DQ-03 | DQ-06 | Bersih | Selisih |
|---|---:|---:|---:|---:|---:|
| Baris | 1.891 | 0 | -3 | 1.888 | 0 |
| Karton | 8.754 | 0 | -9 | 8.745 | 0 |
| Gross | 1.758.432.000 | 0 | -2.112.000 | 1.756.320.000 | 0 |
| Diskon | 30.395.100 | 0 | -41.100 | 30.354.000 | 0 |
| Net | 1.728.036.900 | 0 | -2.070.900 | 1.725.966.000 | 0 |

DQ-03 bernilai 0 di total karena hanya memindahkan baris dari label region lama ke label baku. Rincian per bulan dan region ada di `docs/02-reconciliation.md`.

## Test

`make test`: 55 test lulus dalam sekitar 20 detik. Cakupan kode 95% (`make cov`).

- `tests/test_dq_rules.py`: minimal satu test per aturan DQ, dengan angka dari file asli dan contoh kecil buatan.
- `tests/test_contract.py`: kontrak pandera, integritas referensi, ukuran dimensi.
- `tests/test_reconciliation.py`: jembatan mentah ke bersih selisih 0.
- `tests/test_raw_and_idempotency.py`: hash file mentah, dua kali build menghasilkan hash yang sama, dokumen di repo sama dengan hasil build baru.
- `tests/test_io.py`: titik koma, BOM, cp1252, UTF-16, xlsx, file kosong dan biner.

## Pertanyaan terbuka untuk Bagus

1. Blok INV500799-INV500823: tetap dihitung (pilihan sekarang) atau dikeluarkan dari angka utama? Dampaknya Rp4,9 juta.
2. OUT1001 dan OUT1003 (Toko Sinar Abadi, Jakarta Barat): perlakukan sebagai satu outlet atau dua?
3. Retur RTR900001 (2 karton, padahal baru dibeli 1): cukup ditandai, atau perlu dikonfirmasi ke tim?
4. Daftar libur nasional 2026 diambil dari ingatan dan hanya berisi tanggal di luar periode. Perlu dicek ke SKB 3 Menteri bila data diperluas ke bulan lain.

# 02 Kontrak data

Kontrak ini mengatur apa yang boleh masuk ke pipeline dan apa yang dijamin keluar. Versi yang bisa dibaca mesin ada di `contracts/sales_data_contract.json` (dibuat ulang oleh `make data`). Skema yang benar-benar dijalankan ada di `src/dk_sales/contract.py` (pandera).

## Input

- File: `data/raw/sales_raw.csv`, tidak boleh diubah. sha256 `48b9f90ddaa91e0033ada4feb3cb47a8aaf490774165d266223be1da34e6741f`. Test `tests/test_raw_and_idempotency.py` memeriksa hash ini dan memastikan git tidak mencatat perubahan di `data/raw`.
- Grain: satu baris = satu SKU pada satu dokumen penjualan (INV) atau retur (RTR).
- Format yang diterima: CSV UTF-8 (dengan atau tanpa BOM), UTF-16, cp1252; pemisah koma, titik koma, tab atau garis tegak dideteksi otomatis; .xlsx sheet pertama. File .xls lama ditolak.
- 15 kolom wajib. Nama kolom dinormalkan (huruf kecil, spasi jadi garis bawah), jadi `Outlet Name` dan `outlet_name` dianggap sama. Kolom tambahan diabaikan dan dicatat.

| Kolom | Tipe | Boleh kosong | Aturan |
|---|---|---|---|
| date | tanggal | tidak | YYYY-MM-DD atau DD/MM/YYYY |
| invoice_no | teks | tidak | `INV` atau `RTR` + 6 digit |
| region | teks | tidak | dipetakan ke 6 nama baku (DQ-03) |
| branch | teks | tidak | satu region per cabang (DQ-20) |
| outlet_id | teks | tidak | atribut stabil per id (DQ-19) |
| outlet_name | teks | tidak | spasi tepi dihapus (DQ-04) |
| outlet_type | teks | tidak | Grosir, Minimarket, Toko Kelontong, Warung |
| salesman | teks | ya | diisi dengan bukti (DQ-05) |
| brand | teks | tidak | satu brand per SKU (DQ-18) |
| sku | teks | tidak | satu harga per SKU (DQ-17) |
| qty_carton | bilangan bulat | tidak | bukan nol; positif untuk INV, negatif untuk RTR (DQ-24) |
| price_per_carton_idr | bilangan bulat | tidak | lebih dari 0 |
| gross_sales_idr | bilangan bulat | tidak | = qty x harga (DQ-14) |
| discount_idr | bilangan bulat | tidak | 0/2/3/5% dari gross, dibulatkan ke Rp100 (DQ-16) |
| net_sales_idr | bilangan bulat | tidak | = gross - diskon (DQ-15) |

## Apa yang terjadi bila kontrak dilanggar

| Pelanggaran | Tindakan |
|---|---|
| Kolom wajib hilang, file kosong, file biner | File ditolak dengan pesan yang menyebut kolom/masalahnya (DQ-01) |
| Nilai tidak bisa dibaca (tanggal, angka, format invoice, kolom wajib kosong) | Baris dikarantina (DQ-02) |
| Aritmetika salah, tanda qty salah | Baris dikarantina (DQ-14, DQ-15, DQ-24) |
| Duplikat persis | Kemunculan kedua dan seterusnya dikarantina (DQ-06) |
| Ejaan region, spasi tepi | Diperbaiki, nilai lama di log (DQ-03, DQ-04) |
| Salesman kosong | Diisi bila ada bukti, ditandai (DQ-05) |
| Hal lain yang mencurigakan | Ditandai di kolom `dq_*`, angka tidak diubah |

## Output yang dijamin

- `rows_in == rows_clean + rows_quarantined`. Tidak ada baris yang hilang tanpa catatan.
- Setiap baris fakta: `gross = qty x harga`, `net = gross - diskon`, `is_return` benar bila dan hanya bila qty negatif.
- `region` hanya berisi 6 nama baku.
- Tidak ada duplikat persis di fakta.
- Setiap kunci di fakta ada di dimensinya (outlet, produk, geo, tanggal, salesman).
- Rekonsiliasi mentah ke bersih per bulan dan region selisih 0 rupiah untuk baris, karton, gross, diskon dan net.
- Menjalankan pipeline dua kali menghasilkan file yang sama byte per byte.

Semua jaminan di atas punya test di `tests/`.

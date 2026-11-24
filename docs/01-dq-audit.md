# 01 Audit kualitas data

Dibuat otomatis oleh `make data`. Setiap aturan punya id tetap (DQ-01 sampai DQ-27) yang dipakai di log (`data/processed/dq_log.csv`), karantina (`data/processed/quarantine_lines.csv`), kolom tanda di `fact_sales_line`, dan test (`tests/test_dq_rules.py`).

Baris masuk 1891, baris bersih 1888, baris karantina 3. Tidak ada baris yang dibuang tanpa catatan.

Arti kolom: **baris** = jumlah baris yang terkena aturan di data mentah; **entitas** = jumlah invoice/outlet/tanggal yang terkena bila aturan berlaku di level itu; **sisa** = pelanggaran yang masih ada setelah cleaning.

## Ringkasan aturan

| id | aturan | tingkat | level | baris | entitas | sisa | tindakan |
|---|---|---|---|---|---|---|---|
| DQ-01 | Skema kolom: 15 kolom wajib dengan nama yang dikenal | tinggi | file | 0 | 0 | 0 | ditolak |
| DQ-02 | Format nilai: tanggal ISO, angka bulat, nomor invoice, kolom wajib terisi | tinggi | row | 0 | 0 | 0 | dikarantina |
| DQ-03 | Penulisan region tidak baku (huruf besar/kecil, singkatan) | sedang | row | 10 | 0 | 0 | diperbaiki |
| DQ-04 | Spasi di awal/akhir teks (misalnya outlet_name) | rendah | row | 4 | 0 | 0 | diperbaiki |
| DQ-05 | Salesman kosong | sedang | row | 5 | 0 | 0 | diisi (inferensi) |
| DQ-06 | Baris duplikat persis dalam invoice yang sama | tinggi | row | 3 | 3 | 0 | dikarantina |
| DQ-07 | Baris retur (dokumen RTR, qty dan nilai negatif) | sedang | row | 1 | 0 | 0 | ditandai |
| DQ-08 | Retur tanpa pembelian yang cukup di periode data | rendah | row | 1 | 0 | 0 | ditandai |
| DQ-09 | Nomor invoice di luar urutan (nomor lebih besar dari invoice bertanggal lebih akhir) | sedang | invoice | 25 | 25 | 0 | ditandai |
| DQ-10 | Outlet yang hanya muncul di invoice di luar urutan | sedang | outlet | 25 | 5 | 0 | ditandai |
| DQ-11 | Transaksi di hari non-dagang (Minggu atau libur nasional) | rendah | row | 1 | 0 | 0 | ditandai |
| DQ-12 | Nama outlet sama, outlet_id berbeda, di cabang yang sama | sedang | outlet | 25 | 2 | 0 | ditandai |
| DQ-13 | Nama outlet sama, outlet_id berbeda, di cabang berbeda | info | outlet | 463 | 18 | 0 | dicatat |
| DQ-14 | gross_sales_idr = qty_carton x price_per_carton_idr | tinggi | row | 0 | 0 | 0 | dikarantina |
| DQ-15 | net_sales_idr = gross_sales_idr - discount_idr | tinggi | row | 0 | 0 | 0 | dikarantina |
| DQ-16 | Pola diskon: 0, 2, 3 atau 5 persen dari gross, dibulatkan ke Rp100 terdekat | rendah | row | 0 | 0 | 0 | ditandai |
| DQ-17 | Satu harga per SKU | sedang | row | 0 | 0 | 0 | ditandai |
| DQ-18 | Satu brand per SKU | sedang | row | 0 | 0 | 0 | ditandai |
| DQ-19 | Atribut outlet stabil (nama, tipe, cabang, region per outlet_id) | sedang | outlet | 14 | 10 | 0 | ditandai |
| DQ-20 | Satu region per cabang | sedang | row | 10 | 0 | 0 | ditandai |
| DQ-21 | Salesman hanya di satu cabang | sedang | row | 0 | 0 | 0 | ditandai |
| DQ-22 | Header invoice sama di semua baris (tanggal, outlet, cabang, region, salesman) | sedang | invoice | 19 | 19 | 0 | ditandai |
| DQ-23 | SKU tidak berulang dalam satu invoice (setelah duplikat persis dikarantina) | rendah | row | 0 | 0 | 0 | ditandai |
| DQ-24 | Tanda qty sesuai jenis dokumen (INV positif, RTR negatif, tidak nol) | tinggi | row | 0 | 0 | 0 | dikarantina |
| DQ-25 | Lebih dari satu invoice penjualan per outlet per hari | info | outlet | 0 | 0 | 0 | ditandai |
| DQ-26 | Hari dagang (Senin-Sabtu) tanpa transaksi | info | date | 0 | 0 | 0 | dicatat |
| DQ-27 | Tanggal di luar periode yang diharapkan | sedang | row | 0 | 0 | 0 | ditandai |

## Temuan khusus: invoice di luar urutan (DQ-09, DQ-10)

- 25 invoice (INV500799 s.d. INV500823), 25 baris, 25 karton, net Rp4.908.000 (0,28% dari net penjualan).
- Invoice reguler bernomor naik mengikuti tanggal tanpa pengecualian (798 invoice). Blok ini bernomor setelah invoice reguler terakhir, tetapi tanggalnya tersebar dari 2026-09-05 sampai 2026-10-31.
- Setiap invoice di blok ini hanya 1 baris dan 1 karton, semua tanpa diskon. Pada baris reguler 1 karton, yang tanpa diskon hanya 53%.
- Nomor dalam blok dikelompokkan per outlet: OUT1003, OUT1026, OUT1035, OUT1042, OUT1045. Kelima outlet ini tidak pernah muncul di invoice reguler.
- Di file mentah, setiap baris blok ini berada di posisi terakhir pada tanggalnya, setelah semua invoice reguler hari itu.
- Transaksi di hari non-dagang: 1 baris (2026-09-27 INV500813); 1 di antaranya ada di blok ini.
- Nama outlet: OUT1003 (Toko Sinar Abadi, Jakarta Barat) bernama sama dengan OUT1001 di Jakarta Barat, OUT1040 di Medan; OUT1026 (Toko Mulia, Solo) bernama sama dengan OUT1030 di Surabaya; OUT1035 (Warung Maju Lancar) namanya unik; OUT1042 (Toko Mandiri, Palembang) bernama sama dengan OUT1021 di Semarang; OUT1045 (Toko Anugerah, Banjarmasin) bernama sama dengan OUT1024 di Semarang, OUT1041 di Palembang.

Penjelasan yang paling cocok: baris-baris ini ditambahkan belakangan ke export, bukan dicatat saat transaksi. Bisa berupa input susulan (misalnya nota manual atau order kanvas yang diketik setelah tutup bulan), atau baris yang sengaja disisipkan ke data contoh. Dari data saja tidak bisa dipastikan. Keputusan: baris tetap dihitung karena angkanya konsisten (qty x harga, tanpa diskon), tetapi diberi tanda `dq_late_numbered_invoice` dan `dq_suspect_outlet` sehingga dashboard bisa menampilkan atau mengecualikannya.

## Temuan khusus: retur (DQ-07, DQ-08)

- RTR900001 tanggal 2026-10-10, outlet OUT1049, Tos Tos Tortilla BBQ 140g, qty -2, net -Rp528.000. Pembelian SKU ini oleh outlet yang sama sampai tanggal itu: 1 karton (INV500527).

Retur disimpan sebagai baris tersendiri dengan `is_return = true` dan `document_type = return`. Penjualan bruto dan neto penjualan hanya menjumlah baris `sale`. Neto setelah retur = neto penjualan + neto retur.

## Detail per aturan

### DQ-01 Skema kolom: 15 kolom wajib dengan nama yang dikenal

- Tingkat: tinggi; level: file; tindakan: ditolak
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Keputusan: File ditolak bila ada kolom wajib yang hilang. Nama kolom dinormalkan (huruf kecil, spasi jadi garis bawah); kolom tambahan diabaikan dan dicatat.

### DQ-02 Format nilai: tanggal ISO, angka bulat, nomor invoice, kolom wajib terisi

- Tingkat: tinggi; level: row; tindakan: dikarantina
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Keputusan: Baris yang tanggalnya tidak bisa dibaca, angkanya bukan bilangan bulat, nomor invoicenya tidak berpola INV/RTR + 6 digit, atau kolom wajibnya kosong masuk karantina dengan alasannya.

### DQ-03 Penulisan region tidak baku (huruf besar/kecil, singkatan)

- Tingkat: sedang; level: row; tindakan: diperbaiki
- Jumlah: 10 baris, 0 entitas, sisa setelah cleaning 0
- Keputusan: Region dipetakan ke 6 nama baku (Jabodetabek, Jawa Barat, Jawa Tengah, Jawa Timur, Sumatera, Kalimantan). Singkatan seperti Jabar dipetakan lewat daftar alias. Nilai lama dicatat di log.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 11 | 12 | INV500005 | OUT1014 | region | Jabar | Jawa Barat | Region 'Jabar' dipetakan ke nama baku 'Jawa Barat'. |
| 103 | 104 | INV500041 | OUT1017 | region | JAWA BARAT | Jawa Barat | Region 'JAWA BARAT' dipetakan ke nama baku 'Jawa Barat'. |
| 134 | 135 | INV500054 | OUT1015 | region | Jabar | Jawa Barat | Region 'Jabar' dipetakan ke nama baku 'Jawa Barat'. |
| 642 | 643 | INV500265 | OUT1014 | region | Jabar | Jawa Barat | Region 'Jabar' dipetakan ke nama baku 'Jawa Barat'. |
| 662 | 663 | INV500274 | OUT1006 | region | JABODETABEK | Jabodetabek | Region 'JABODETABEK' dipetakan ke nama baku 'Jabodetabek'. |

### DQ-04 Spasi di awal/akhir teks (misalnya outlet_name)

- Tingkat: rendah; level: row; tindakan: diperbaiki
- Jumlah: 4 baris, 0 entitas, sisa setelah cleaning 0
- Keputusan: Spasi di awal dan akhir semua kolom teks dihapus, spasi ganda di tengah dijadikan satu.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 163 | 164 | INV500066 | OUT1004 | outlet_name | 'Grosir Berkah ' | 'Grosir Berkah' | Spasi di awal/akhir atau spasi ganda dihapus. |
| 618 | 619 | INV500257 | OUT1032 | outlet_name | 'Toko Murah Meriah ' | 'Toko Murah Meriah' | Spasi di awal/akhir atau spasi ganda dihapus. |
| 1265 | 1266 | INV500529 | OUT1004 | outlet_name | 'Grosir Berkah ' | 'Grosir Berkah' | Spasi di awal/akhir atau spasi ganda dihapus. |
| 1738 | 1739 | INV500734 | OUT1005 | outlet_name | 'Toko Sumber Rejeki ' | 'Toko Sumber Rejeki' | Spasi di awal/akhir atau spasi ganda dihapus. |

### DQ-05 Salesman kosong

- Tingkat: sedang; level: row; tindakan: diisi (inferensi)
- Jumlah: 5 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_salesman_inferred`
- Keputusan: Salesman diisi hanya bila ada bukti: (1) baris lain di invoice yang sama punya satu salesman, atau (2) outlet itu hanya pernah dilayani satu salesman. Tanpa bukti, nilainya dibiarkan kosong dan ditandai. Baris yang diisi diberi tanda dq_salesman_inferred.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 603 | 604 | INV500251 | OUT1020 | salesman |  | Joko | Baris lain di invoice INV500251 dicatat atas nama Joko. |
| 998 | 999 | INV500423 | OUT1038 | salesman |  | Wahyu | Baris lain di invoice INV500423 dicatat atas nama Wahyu. |
| 1441 | 1442 | INV500607 | OUT1046 | salesman |  | Agus | Baris lain di invoice INV500607 dicatat atas nama Agus. |
| 1463 | 1464 | INV500617 | OUT1021 | salesman |  | Lestari | Baris lain di invoice INV500617 dicatat atas nama Lestari. |
| 1504 | 1505 | INV500636 | OUT1036 | salesman |  | Sari | Baris lain di invoice INV500636 dicatat atas nama Sari. |

### DQ-06 Baris duplikat persis dalam invoice yang sama

- Tingkat: tinggi; level: row; tindakan: dikarantina
- Jumlah: 3 baris, 3 entitas, sisa setelah cleaning 0
- Keputusan: Kemunculan pertama dipertahankan, kemunculan berikutnya masuk karantina dengan nomor baris aslinya. Tidak ada nomor baris item di data, dan tidak ada invoice lain yang memuat SKU yang sama dua kali, sehingga baris kembar dianggap terinput dua kali.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 495 | 496 | INV500201 | OUT1014 | * |  |  | Duplikat persis dari raw_row_id 493 (invoice INV500201, SKU Tos Tos Tortilla BBQ 140g). |
| 913 | 914 | INV500386 | OUT1020 | * |  |  | Duplikat persis dari raw_row_id 912 (invoice INV500386, SKU Sukro Pedas 100g). |
| 1873 | 1874 | INV500791 | OUT1038 | * |  |  | Duplikat persis dari raw_row_id 1871 (invoice INV500791, SKU Kacang Kulit 250g). |

### DQ-07 Baris retur (dokumen RTR, qty dan nilai negatif)

- Tingkat: sedang; level: row; tindakan: ditandai
- Jumlah: 1 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `is_return`
- Keputusan: Retur tetap disimpan sebagai retur (is_return = true). Penjualan bruto hanya menjumlah baris penjualan; retur dilaporkan terpisah dan dikurangkan saat menghitung penjualan neto setelah retur.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 1264 | 1265 | RTR900001 | OUT1049 | invoice_no | RTR900001 | RTR900001 | Dokumen retur, qty -2, net -528000. Disimpan sebagai retur. |

### DQ-08 Retur tanpa pembelian yang cukup di periode data

- Tingkat: rendah; level: row; tindakan: ditandai
- Jumlah: 1 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_return_unmatched`
- Keputusan: Ditandai saja. Retur bisa berasal dari pembelian sebelum September 2026 yang tidak ada di file. Perlu konfirmasi ke tim sales/finance.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 1264 | 1265 | RTR900001 | OUT1049 | qty_carton | -2 | -2 | Retur 2 karton Tos Tos Tortilla BBQ 140g, sedangkan pembelian outlet OUT1049 untuk SKU ini sampai tanggal retur hanya 1 karton (invoice: INV500527). |

### DQ-09 Nomor invoice di luar urutan (nomor lebih besar dari invoice bertanggal lebih akhir)

- Tingkat: sedang; level: invoice; tindakan: ditandai
- Jumlah: 25 baris, 25 entitas, sisa setelah cleaning 0
- Catatan: INV500799 s.d. INV500823
- Kolom tanda di fact: `dq_late_numbered_invoice`
- Keputusan: Nomor invoice reguler naik mengikuti tanggal. Invoice yang nomornya tidak cocok dengan urutan tanggal ditandai sebagai blok yang diterbitkan terlambat. Baris tetap dihitung karena angkanya konsisten, tetapi bisa dikecualikan lewat tanda dq_late_numbered_invoice.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 187 | 188 | INV500818 | OUT1045 | invoice_no | INV500818 | INV500818 | Nomor INV500818 bertanggal 2026-09-05 lebih besar dari 722 invoice reguler bertanggal lebih akhir, terakhir INV500798 (2026-10-31). |
| 234 | 235 | INV500802 | OUT1026 | invoice_no | INV500802 | INV500802 | Nomor INV500802 bertanggal 2026-09-07 lebih besar dari 704 invoice reguler bertanggal lebih akhir, terakhir INV500798 (2026-10-31). |
| 235 | 236 | INV500807 | OUT1035 | invoice_no | INV500807 | INV500807 | Nomor INV500807 bertanggal 2026-09-07 lebih besar dari 704 invoice reguler bertanggal lebih akhir, terakhir INV500798 (2026-10-31). |
| 341 | 342 | INV500819 | OUT1045 | invoice_no | INV500819 | INV500819 | Nomor INV500819 bertanggal 2026-09-10 lebih besar dari 660 invoice reguler bertanggal lebih akhir, terakhir INV500798 (2026-10-31). |
| 444 | 445 | INV500820 | OUT1045 | invoice_no | INV500820 | INV500820 | Nomor INV500820 bertanggal 2026-09-14 lebih besar dari 618 invoice reguler bertanggal lebih akhir, terakhir INV500798 (2026-10-31). |

### DQ-10 Outlet yang hanya muncul di invoice di luar urutan

- Tingkat: sedang; level: outlet; tindakan: ditandai
- Jumlah: 25 baris, 5 entitas, sisa setelah cleaning 0
- Catatan: OUT1003, OUT1026, OUT1035, OUT1042, OUT1045
- Kolom tanda di fact: `dq_suspect_outlet`
- Keputusan: Outlet ini tidak pernah muncul di urutan invoice reguler. Semua barisnya 1 karton tanpa diskon. Tetap disimpan dan ditandai dq_suspect_outlet; perlu dicek ke master outlet.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 187 | 188 | INV500818 | OUT1045 | outlet_id | OUT1045 | OUT1045 | Outlet OUT1045 hanya muncul di invoice di luar urutan. |
| 234 | 235 | INV500802 | OUT1026 | outlet_id | OUT1026 | OUT1026 | Outlet OUT1026 hanya muncul di invoice di luar urutan. |
| 235 | 236 | INV500807 | OUT1035 | outlet_id | OUT1035 | OUT1035 | Outlet OUT1035 hanya muncul di invoice di luar urutan. |
| 341 | 342 | INV500819 | OUT1045 | outlet_id | OUT1045 | OUT1045 | Outlet OUT1045 hanya muncul di invoice di luar urutan. |
| 444 | 445 | INV500820 | OUT1045 | outlet_id | OUT1045 | OUT1045 | Outlet OUT1045 hanya muncul di invoice di luar urutan. |

### DQ-11 Transaksi di hari non-dagang (Minggu atau libur nasional)

- Tingkat: rendah; level: row; tindakan: ditandai
- Jumlah: 1 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_non_trading_day`
- Keputusan: Di data ini hari Minggu kosong kecuali satu baris. Baris ditandai, tidak diubah.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 838 | 839 | INV500813 | OUT1042 | date | 2026-09-27 | 2026-09-27 | Transaksi pada hari Minggu 2026-09-27. |

### DQ-12 Nama outlet sama, outlet_id berbeda, di cabang yang sama

- Tingkat: sedang; level: outlet; tindakan: ditandai
- Jumlah: 25 baris, 2 entitas, sisa setelah cleaning 0
- Catatan: OUT1001, OUT1003
- Kolom tanda di fact: `dq_outlet_name_shared_in_branch`
- Keputusan: Kemungkinan outlet ganda di master data. Kedua id dipertahankan karena tidak ada bukti untuk menggabungkan; baris ditandai dq_outlet_name_shared_in_branch.

| raw_row_id | baris file | invoice | outlet | kolom | sebelum | sesudah | alasan |
|---|---|---|---|---|---|---|---|
| 44 | 45 | INV500019 | OUT1001 | outlet_id | OUT1001 | OUT1001 | Nama 'Toko Sinar Abadi' juga dipakai OUT1003 di cabang Jakarta Barat. |
| 123 | 124 | INV500049 | OUT1001 | outlet_id | OUT1001 | OUT1001 | Nama 'Toko Sinar Abadi' juga dipakai OUT1003 di cabang Jakarta Barat. |
| 124 | 125 | INV500049 | OUT1001 | outlet_id | OUT1001 | OUT1001 | Nama 'Toko Sinar Abadi' juga dipakai OUT1003 di cabang Jakarta Barat. |
| 377 | 378 | INV500153 | OUT1001 | outlet_id | OUT1001 | OUT1001 | Nama 'Toko Sinar Abadi' juga dipakai OUT1003 di cabang Jakarta Barat. |
| 378 | 379 | INV500153 | OUT1001 | outlet_id | OUT1001 | OUT1001 | Nama 'Toko Sinar Abadi' juga dipakai OUT1003 di cabang Jakarta Barat. |

### DQ-13 Nama outlet sama, outlet_id berbeda, di cabang berbeda

- Tingkat: info; level: outlet; tindakan: dicatat
- Jumlah: 463 baris, 18 entitas, sisa setelah cleaning 0
- Catatan: 8 nama dipakai 18 outlet_id
- Keputusan: Nama toko umum yang dipakai di kota berbeda. Dianggap outlet berbeda. Dicatat di dim_outlet (name_shared_count) agar laporan per nama tidak tergabung keliru.

### DQ-14 gross_sales_idr = qty_carton x price_per_carton_idr

- Tingkat: tinggi; level: row; tindakan: dikarantina
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Keputusan: Baris yang tidak cocok masuk karantina karena tidak bisa ditentukan angka mana yang benar.

### DQ-15 net_sales_idr = gross_sales_idr - discount_idr

- Tingkat: tinggi; level: row; tindakan: dikarantina
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Keputusan: Baris yang tidak cocok masuk karantina karena tidak bisa ditentukan angka mana yang benar.

### DQ-16 Pola diskon: 0, 2, 3 atau 5 persen dari gross, dibulatkan ke Rp100 terdekat

- Tingkat: rendah; level: row; tindakan: ditandai
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_discount_off_pattern`
- Keputusan: Selisih sampai Rp40 terhadap persentase tepat adalah efek pembulatan ke Rp100, bukan kesalahan. Baris di luar pola ditandai dq_discount_off_pattern.

### DQ-17 Satu harga per SKU

- Tingkat: sedang; level: row; tindakan: ditandai
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_price_off_list`
- Keputusan: Harga per karton dibandingkan dengan harga terbanyak untuk SKU itu; yang berbeda ditandai.

### DQ-18 Satu brand per SKU

- Tingkat: sedang; level: row; tindakan: ditandai
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_brand_mismatch`
- Keputusan: SKU yang tercatat di brand berbeda ditandai.

### DQ-19 Atribut outlet stabil (nama, tipe, cabang, region per outlet_id)

- Tingkat: sedang; level: outlet; tindakan: ditandai
- Jumlah: 14 baris, 10 entitas, sisa setelah cleaning 0
- Catatan: mentah: OUT1004, OUT1005, OUT1006, OUT1013, OUT1014, OUT1015, OUT1017, OUT1020, OUT1032, OUT1033
- Kolom tanda di fact: `dq_outlet_attr_conflict`
- Keputusan: Di data mentah tidak stabil hanya karena DQ-03 dan DQ-04. Setelah perbaikan dicek ulang; sisa perbedaan ditandai.

### DQ-20 Satu region per cabang

- Tingkat: sedang; level: row; tindakan: ditandai
- Jumlah: 10 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_branch_region_conflict`
- Keputusan: Di data mentah tidak stabil hanya karena DQ-03. Setelah perbaikan dicek ulang.

### DQ-21 Salesman hanya di satu cabang

- Tingkat: sedang; level: row; tindakan: ditandai
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_salesman_branch_conflict`
- Keputusan: Salesman yang muncul di lebih dari satu cabang ditandai pada baris cabang minoritas.

### DQ-22 Header invoice sama di semua baris (tanggal, outlet, cabang, region, salesman)

- Tingkat: sedang; level: invoice; tindakan: ditandai
- Jumlah: 19 baris, 19 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_invoice_header_conflict`
- Keputusan: Di data mentah tidak sama hanya karena DQ-03, DQ-04 dan DQ-05. Setelah perbaikan dicek ulang.

### DQ-23 SKU tidak berulang dalam satu invoice (setelah duplikat persis dikarantina)

- Tingkat: rendah; level: row; tindakan: ditandai
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Catatan: mentah: 6 baris (semuanya duplikat persis DQ-06)
- Kolom tanda di fact: `dq_repeated_sku_in_invoice`
- Keputusan: SKU yang muncul dua kali dengan angka berbeda ditandai, tidak digabung.

### DQ-24 Tanda qty sesuai jenis dokumen (INV positif, RTR negatif, tidak nol)

- Tingkat: tinggi; level: row; tindakan: dikarantina
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Keputusan: Baris dengan qty nol atau tanda yang tidak sesuai jenis dokumennya masuk karantina.

### DQ-25 Lebih dari satu invoice penjualan per outlet per hari

- Tingkat: info; level: outlet; tindakan: ditandai
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Catatan: 1 retur di hari yang sama dengan invoice penjualan outlet yang sama (bukan pelanggaran)
- Kolom tanda di fact: `dq_multi_invoice_day`
- Keputusan: Ditandai saja; bisa kunjungan ulang yang sah.

### DQ-26 Hari dagang (Senin-Sabtu) tanpa transaksi

- Tingkat: info; level: date; tindakan: dicatat
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Catatan: tidak ada
- Keputusan: Dicatat di dim_date (has_sales). Tidak mengubah baris.

### DQ-27 Tanggal di luar periode yang diharapkan

- Tingkat: sedang; level: row; tindakan: ditandai
- Jumlah: 0 baris, 0 entitas, sisa setelah cleaning 0
- Kolom tanda di fact: `dq_out_of_period`
- Keputusan: Baris di luar periode ditandai dq_out_of_period dan tidak dibuang.


# 01 Profiling data mentah

Dokumen ini dibuat otomatis oleh `make data` dari `data/raw/sales_raw.csv` sebelum cleaning. Angka mentah lengkap ada di `docs/01-profiling.json`.

## Ringkasan

- File: `data/raw/sales_raw.csv`, sha256 `48b9f90ddaa91e0033ada4feb3cb47a8aaf490774165d266223be1da34e6741f`
- 1891 baris, 15 kolom, tanggal 2026-09-01 s.d. 2026-10-31
- 824 nomor dokumen: INV 823, RTR 1
- Total mentah: 8754 karton, gross Rp1.758.432.000, diskon Rp30.395.100, net Rp1.728.036.900
- Baris duplikat persis: 3. File terurut menurut tanggal: ya.

## Skema dan tipe

| Kolom | Tipe terbaca | Kosong | Spasi tepi | Nilai unik | Unik setelah trim+casefold | Rentang |
|---|---|---:|---:|---:|---:|---|
| date | date | 0 | 0 | 54 | 54 | 2026-09-01 s.d. 2026-10-31 |
| invoice_no | string | 0 | 0 | 824 | 824 |  |
| region | string | 0 | 0 | 10 | 7 |  |
| branch | string | 0 | 0 | 13 | 13 |  |
| outlet_id | string | 0 | 0 | 52 | 52 |  |
| outlet_name | string | 0 | 4 | 45 | 42 |  |
| outlet_type | string | 0 | 0 | 4 | 4 |  |
| salesman | string | 5 | 0 | 27 | 27 |  |
| brand | string | 0 | 0 | 8 | 8 |  |
| sku | string | 0 | 0 | 13 | 13 |  |
| qty_carton | integer | 0 | 0 | 16 | 16 | -2 s.d. 15 |
| price_per_carton_idr | integer | 0 | 0 | 11 | 11 | 120000 s.d. 312000 |
| gross_sales_idr | integer | 0 | 0 | 127 | 127 | -528000 s.d. 4680000 |
| discount_idr | integer | 0 | 0 | 215 | 215 | 0 s.d. 234000 |
| net_sales_idr | integer | 0 | 0 | 396 | 396 | -528000 s.d. 4680000 |

## Nilai per kolom kategori

### region

| region | baris |
|---|---:|
| Jabodetabek | 503 |
| Jawa Barat | 385 |
| Sumatera | 282 |
| Jawa Timur | 279 |
| Jawa Tengah | 253 |
| Kalimantan | 179 |
| JAWA BARAT | 4 |
| Jabar | 4 |
| JABODETABEK | 1 |
| JAWA TIMUR | 1 |

### outlet_type

| outlet_type | baris |
|---|---:|
| Toko Kelontong | 753 |
| Grosir | 569 |
| Warung | 363 |
| Minimarket | 206 |

### brand

| brand | baris |
|---|---:|
| Kacang Dua Kelinci | 713 |
| Sukro | 325 |
| Tos Tos | 299 |
| Tic Tac | 247 |
| Pilus | 86 |
| Deka | 84 |
| Usagi | 73 |
| Roni | 64 |

### qty_carton

| qty_carton | baris |
|---|---:|
| 4 | 382 |
| 1 | 354 |
| 2 | 336 |
| 3 | 286 |
| 8 | 57 |
| 15 | 53 |
| 6 | 53 |
| 10 | 51 |
| 11 | 51 |
| 13 | 47 |
| 14 | 47 |
| 9 | 46 |
| 12 | 44 |
| 5 | 44 |
| 7 | 39 |
| -2 | 1 |

### sku dan harga per karton

| SKU | Brand | Harga per karton | Baris |
|---|---|---:|---:|
| Kacang Kulit 250g | Kacang Dua Kelinci | Rp312.000 | 247 |
| Kacang Kulit 70g | Kacang Dua Kelinci | Rp198.000 | 236 |
| Kacang Atom 40g | Kacang Dua Kelinci | Rp156.000 | 230 |
| Sukro Pedas 100g | Sukro | Rp186.000 | 177 |
| Tos Tos Tortilla Nacho 65g | Tos Tos | Rp192.000 | 155 |
| Sukro Original 100g | Sukro | Rp186.000 | 148 |
| Tos Tos Tortilla BBQ 140g | Tos Tos | Rp264.000 | 144 |
| Tic Tac Original 80g | Tic Tac | Rp168.000 | 128 |
| Tic Tac Sapi Panggang 80g | Tic Tac | Rp168.000 | 119 |
| Pilus Garuda Rumput Laut 95g | Pilus | Rp174.000 | 86 |
| Deka Wafer Cokelat 120g | Deka | Rp216.000 | 84 |
| Usagi Wheat Puffs 45g | Usagi | Rp144.000 | 73 |
| Roni Mie Goreng 30g | Roni | Rp120.000 | 64 |

## Kalender

54 dari 61 hari punya transaksi. Hari tanpa transaksi: 2026-09-06 (Minggu), 2026-09-13 (Minggu), 2026-09-20 (Minggu), 2026-10-04 (Minggu), 2026-10-11 (Minggu), 2026-10-18 (Minggu), 2026-10-25 (Minggu).

| Hari | baris |
|---|---:|
| Senin | 275 |
| Selasa | 308 |
| Rabu | 334 |
| Kamis | 332 |
| Jumat | 309 |
| Sabtu | 332 |
| Minggu | 1 |

| Bulan | baris |
|---|---:|
| 2026-09 | 929 |
| 2026-10 | 962 |

<details><summary>Baris per tanggal</summary>

| Tanggal | baris |
|---|---:|
| 2026-09-01 | 43 |
| 2026-09-02 | 46 |
| 2026-09-03 | 33 |
| 2026-09-04 | 34 |
| 2026-09-05 | 31 |
| 2026-09-07 | 48 |
| 2026-09-08 | 20 |
| 2026-09-09 | 37 |
| 2026-09-10 | 49 |
| 2026-09-11 | 35 |
| 2026-09-12 | 29 |
| 2026-09-14 | 39 |
| 2026-09-15 | 41 |
| 2026-09-16 | 35 |
| 2026-09-17 | 34 |
| 2026-09-18 | 33 |
| 2026-09-19 | 37 |
| 2026-09-21 | 35 |
| 2026-09-22 | 30 |
| 2026-09-23 | 39 |
| 2026-09-24 | 38 |
| 2026-09-25 | 42 |
| 2026-09-26 | 29 |
| 2026-09-27 | 1 |
| 2026-09-28 | 25 |
| 2026-09-29 | 34 |
| 2026-09-30 | 32 |
| 2026-10-01 | 40 |
| 2026-10-02 | 35 |
| 2026-10-03 | 55 |
| 2026-10-05 | 32 |
| 2026-10-06 | 42 |
| 2026-10-07 | 37 |
| 2026-10-08 | 39 |
| 2026-10-09 | 26 |
| 2026-10-10 | 29 |
| 2026-10-12 | 29 |
| 2026-10-13 | 30 |
| 2026-10-14 | 33 |
| 2026-10-15 | 20 |
| 2026-10-16 | 25 |
| 2026-10-17 | 41 |
| 2026-10-19 | 38 |
| 2026-10-20 | 31 |
| 2026-10-21 | 35 |
| 2026-10-22 | 39 |
| 2026-10-23 | 48 |
| 2026-10-24 | 34 |
| 2026-10-26 | 29 |
| 2026-10-27 | 37 |
| 2026-10-28 | 40 |
| 2026-10-29 | 40 |
| 2026-10-30 | 31 |
| 2026-10-31 | 47 |

</details>

## Baris per region (teks mentah), cabang, tipe outlet

| region (mentah) | baris |
|---|---:|
| Jabodetabek | 503 |
| Jawa Barat | 385 |
| Sumatera | 282 |
| Jawa Timur | 279 |
| Jawa Tengah | 253 |
| Kalimantan | 179 |
| JAWA BARAT | 4 |
| Jabar | 4 |
| JABODETABEK | 1 |
| JAWA TIMUR | 1 |

| Cabang | baris |
|---|---:|
| Bandung | 215 |
| Tangerang | 207 |
| Cirebon | 178 |
| Medan | 155 |
| Bekasi | 153 |
| Jakarta Barat | 144 |
| Solo | 142 |
| Surabaya | 141 |
| Malang | 139 |
| Palembang | 127 |
| Balikpapan | 113 |
| Semarang | 111 |
| Banjarmasin | 66 |

| Tipe outlet | baris |
|---|---:|
| Toko Kelontong | 753 |
| Grosir | 569 |
| Warung | 363 |
| Minimarket | 206 |

## Baris per salesman dan outlet

| Salesman | baris |
|---|---:|
| Gita | 118 |
| Joko | 118 |
| Citra | 111 |
| Hendra | 97 |
| Dedi | 96 |
| Andi | 87 |
| Nanda | 79 |
| Teguh | 79 |
| Eko | 77 |
| Fajar | 76 |
| Wahyu | 75 |
| Oki | 72 |
| Yudi | 72 |
| Sari | 71 |
| Putri | 69 |
| Rizal | 67 |
| Dewi | 63 |
| Kurnia | 63 |
| Made | 63 |
| Indra | 59 |
| Budi | 57 |
| Zaki | 55 |
| Feri | 50 |
| Lestari | 47 |
| Agus | 33 |
| Bayu | 32 |
| (kosong) | 5 |

<details><summary>Baris per outlet_id</summary>

| outlet_id | baris |
|---|---:|
| OUT1007 | 96 |
| OUT1014 | 85 |
| OUT1004 | 80 |
| OUT1037 | 73 |
| OUT1025 | 69 |
| OUT1036 | 62 |
| OUT1044 | 61 |
| OUT1017 | 58 |
| OUT1019 | 58 |
| OUT1013 | 55 |
| OUT1006 | 52 |
| OUT1015 | 52 |
| OUT1009 | 49 |
| OUT1020 | 47 |
| OUT1012 | 46 |
| OUT1050 | 43 |
| OUT1029 | 42 |
| OUT1038 | 41 |
| OUT1002 | 39 |
| OUT1030 | 39 |
| OUT1041 | 38 |
| OUT1033 | 37 |
| OUT1027 | 36 |
| OUT1034 | 35 |
| OUT1005 | 33 |
| OUT1010 | 33 |
| OUT1028 | 32 |
| OUT1032 | 32 |
| OUT1023 | 31 |
| OUT1024 | 31 |
| OUT1046 | 31 |
| OUT1039 | 29 |
| OUT1031 | 28 |
| OUT1049 | 28 |
| OUT1021 | 27 |
| OUT1008 | 26 |
| OUT1011 | 25 |
| OUT1052 | 25 |
| OUT1016 | 23 |
| OUT1001 | 22 |
| OUT1022 | 22 |
| OUT1043 | 22 |
| OUT1051 | 17 |
| OUT1018 | 15 |
| OUT1048 | 15 |
| OUT1047 | 14 |
| OUT1040 | 12 |
| OUT1042 | 6 |
| OUT1045 | 6 |
| OUT1026 | 5 |
| OUT1035 | 5 |
| OUT1003 | 3 |

</details>

## Invoice

| Baris per invoice | invoice |
|---|---:|
| 1 | 234 |
| 2 | 245 |
| 3 | 213 |
| 4 | 132 |

- Nomor INV: 500001 s.d. 500823, celah nomor: tidak ada
- Invoice dengan lebih dari satu tanggal: 0
- Karton per invoice: median 7, rata-rata 10.62, maks 55
- Net per invoice: median Rp1.386.400, rata-rata Rp2.097.132, maks Rp10.764.000

## Qty per tipe outlet

| Tipe outlet | Baris | Min | Median | Maks | Rata-rata |
|---|---:|---:|---:|---:|---:|
| Grosir | 569 | 4 | 10 | 15 | 9.65 |
| Minimarket | 206 | 1 | 2 | 4 | 2.45 |
| Toko Kelontong | 753 | 1 | 2 | 4 | 2.43 |
| Warung | 363 | -2 | 3 | 4 | 2.55 |

Grosir membeli 4 sampai 15 karton per baris; tipe lain 1 sampai 4 karton. Perbandingan antar outlet harus memperhitungkan tipe outlet.

## Persentase diskon per baris (diskon / gross)

| Diskon % | baris |
|---|---:|
| 0.0 | 940 |
| 1.98 | 3 |
| 1.99 | 91 |
| 2.0 | 155 |
| 2.01 | 48 |
| 2.02 | 11 |
| 2.98 | 5 |
| 2.99 | 35 |
| 3.0 | 169 |
| 3.01 | 84 |
| 3.02 | 4 |
| 5.0 | 346 |

Nilai seperti 1,99% atau 3,01% bukan tarif tersendiri. Semua 1.891 baris cocok dengan 0, 2, 3 atau 5 persen dari gross yang dibulatkan ke Rp100 terdekat (lihat DQ-16).


# 02 Kamus data

Dibuat otomatis oleh `make data`. Semua tabel ada di `data/processed/` dalam format Parquet dan CSV (nama file sama). Model berbentuk star schema: satu tabel fakta per baris invoice dan lima dimensi.

```
dim_date ─┐
dim_geo ──┤
dim_outlet┼── fact_sales_line (1 baris = 1 SKU pada 1 dokumen)
dim_product┤
dim_salesman┘
```

Ukuran utama: penjualan neto = jumlah `net_sales_idr` baris `sale`. Retur dihitung terpisah (`is_return = true`). Neto setelah retur = neto penjualan + neto retur (retur bernilai negatif).

File pendukung:

- `dq_log.csv`: satu baris per perubahan, inferensi, tanda atau karantina (raw_row_id, source_line, rule_id, column, before, after, action, reason). source_line = nomor baris di file CSV termasuk header.
- `quarantine_lines.csv`: baris yang dikeluarkan dari fakta, dengan nilai mentah, rule_id dan alasan.
- `reconciliation_bridge.csv`: jembatan total mentah ke bersih per bulan dan region.
- `sales_vs_returns.csv`: total penjualan dan retur per bulan dan region.
- `dq_summary.json`: jumlah per aturan.

## fact_sales_line

1888 baris.

| kolom | tipe | contoh | keterangan |
|---|---|---|---|
| line_id | int64 | 1 | Id baris, sama dengan raw_row_id (nomor baris data di file mentah, header tidak dihitung). |
| date_key | int64 | 20260901 | Tanggal dalam bentuk YYYYMMDD, kunci ke dim_date. |
| date | datetime64[s] | 2026-09-01 | Tanggal dokumen. |
| year_month | str | 2026-09 | Bulan dokumen, YYYY-MM. |
| invoice_no | str | INV500001 | Nomor dokumen. INV = penjualan, RTR = retur. |
| document_type | str | sale | sale atau return. |
| is_return | bool | False | true untuk baris retur. |
| outlet_id | str | OUT1004 | Kunci ke dim_outlet. |
| geo_key | str | jakarta-barat | Kunci ke dim_geo (slug nama cabang). |
| region | str | Jabodetabek | Region baku (6 nilai). |
| branch | str | Jakarta Barat | Cabang. |
| salesman_code | str | andi | Kunci ke dim_salesman (slug nama). Kosong bila salesman tidak diketahui. |
| salesman | str | Andi | Nama salesman setelah DQ-05. |
| sku_code | str | kacang-kulit-70g | Kunci ke dim_product (slug SKU). |
| brand | str | Kacang Dua Kelinci | Brand. |
| sku | str | Kacang Kulit 70g | Nama SKU. |
| qty_carton | int64 | 5 | Jumlah karton. Negatif untuk retur. |
| price_per_carton_idr | int64 | 198000 | Harga per karton dalam rupiah. |
| gross_sales_idr | int64 | 990000 | qty_carton x price_per_carton_idr. |
| discount_idr | int64 | 49500 | Diskon rupiah, 0/2/3/5% dari gross dibulatkan ke Rp100. |
| net_sales_idr | int64 | 940500 | gross_sales_idr - discount_idr. |
| discount_rate_pct | float64 | 5.0 | discount_idr / gross_sales_idr x 100, dua desimal. |
| dq_salesman_inferred | bool | False | DQ-05: Salesman kosong. |
| dq_return_unmatched | bool | False | DQ-08: Retur tanpa pembelian yang cukup di periode data. |
| dq_late_numbered_invoice | bool | False | DQ-09: Nomor invoice di luar urutan (nomor lebih besar dari invoice bertanggal lebih akhir). |
| dq_suspect_outlet | bool | False | DQ-10: Outlet yang hanya muncul di invoice di luar urutan. |
| dq_non_trading_day | bool | False | DQ-11: Transaksi di hari non-dagang (Minggu atau libur nasional). |
| dq_outlet_name_shared_in_branch | bool | False | DQ-12: Nama outlet sama, outlet_id berbeda, di cabang yang sama. |
| dq_discount_off_pattern | bool | False | DQ-16: Pola diskon: 0, 2, 3 atau 5 persen dari gross, dibulatkan ke Rp100 terdekat. |
| dq_price_off_list | bool | False | DQ-17: Satu harga per SKU. |
| dq_brand_mismatch | bool | False | DQ-18: Satu brand per SKU. |
| dq_outlet_attr_conflict | bool | False | DQ-19: Atribut outlet stabil (nama, tipe, cabang, region per outlet_id). |
| dq_branch_region_conflict | bool | False | DQ-20: Satu region per cabang. |
| dq_salesman_branch_conflict | bool | False | DQ-21: Salesman hanya di satu cabang. |
| dq_invoice_header_conflict | bool | False | DQ-22: Header invoice sama di semua baris (tanggal, outlet, cabang, region, salesman). |
| dq_repeated_sku_in_invoice | bool | False | DQ-23: SKU tidak berulang dalam satu invoice (setelah duplikat persis dikarantina). |
| dq_multi_invoice_day | bool | False | DQ-25: Lebih dari satu invoice penjualan per outlet per hari. |
| dq_out_of_period | bool | False | DQ-27: Tanggal di luar periode yang diharapkan. |
| dq_flags | str |  | Daftar tanda DQ yang aktif pada baris, dipisah titik koma. |

## dim_date

61 baris.

| kolom | tipe | contoh | keterangan |
|---|---|---|---|
| date_key | int64 | 20260901 | YYYYMMDD, kunci. |
| date | datetime64[us] | 2026-09-01 | Tanggal. |
| day_of_week | int64 | 2 | 1 = Senin sampai 7 = Minggu. |
| day_name_id | str | Selasa | Nama hari dalam bahasa Indonesia. |
| iso_year | int64 | 2026 | Tahun ISO. |
| iso_week | int64 | 36 | Minggu ISO (Senin sebagai awal minggu). |
| week_start | datetime64[us] | 2026-08-31 | Tanggal Senin di minggu itu. |
| month | int64 | 9 | Nomor bulan. |
| month_name_id | str | September | Nama bulan dalam bahasa Indonesia. |
| year_month | str | 2026-09 | YYYY-MM. |
| is_sunday | bool | False | true untuk hari Minggu. |
| is_holiday | bool | False | true untuk libur nasional (data/reference/holidays_id.csv). |
| holiday_name | str |  | Nama libur nasional. |
| is_trading_day | bool | True | Senin sampai Sabtu dan bukan libur nasional. |
| has_sales | bool | True | true bila ada baris penjualan pada tanggal itu. |

## dim_geo

13 baris.

| kolom | tipe | contoh | keterangan |
|---|---|---|---|
| geo_key | str | bekasi | Slug cabang, kunci. |
| region | str | Jabodetabek | Region baku. |
| branch | str | Bekasi | Cabang. |
| n_outlets | int64 | 4 | Jumlah outlet di cabang. |
| n_salesmen | int64 | 2 | Jumlah salesman di cabang. |

## dim_product

13 baris.

| kolom | tipe | contoh | keterangan |
|---|---|---|---|
| sku_code | str | deka-wafer-cokelat-120g | Slug SKU, kunci. |
| brand | str | Deka | Brand. |
| sku | str | Deka Wafer Cokelat 120g | Nama SKU. |
| pack_size_g | Int64 | 120 | Ukuran kemasan dalam gram, diambil dari nama SKU. |
| list_price_per_carton_idr | int64 | 216000 | Harga per karton yang berlaku di data. |

## dim_salesman

26 baris.

| kolom | tipe | contoh | keterangan |
|---|---|---|---|
| salesman_code | str | agus | Slug nama, kunci. |
| salesman | str | Agus | Nama salesman. |
| branch | str | Banjarmasin | Cabang tempat salesman bertugas. |
| region | str | Kalimantan | Region cabang. |
| n_outlets | int64 | 4 | Jumlah outlet yang dilayani. |
| n_invoices | int64 | 14 | Jumlah dokumen. |

## dim_outlet

52 baris.

| kolom | tipe | contoh | keterangan |
|---|---|---|---|
| outlet_id | str | OUT1001 | Id outlet dari sumber. |
| outlet_name | str | Toko Sinar Abadi | Nama outlet setelah DQ-04. |
| outlet_type | str | Toko Kelontong | Grosir, Minimarket, Toko Kelontong atau Warung. |
| branch | str | Jakarta Barat | Cabang outlet. |
| region | str | Jabodetabek | Region baku. |
| first_date | datetime64[s] | 2026-09-02 | Tanggal transaksi pertama di data. |
| last_date | datetime64[s] | 2026-10-28 | Tanggal transaksi terakhir di data. |
| n_invoices | int64 | 9 | Jumlah dokumen (penjualan dan retur). |
| n_salesmen | int64 | 2 | Jumlah salesman yang pernah melayani outlet. |
| dq_suspect_outlet | bool | False | DQ-10: Outlet yang hanya muncul di invoice di luar urutan. |
| dq_outlet_name_shared_in_branch | bool | True | DQ-12: Nama outlet sama, outlet_id berbeda, di cabang yang sama. |
| name_shared_count | int64 | 3 | Jumlah outlet_id yang memakai nama yang sama (DQ-13). 1 berarti nama unik. |


# 02 Rekonsiliasi mentah ke bersih

Dibuat otomatis oleh `make data`. Untuk setiap bulan dan label region seperti tertulis di file mentah: mentah + koreksi per aturan = bersih. Kolom selisih harus 0 untuk semua ukuran; test `tests/test_reconciliation.py` memeriksanya.

- DQ-03 memindahkan baris dari label region tidak baku ke label baku (minus di label lama, plus di label baru).
- DQ-06 mengeluarkan baris duplikat persis ke karantina.

## Baris

| bulan | region (label mentah) | mentah | DQ-03 | DQ-06 | bersih | selisih |
|---|---|---|---|---|---|---|
| 2026-09 | JABODETABEK | 1 | -1 | 0 | 0 | 0 |
| 2026-09 | JAWA BARAT | 1 | -1 | 0 | 0 | 0 |
| 2026-09 | Jabar | 3 | -3 | 0 | 0 | 0 |
| 2026-09 | Jabodetabek | 256 | 1 | 0 | 257 | 0 |
| 2026-09 | Jawa Barat | 199 | 4 | -2 | 201 | 0 |
| 2026-09 | Jawa Tengah | 123 | 0 | 0 | 123 | 0 |
| 2026-09 | Jawa Timur | 107 | 0 | 0 | 107 | 0 |
| 2026-09 | Kalimantan | 82 | 0 | 0 | 82 | 0 |
| 2026-09 | Sumatera | 157 | 0 | 0 | 157 | 0 |
| 2026-10 | JAWA BARAT | 3 | -3 | 0 | 0 | 0 |
| 2026-10 | JAWA TIMUR | 1 | -1 | 0 | 0 | 0 |
| 2026-10 | Jabar | 1 | -1 | 0 | 0 | 0 |
| 2026-10 | Jabodetabek | 247 | 0 | 0 | 247 | 0 |
| 2026-10 | Jawa Barat | 186 | 4 | 0 | 190 | 0 |
| 2026-10 | Jawa Tengah | 130 | 0 | 0 | 130 | 0 |
| 2026-10 | Jawa Timur | 172 | 1 | 0 | 173 | 0 |
| 2026-10 | Kalimantan | 97 | 0 | 0 | 97 | 0 |
| 2026-10 | Sumatera | 125 | 0 | -1 | 124 | 0 |
| Total |  | 1891 | 0 | -3 | 1888 | 0 |

## Karton

| bulan | region (label mentah) | mentah | DQ-03 | DQ-06 | bersih | selisih |
|---|---|---|---|---|---|---|
| 2026-09 | JABODETABEK | 4 | -4 | 0 | 0 | 0 |
| 2026-09 | JAWA BARAT | 4 | -4 | 0 | 0 | 0 |
| 2026-09 | Jabar | 13 | -13 | 0 | 0 | 0 |
| 2026-09 | Jabodetabek | 1217 | 4 | 0 | 1221 | 0 |
| 2026-09 | Jawa Barat | 838 | 17 | -8 | 847 | 0 |
| 2026-09 | Jawa Tengah | 603 | 0 | 0 | 603 | 0 |
| 2026-09 | Jawa Timur | 366 | 0 | 0 | 366 | 0 |
| 2026-09 | Kalimantan | 365 | 0 | 0 | 365 | 0 |
| 2026-09 | Sumatera | 916 | 0 | 0 | 916 | 0 |
| 2026-10 | JAWA BARAT | 13 | -13 | 0 | 0 | 0 |
| 2026-10 | JAWA TIMUR | 3 | -3 | 0 | 0 | 0 |
| 2026-10 | Jabar | 3 | -3 | 0 | 0 | 0 |
| 2026-10 | Jabodetabek | 1313 | 0 | 0 | 1313 | 0 |
| 2026-10 | Jawa Barat | 695 | 16 | 0 | 711 | 0 |
| 2026-10 | Jawa Tengah | 512 | 0 | 0 | 512 | 0 |
| 2026-10 | Jawa Timur | 732 | 3 | 0 | 735 | 0 |
| 2026-10 | Kalimantan | 359 | 0 | 0 | 359 | 0 |
| 2026-10 | Sumatera | 798 | 0 | -1 | 797 | 0 |
| Total |  | 8754 | 0 | -9 | 8745 | 0 |

## Gross (Rp)

| bulan | region (label mentah) | mentah | DQ-03 | DQ-06 | bersih | selisih |
|---|---|---|---|---|---|---|
| 2026-09 | JABODETABEK | 672.000 | -672.000 | 0 | 0 | 0 |
| 2026-09 | JAWA BARAT | 768.000 | -768.000 | 0 | 0 | 0 |
| 2026-09 | Jabar | 2.160.000 | -2.160.000 | 0 | 0 | 0 |
| 2026-09 | Jabodetabek | 242.640.000 | 672.000 | 0 | 243.312.000 | 0 |
| 2026-09 | Jawa Barat | 169.002.000 | 2.928.000 | -1.800.000 | 170.130.000 | 0 |
| 2026-09 | Jawa Tengah | 119.238.000 | 0 | 0 | 119.238.000 | 0 |
| 2026-09 | Jawa Timur | 73.710.000 | 0 | 0 | 73.710.000 | 0 |
| 2026-09 | Kalimantan | 75.396.000 | 0 | 0 | 75.396.000 | 0 |
| 2026-09 | Sumatera | 181.554.000 | 0 | 0 | 181.554.000 | 0 |
| 2026-10 | JAWA BARAT | 2.316.000 | -2.316.000 | 0 | 0 | 0 |
| 2026-10 | JAWA TIMUR | 594.000 | -594.000 | 0 | 0 | 0 |
| 2026-10 | Jabar | 594.000 | -594.000 | 0 | 0 | 0 |
| 2026-10 | Jabodetabek | 260.604.000 | 0 | 0 | 260.604.000 | 0 |
| 2026-10 | Jawa Barat | 143.118.000 | 2.910.000 | 0 | 146.028.000 | 0 |
| 2026-10 | Jawa Tengah | 107.532.000 | 0 | 0 | 107.532.000 | 0 |
| 2026-10 | Jawa Timur | 141.066.000 | 594.000 | 0 | 141.660.000 | 0 |
| 2026-10 | Kalimantan | 71.514.000 | 0 | 0 | 71.514.000 | 0 |
| 2026-10 | Sumatera | 165.954.000 | 0 | -312.000 | 165.642.000 | 0 |
| Total |  | 1.758.432.000 | 0 | -2.112.000 | 1.756.320.000 | 0 |

## Diskon (Rp)

| bulan | region (label mentah) | mentah | DQ-03 | DQ-06 | bersih | selisih |
|---|---|---|---|---|---|---|
| 2026-09 | JABODETABEK | 33.600 | -33.600 | 0 | 0 | 0 |
| 2026-09 | JAWA BARAT | 38.400 | -38.400 | 0 | 0 | 0 |
| 2026-09 | Jabar | 0 | 0 | 0 | 0 | 0 |
| 2026-09 | Jabodetabek | 4.272.300 | 33.600 | 0 | 4.305.900 | 0 |
| 2026-09 | Jawa Barat | 3.058.800 | 38.400 | -31.700 | 3.065.500 | 0 |
| 2026-09 | Jawa Tengah | 2.290.100 | 0 | 0 | 2.290.100 | 0 |
| 2026-09 | Jawa Timur | 1.408.600 | 0 | 0 | 1.408.600 | 0 |
| 2026-09 | Kalimantan | 1.515.800 | 0 | 0 | 1.515.800 | 0 |
| 2026-09 | Sumatera | 3.236.700 | 0 | 0 | 3.236.700 | 0 |
| 2026-10 | JAWA BARAT | 0 | 0 | 0 | 0 | 0 |
| 2026-10 | JAWA TIMUR | 0 | 0 | 0 | 0 | 0 |
| 2026-10 | Jabar | 0 | 0 | 0 | 0 | 0 |
| 2026-10 | Jabodetabek | 3.782.300 | 0 | 0 | 3.782.300 | 0 |
| 2026-10 | Jawa Barat | 2.145.200 | 0 | 0 | 2.145.200 | 0 |
| 2026-10 | Jawa Tengah | 1.598.400 | 0 | 0 | 1.598.400 | 0 |
| 2026-10 | Jawa Timur | 2.582.900 | 0 | 0 | 2.582.900 | 0 |
| 2026-10 | Kalimantan | 1.153.800 | 0 | 0 | 1.153.800 | 0 |
| 2026-10 | Sumatera | 3.278.200 | 0 | -9.400 | 3.268.800 | 0 |
| Total |  | 30.395.100 | 0 | -41.100 | 30.354.000 | 0 |

## Net (Rp)

| bulan | region (label mentah) | mentah | DQ-03 | DQ-06 | bersih | selisih |
|---|---|---|---|---|---|---|
| 2026-09 | JABODETABEK | 638.400 | -638.400 | 0 | 0 | 0 |
| 2026-09 | JAWA BARAT | 729.600 | -729.600 | 0 | 0 | 0 |
| 2026-09 | Jabar | 2.160.000 | -2.160.000 | 0 | 0 | 0 |
| 2026-09 | Jabodetabek | 238.367.700 | 638.400 | 0 | 239.006.100 | 0 |
| 2026-09 | Jawa Barat | 165.943.200 | 2.889.600 | -1.768.300 | 167.064.500 | 0 |
| 2026-09 | Jawa Tengah | 116.947.900 | 0 | 0 | 116.947.900 | 0 |
| 2026-09 | Jawa Timur | 72.301.400 | 0 | 0 | 72.301.400 | 0 |
| 2026-09 | Kalimantan | 73.880.200 | 0 | 0 | 73.880.200 | 0 |
| 2026-09 | Sumatera | 178.317.300 | 0 | 0 | 178.317.300 | 0 |
| 2026-10 | JAWA BARAT | 2.316.000 | -2.316.000 | 0 | 0 | 0 |
| 2026-10 | JAWA TIMUR | 594.000 | -594.000 | 0 | 0 | 0 |
| 2026-10 | Jabar | 594.000 | -594.000 | 0 | 0 | 0 |
| 2026-10 | Jabodetabek | 256.821.700 | 0 | 0 | 256.821.700 | 0 |
| 2026-10 | Jawa Barat | 140.972.800 | 2.910.000 | 0 | 143.882.800 | 0 |
| 2026-10 | Jawa Tengah | 105.933.600 | 0 | 0 | 105.933.600 | 0 |
| 2026-10 | Jawa Timur | 138.483.100 | 594.000 | 0 | 139.077.100 | 0 |
| 2026-10 | Kalimantan | 70.360.200 | 0 | 0 | 70.360.200 | 0 |
| 2026-10 | Sumatera | 162.675.800 | 0 | -302.600 | 162.373.200 | 0 |
| Total |  | 1.728.036.900 | 0 | -2.070.900 | 1.725.966.000 | 0 |

## Penjualan dan retur di data bersih

| bulan | baris penjualan | gross penjualan | diskon | net penjualan | baris retur | net retur | net setelah retur |
|---|---|---|---|---|---|---|---|
| 2026-09 | 927 | Rp863.340.000 | Rp15.822.600 | Rp847.517.400 | 0 | Rp0 | Rp847.517.400 |
| 2026-10 | 960 | Rp893.508.000 | Rp14.531.400 | Rp878.976.600 | 1 | -Rp528.000 | Rp878.448.600 |
| Total | 1887 | Rp1.756.848.000 | Rp30.354.000 | Rp1.726.494.000 | 1 | -Rp528.000 | Rp1.725.966.000 |

Bila invoice di luar urutan (DQ-09) dikecualikan, net penjualan berkurang Rp4.908.000 (25 baris). Angka di atas masih memasukkannya.


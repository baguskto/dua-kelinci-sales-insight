# Data penjualan Dua Kelinci

Pipeline untuk membaca, memeriksa dan membersihkan data penjualan Dua Kelinci September-Oktober 2026 (1.891 baris invoice), lalu menyusunnya menjadi tabel fakta dan dimensi yang siap dipakai dashboard.

## Cara menjalankan

Butuh [uv](https://docs.astral.sh/uv/) dan `make`.

```
make setup   # pasang Python 3.12 dan dependensi
make data    # bangun data/processed, docs dan kontrak dari data/raw/sales_raw.csv
make test    # jalankan semua test
```

Tanpa `make`: `uv sync`, `uv run python -m dk_sales.pipeline`, `uv run pytest`.

## Isi repo

- `data/raw/sales_raw.csv`: data mentah, tidak pernah diubah. Hash-nya dicek oleh test.
- `src/dk_sales/`: kode pipeline (baca file, aturan kualitas data, cleaning, model, rekonsiliasi, dokumen).
- `data/processed/`: hasil `make data` (Parquet dan CSV), tidak disimpan di git.
- `docs/01-profiling.md`: profil data mentah.
- `docs/01-dq-audit.md`: 27 aturan kualitas data, jumlah temuan, contoh baris dan keputusan.
- `docs/02-data-dictionary.md`: kamus data tabel fakta dan dimensi.
- `docs/02-data-contract.md`: kontrak input dan output.
- `docs/02-reconciliation.md`: rekonsiliasi total mentah ke bersih per bulan dan region.
- `docs/03-phase1-report.md`: laporan fase 1.

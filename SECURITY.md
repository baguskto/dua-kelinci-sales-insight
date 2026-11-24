# Kebijakan keamanan

## Versi yang didukung

| Versi | Didukung |
|---|---|
| `main` (versi terbaru) | ya |
| versi lain | tidak |

## Melaporkan celah keamanan

Jangan membuka issue publik untuk celah keamanan. Kirim email ke baguskto@gmail.com dengan judul "SECURITY: dua-kelinci-sales-insight", berisi langkah untuk mereproduksi, dampak yang Anda lihat, dan versi atau commit yang dipakai. Jangan sertakan data penjualan asli atau kredensial.

Target respons: konfirmasi dalam 2 hari kerja, penilaian awal dalam 5 hari kerja, dan perbaikan untuk temuan tinggi atau kritis dalam 14 hari. Pelapor akan diberi kabar sampai perbaikan dirilis.

## Ruang lingkup

Aplikasi web (`src/dk_sales/web`), chat dan guardrail (`src/dk_sales/chat`, `src/dk_sales/guard.py`), pipeline data, Dockerfile dan konfigurasi `compose.yaml`/`ops/`. Layanan pihak ketiga yang dijalankan sendiri (Grafana, Loki, Prometheus, Langfuse, Caddy) mengikuti kebijakan proyek masing-masing; laporkan ke sana bila celahnya ada di produk itu.

Rincian kontrol: [docs/security/README.md](docs/security/README.md).

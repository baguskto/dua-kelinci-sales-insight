# Operasional

Jalur reviewer tetap dua perintah (`pip install -r requirements.txt`, `python app.py`) tanpa Docker dan tanpa kunci. Semua bagian produksi di bawah ini opsional dan aktif lewat konfigurasi.

## Isi stack ops

`docker compose --profile ops up -d` menjalankan, semuanya di mesin sendiri (tidak ada yang dikirim ke layanan cloud):

| Layanan | Image (dipin) | Port di host | Batas memori | Fungsi |
|---|---|---|---|---|
| app-prod | build lokal (Debian 13, Python 3.12.13) | lewat Caddy | 512 MB | Aplikasi, `APP_ENV=production`, akun lokal argon2 |
| caddy | caddy:2.9.1-alpine | 127.0.0.1:8443 | 64 MB | TLS dan reverse proxy |
| prometheus | prom/prometheus:v3.2.1 | 127.0.0.1:9090 | 256 MB | Metrik, retensi 15 hari |
| loki | grafana/loki:3.4.2 | internal | 256 MB | Log, retensi 7 hari |
| alloy | grafana/alloy:v1.7.1 | internal | 128 MB | Kirim log container app dan caddy ke Loki |
| grafana | grafana/grafana:11.5.2 | 127.0.0.1:3000 | 256 MB | 4 dashboard dan 6 alert sebagai kode |
| langfuse-web, langfuse-worker | langfuse/langfuse(-worker):3.227.1 | 127.0.0.1:3001 | 1280 + 512 MB | Tracing chat dan ringkasan, dataset evaluasi |
| langfuse-postgres | postgres:16.8-alpine | internal | 256 MB | Metadata Langfuse |
| langfuse-clickhouse | clickhouse/clickhouse-server:24.12-alpine | internal | 1536 MB | Data trace Langfuse |
| langfuse-redis | redis:7.4.2-alpine | internal | 128 MB | Antrian Langfuse |
| langfuse-minio | cgr.dev/chainguard/minio (digest) | internal | 256 MB | Penyimpanan event Langfuse |

Pemakaian memori terukur saat dijalankan di Mac ini: sekitar 2,3 GB total (Langfuse web 1,0 GB, ClickHouse 460 MB, worker 280 MB, aplikasi 120 MB). Telemetri bawaan Grafana, Loki dan Langfuse dimatikan.

## Mulai cepat

```
make ops-secrets        # .env dan ops/secrets/* acak, chmod 600/700; password awal di ops/secrets/initial-passwords.txt
make ops-up             # build image aplikasi dan jalankan profile ops
make ops-ps             # semua layanan harus "healthy"
make ops-down
```

- Aplikasi: https://localhost:8443 (sertifikat CA internal Caddy). Akun: `admin`, `hos`, `jabar`, `sukro`.
- Grafana: http://localhost:3000 (admin). Folder "Dua Kelinci": Kesehatan layanan, Pemakaian aplikasi, Chat dan guardrail, Kualitas data.
- Langfuse: http://localhost:3001 (admin@duakelinci.local). Proyek "Sales Insight": trace `chat_turn` dan `telegram_summary`, dataset `dk-chat-golden` dan `dk-chat-redteam`.
- Telegram untuk alert Grafana: isi `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` di `.env`, lalu `make ops-telegram-alerts` dan restart grafana. Tanpa itu alert hanya terlihat di Grafana.
- Data uji: `uv run python scripts/ops_traffic.py` (halaman, unggahan, set chat), `uv run python scripts/langfuse_eval.py` (dataset dan experiment run).

## Konfigurasi aplikasi

Semua variabel ada di [.env.example](../../.env.example). Mode production menolak start bila salah satu ini tidak aman: `AUTH_MODE` bukan `local`/`oidc`, `SECRET_KEY` kurang dari 32 karakter acak, `ALLOWED_HOSTS` kosong atau `*`, `FORCE_HTTPS` tidak `true`, `TRUSTED_PROXIES` kosong, `METRICS_TOKEN` kurang dari 24 karakter, file akun lokal tidak ada, atau isian Entra ID tidak lengkap. Mode development hanya mendengar di 127.0.0.1.

### Microsoft Entra ID

1. Daftarkan aplikasi di Entra ID, redirect URI `https://<host>/auth/entra/callback`, buat client secret.
2. Tambahkan app role: `HeadOfSales`, `Admin`, `HeadOfRegion.JawaBarat` (satu per region, nama tanpa spasi), `BrandManager.Sukro` (satu per brand). Tetapkan role ke pengguna atau grup.
3. Isi `AUTH_MODE=oidc`, `OIDC_TENANT_ID`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`. Pasang extra `oidc` (`pyjwt[crypto]`, sudah ada di image produksi).
4. Pengguna tanpa role ditolak dengan pesan "belum diberi peran".

Runbook lengkap: [runbook.md](runbook.md).

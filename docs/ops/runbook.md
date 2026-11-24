# Runbook

## Deploy ke VM Linux (Docker compose)

Prasyarat: Ubuntu 24.04 atau Debian 12/13, Docker Engine dengan compose v2.24+, 4 GB RAM untuk stack lengkap (1 GB cukup untuk aplikasi saja), DNS internal untuk nama host, port 443 terbuka dari jaringan kantor saja.

```
sudo mkdir -p /opt/dua-kelinci && sudo chown $USER /opt/dua-kelinci
git clone https://github.com/baguskto/dua-kelinci-sales-insight /opt/dua-kelinci
cd /opt/dua-kelinci
make ops-secrets
```

Lalu sesuaikan untuk host sungguhan:

1. `ops/caddy/Caddyfile`: ganti `https://localhost:8443` dengan `https://sales.<domain-internal>` dan pilih sertifikat (ACME internal, file sertifikat perusahaan, atau `tls internal` dengan CA yang dibagikan lewat GPO). Ubah port di `compose.yaml` ke `443:8443`.
2. `.env`: `ALLOWED_HOSTS=sales.<domain-internal>,app-prod,127.0.0.1`. Untuk login Microsoft, isi bagian Entra ID (lihat README ops) dan `AUTH_MODE=oidc`.
3. Ganti data default: letakkan file export di volume `app-prod-data` lewat unggahan admin, atau set `DATA_FILE`.
4. `make ops-up`, lalu `make ops-ps` sampai semua "healthy".
5. Pasang unit systemd agar hidup setelah reboot: `sudo cp ops/systemd/dua-kelinci-compose.service /etc/systemd/system/ && sudo systemctl enable --now dua-kelinci-compose`.

Alternatif tanpa Docker: `ops/systemd/dua-kelinci-app.service` menjalankan aplikasi dari virtualenv sebagai pengguna `dkapp` dengan sandbox systemd (ProtectSystem=strict, NoNewPrivileges, MemoryMax). Reverse proxy dan TLS memakai Caddy atau nginx yang sudah ada.

## Upgrade

```
cd /opt/dua-kelinci
git fetch && git log --oneline HEAD..origin/main        # baca perubahan
PREV=$(git rev-parse --short HEAD)
docker tag dua-kelinci-sales:local dua-kelinci-sales:$PREV   # simpan image lama untuk rollback
git pull --ff-only
APP_IMAGE_TAG=$(git rev-parse --short HEAD) docker compose --profile ops up -d --build app-prod
docker compose --profile ops ps app-prod                  # tunggu "healthy"
curl -sk https://localhost:8443/health
```

Image layanan lain dipin di `compose.yaml`; menaikkan versinya dilakukan lewat PR (Dependabot) dan diuji dulu di staging.

## Rollback

```
APP_IMAGE_TAG=<sha-sebelumnya> docker compose --profile ops up -d --no-build app-prod
```

Data tidak berubah karena unggahan disimpan per sha256 di volume dan file default ikut image. Bila rollback melewati perubahan skema data, jalankan `POST /dataset/reset` (tombol "Kembali ke sales.csv" di panel Kualitas data) lalu unggah ulang file terakhir.

## Backup dan restore

| Yang dibackup | Lokasi | Cara |
|---|---|---|
| Unggahan dan audit log aplikasi | volume `dua-kelinci_app-prod-data` | `docker run --rm -v dua-kelinci_app-prod-data:/d -v $PWD:/b alpine tar czf /b/app-data-$(date +%F).tgz -C /d .` |
| Postgres Langfuse | service `langfuse-postgres` | `docker compose exec -T langfuse-postgres pg_dump -U langfuse -Fc langfuse > langfuse-$(date +%F).dump` |
| Trace Langfuse (ClickHouse) | volume `dua-kelinci_langfuse-clickhouse` | Hentikan service, tar volume seperti di atas. Trace bisa juga dianggap sekali pakai dan tidak dibackup. |
| Dashboard dan alert | git (`ops/grafana`) | Sudah di repo |
| Secret | `.env`, `ops/secrets/` | Simpan di password manager atau vault, bukan di backup biasa |

Restore aplikasi: `docker run --rm -v dua-kelinci_app-prod-data:/d -v $PWD:/b alpine sh -c "cd /d && tar xzf /b/app-data-<tanggal>.tgz"`, lalu restart `app-prod`.

Restore Langfuse Postgres: `docker compose exec -T langfuse-postgres pg_restore -U langfuse -d langfuse --clean < langfuse-<tanggal>.dump`, lalu restart `langfuse-web` dan `langfuse-worker`.

Jadwal yang disarankan: harian untuk data aplikasi dan Postgres Langfuse (cron + rotasi 14 hari), uji restore sebulan sekali di VM staging.

## Retensi log

- Log container Docker: json-file, 10 MB x 3 file per container (di `compose.yaml`).
- Loki: 7 hari (`ops/loki/loki.yaml`, `retention_period`).
- Prometheus: 15 hari (`--storage.tsdb.retention.time`).
- Audit log aplikasi (`/data/audit.jsonl`): disimpan sampai dirotasi. Rotasi bulanan dengan logrotate di host atau salin ke arsip sebelum dihapus; jangan dihapus lebih cepat dari kebijakan audit perusahaan.
- Langfuse: atur retensi di pengaturan proyek bila trace tidak perlu disimpan lama.

## Rotasi secret

Urutan aman (tanpa downtime panjang):

1. `cp .env .env.bak-$(date +%F)` dan salin `ops/secrets/` ke tempat aman.
2. `./scripts/gen-secrets.sh --force` membuat semua secret baru.
3. Secret yang tersimpan di database harus diubah di dalam layanannya juga:
   - Password Postgres Langfuse: `docker compose exec langfuse-postgres psql -U langfuse -c "ALTER USER langfuse PASSWORD '<baru>'"` sebelum restart.
   - Password ClickHouse dan MinIO dibaca saat start; restart service-nya.
   - `LANGFUSE_ENCRYPTION_KEY` dan `LANGFUSE_SALT` sebaiknya tidak dirotasi tanpa migrasi; kunci API proyek dirotasi lewat UI Langfuse lalu disalin ke `.env`.
   - Password admin Grafana hanya dibaca saat inisialisasi pertama: `docker compose exec grafana sh -c 'grafana cli --homepath /usr/share/grafana admin reset-admin-password "$(cat /run/secrets/grafana_admin_password)"'`.
4. `make ops-up` (container dengan konfigurasi berubah dibuat ulang). `SECRET_KEY` baru membuat semua sesi lama tidak berlaku; pengguna perlu login ulang.
5. Simpan password baru dari `ops/secrets/initial-passwords.txt` di password manager lalu hapus file itu.

Bila secret bocor: rotasi segera, cek `audit.jsonl` dan log Loki untuk login atau unggahan yang tidak dikenal, dan cabut kunci Anthropic atau token bot Telegram dari konsol masing-masing.

## Gangguan umum

| Gejala | Penyebab yang sering | Tindakan |
|---|---|---|
| `app-prod` tidak start, log "Konfigurasi production tidak aman" | Variabel wajib kosong | Baca daftar di log, lengkapi `.env` |
| Healthcheck 400 | Host tidak ada di `ALLOWED_HOSTS` | Tambahkan nama host |
| Langfuse web restart terus | Heap Node kurang | Naikkan `NODE_OPTIONS` dan `mem_limit` |
| Trace tidak muncul | Kunci Langfuse salah atau Langfuse mati | Aplikasi tetap jalan; cek log `opentelemetry` dan `make ops-ps` |
| Alert "Unggahan gagal berulang" | Format export berubah | Lihat audit log alasan penolakan, sesuaikan pemetaan kolom |

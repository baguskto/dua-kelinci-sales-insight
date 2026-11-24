# 04 Laporan fase 2: aplikasi, chat, lapisan produksi

Tanggal: 25 November 2026. Repo: https://github.com/baguskto/dua-kelinci-sales-insight (branch `main`).

## Yang dibangun

Aplikasi web kecil untuk sales manager yang menjawab tiga pertanyaan tes di satu layar, ditambah cara memeriksa datanya:

1. **Penjualan per region dan brand.** KPI (net setelah retur dengan sparkline mingguan dan perubahan Okt vs Sep, karton, outlet aktif/order, rata-rata invoice, diskon), dumbbell region September ke Oktober, bar brand, heatmap region x brand. Pilihan periode Sep / Okt / Sep-Okt, filter dengan klik bar atau sel, "Lihat tabel" untuk setiap grafik, ekspor CSV aman formula.
2. **5 outlet terlemah**, dibanding median outlet bertipe sama, dengan bullet bar (nilai vs median), alasan satu baris, saran tindakan, dan catatan "Cek data" untuk outlet dari blok invoice di luar urutan dan kemungkinan master ganda.
3. **Ringkasan Telegram** satu paragraf (759 karakter untuk Sep-Okt), dibangun dari angka yang sudah dihitung, tombol Salin, Cetak, dan Kirim (uji kirim bila token belum diatur).
4. **Tanya data**: chat di laci samping, offline dengan parser intent Bahasa Indonesia, mode Claude opsional lewat tool calling, dengan guardrail angka (lihat `docs/08-guardrails.md`).
5. **Kualitas data**: laci berisi 27 aturan, duplikat yang dikarantina, retur, salesman yang diisi, kemungkinan master ganda, rekonsiliasi mentah ke bersih, dan unggahan file lain (admin) dengan kontrak yang sama.
6. **Lapisan produksi** (opsional): mode production yang menolak konfigurasi tidak aman, login Entra ID atau akun lokal argon2, RBAC empat peran, audit log, Docker non-root read-only, compose profile `ops` dengan Caddy, Prometheus, Grafana, Loki, Alloy dan Langfuse v3 self-hosted, CI dan scan rantai pasok.

Konsep UI ditulis dulu di `docs/05-ui-concept.md` lalu dibangun mengikutinya.

## Screenshot

| | |
|---|---|
| Dashboard desktop | `docs/img/dashboard-desktop.png`, halaman penuh `docs/img/dashboard-desktop-full.png` |
| Ponsel 390 px | `docs/img/dashboard-mobile.png`, `docs/img/dashboard-mobile-full.png` |
| Tanya data | `docs/img/chat-drawer.png` |
| Kualitas data | `docs/img/data-quality-drawer.png` |
| Unggahan rusak | `docs/img/upload-error.png` |
| Filter Jawa Barat | `docs/img/filter-jawa-barat.png` |
| Production, login Head of Region Jawa Barat lewat Caddy | `docs/img/prod-head-of-region-jabar.png` |
| Grafana | `docs/img/grafana-service-health.png`, `grafana-sales-usage.png`, `grafana-chat-guardrails.png`, `grafana-data-quality.png`, `grafana-alert-rules.png` |
| Langfuse | `docs/img/langfuse-traces.png`, `langfuse-trace-detail.png`, `langfuse-datasets.png` |

## Definisi outlet terlemah

Net setelah retur per outlet pada periode yang dipilih, dibagi median outlet bertipe sama (Grosir, Minimarket, Toko Kelontong, Warung). Indeks terendah paling lemah, hanya outlet di bawah median yang tampil. Jumlah order, order terakhir, tren bulan dan SKU yang belum dibeli dipakai untuk alasan dan saran, tidak untuk urutan. Rincian dan alternatif yang tidak dipakai: `docs/06-metric-definitions.md`.

Hasil Sep-Okt: OUT1003, OUT1026, OUT1045, OUT1042, OUT1035, semuanya di bawah 10% median tipenya. Ini lima outlet yang hanya muncul di blok INV500799-INV500823. Sesuai keputusan Bagus mereka tetap dihitung dan tampil dengan catatan "Nomor invoice di luar urutan: cek input, kemungkinan outlet baru atau order susulan". OUT1001 dan OUT1003 tetap dua outlet dengan catatan kemungkinan data master ganda. Retur RTR900001 tampil di panel Kualitas data dan di detail OUT1049 dengan catatan melebihi pembelian.

## Hasil test

| Jenis | Jumlah | Hasil |
|---|---:|---|
| Semua test (`uv run pytest`) | 151 | 151 lulus, sekitar 200 detik |
| Termasuk e2e Playwright (Chromium) | 5 | lulus: tiga jawaban tampil, toggle periode dan filter, chat dengan sumber, unggahan rusak menampilkan galat, urutan ponsel |
| Cakupan kode `src/dk_sales` | | 90% (cabang ikut dihitung) |
| Lint dan tipe | | ruff bersih, ruff format bersih, mypy bersih (29 file) |

Evaluasi chat:

| Set | Mode offline | Mode LLM tiruan (model yang memakai tool lalu merangkum) | Experiment Langfuse |
|---|---|---|---|
| Golden (35 pertanyaan dengan angka) | 35/35 (100%) | lulus untuk 32 item; 3 item (G17, G18, G35: pertanyaan lanjutan dan klarifikasi nama ganda) hanya diwajibkan lulus di offline | 35/35 |
| Red-team (24 kasus) | 24/24 (100%) | 24/24 | 24/24 |

Test model tiruan juga membuktikan: angka karangan diganti template (`numbers_unmatched`), jawaban tanpa tool ditolak, error API jatuh ke offline, batas 4 tool per giliran, anggaran harian habis memakai offline, region di luar scope ditolak di tool, nama outlet berisi instruksi hanya masuk sebagai `tool_result`. Evaluasi ke API Claude sungguhan belum dijalankan karena tidak ada `ANTHROPIC_API_KEY`; skripnya siap: `scripts/live_eval.py --live`.

## Waktu jalan di mesin bersih

Diukur di Mac ini dengan clone baru dan virtualenv baru (Python 3.12):

- `pip install -r requirements.txt` tanpa cache: 20 detik.
- `python app.py` sampai `/health` siap: 11,7 detik pada start pertama (Python mengompilasi library sekali), 1,9 detik pada start berikutnya. Memuat dan membersihkan data 1,5 detik.
- Docker: `docker compose up` membangun image sekali (beberapa menit, tergantung koneksi), lalu container sehat setelah start pertama data selesai dimuat. Image 891 MB (pandas dan pyarrow paling besar).

## Lapisan produksi yang sudah diverifikasi di Mac ini

- Stack `ops` dinyalakan dalam dua tahap sambil memantau memori (batas berhenti: memori bebas di bawah 15%; titik terendah 16,2%). Semua healthcheck sehat. Total pemakaian sekitar 2,3 GB. Stack dimatikan lagi setelah screenshot.
- Lalu lintas uji lewat https://localhost:8443: login empat peran dan satu login gagal, 52 halaman, 6 unggahan (3 diterima, 3 ditolak), 2 uji kirim Telegram, 59 pertanyaan chat.
- Prometheus men-scrape `/metrics` dengan token; Grafana menampilkan 4 dashboard dan 6 alert (semua normal; alert unggahan gagal butuh lebih dari 3 penolakan dalam 30 menit).
- Langfuse menerima trace `chat_turn` (intent, tool, skor guardrail, mode, peran pengguna, pertanyaan disamarkan) dan `telegram_summary`; dataset golden dan red-team beserta satu experiment run tersimpan.
- Masalah yang ditemukan dan diperbaiki selama verifikasi: unggahan mode JSON mengembalikan 500 di production (sudah diperbaiki dan dites), healthcheck ditolak `ALLOWED_HOSTS`, Langfuse web kehabisan heap Node, SDK Langfuse ikut merekam semua span HTTP FastAPI (sekarang hanya span aplikasi), base image lama dengan 51 CVE, karakter bidi literal di regex.

## Keamanan

Ringkasan di `docs/security/README.md`: STRIDE, checklist ASVS L1, pip-audit tanpa celah, bandit 0 temuan, gitleaks 0 temuan aktif, Trivy 0 HIGH/CRITICAL yang punya perbaikan, SBOM 66 komponen. CI GitHub Actions sudah ditulis tetapi diset manual (`workflow_dispatch`) agar tidak berjalan di GitHub sebelum disetujui.

## Batasan yang diketahui

- Rate limit, kunci login, memori chat dan anggaran token disimpan di memori satu proses. Untuk lebih dari satu replika perlu Redis.
- Login Entra ID dites dengan token yang ditandatangani kunci lokal dan endpoint tiruan, belum dengan tenant Dua Kelinci.
- Kirim Telegram dites dengan fungsi kirim tiruan dan mode uji; belum dengan token bot sungguhan. Perapian bahasa ringkasan oleh Claude (`LLM_POLISH_SUMMARY`) dites dengan model tiruan: teks dengan angka benar dipakai, teks dengan angka karangan diganti template.
- Parser intent offline menangani pola pertanyaan umum (35 di golden set). Pertanyaan yang lebih bebas butuh mode Claude.
- Jalur pip butuh Python 3.11 atau lebih baru (pandas 3). Jalur `uv run app.py` mengunduh Python yang tepat sendiri.
- Langfuse server dipin di 3.227.1 sesuai permintaan v3; UI Langfuse menyebut v3 tidak lagi mendapat fitur baru.
- Alloy membaca socket Docker (mode baca) untuk log; di VM produksi sebaiknya membaca file log.
- Stack ops lengkap butuh sekitar 2,5 GB RAM; aplikasinya sendiri sekitar 120 MB.

## Yang perlu diputuskan Bagus

1. Menyalakan CI di GitHub (ganti trigger ke push/pull_request) dan Dependabot PR.
2. Langfuse tetap v3 atau naik ke v4 (perlu cek kompatibilitas SDK).
3. Apakah menambahkan kunci Anthropic untuk menjalankan `scripts/live_eval.py --live` sekali dan mencatat hasilnya sebelum dikirim ke Dua Kelinci.
4. Isi README untuk pengirim: cukup jalur dua perintah, atau menyebut stack ops di bagian atas.
5. Blok invoice di luar urutan: catatan "Cek data" sekarang ditampilkan di setiap kartu outlet terlemah. Bila terlalu ramai untuk manajer, bisa diringkas menjadi satu catatan di judul bagian.

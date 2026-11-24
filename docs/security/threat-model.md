# Model ancaman (STRIDE)

## Alur data dan batas kepercayaan

```
 Pengguna (browser)          Admin                  Internet (opsional, hanya bila diaktifkan)
      |  HTTPS                 | unggah CSV/xlsx            ^              ^
      v                        v                            |              |
 [Caddy TLS] --(B1)--> [App FastAPI] --(B3)--> Anthropic API    Telegram Bot API
                          |      |  \
                     (B2) |      |   \--(B4)--> Langfuse (self-hosted, jaringan internal)
                          v      v
              DATA_DIR (unggahan, audit)   /metrics --> Prometheus --> Grafana
                                           stdout log --> Alloy --> Loki --> Grafana
```

- B1: proxy ke aplikasi, jaringan Docker internal. Aplikasi hanya mempercayai `X-Forwarded-For` dari IP Caddy (`TRUSTED_PROXIES`).
- B2: file unggahan adalah input tidak tepercaya.
- B3: keluar ke Anthropic hanya bila `ANTHROPIC_API_KEY` diisi; yang dikirim hanya pertanyaan dan hasil agregat tool, bukan baris mentah.
- B4: Langfuse self-hosted; teks pertanyaan disamarkan kecuali `LOG_QUESTION_TEXT=true`.

## STRIDE

| Kategori | Ancaman | Kontrol | Test |
|---|---|---|---|
| Spoofing | Masuk sebagai orang lain | Entra ID OIDC (PKCE, cek state, nonce, issuer, audience, tanda tangan JWKS) atau akun lokal argon2id; kunci akun 15 menit setelah 5 gagal; sesi baru saat login | `test_entra_oidc_flow_validates_token`, `test_login_failure_and_lockout` |
| Spoofing | IP palsu lewat header | `X-Forwarded-For` hanya dibaca dari proxy tepercaya | `client_ip` di `app.py` |
| Tampering | Mengubah data lewat chat | Tool baca-saja, tanpa tool tulis; pengiriman hanya lewat tombol | `test_injection_in_outlet_name_is_passed_as_tool_data_only` |
| Tampering | CSRF | Token per sesi wajib di setiap POST (header atau form), cookie SameSite=Lax | `test_csrf_required_on_every_post` |
| Tampering | File berbahaya (macro, zip bomb, XXE, biner) | Daftar ekstensi, sniffing isi, tolak `vbaProject.bin`, batas rasio dan ukuran zip, openpyxl dengan defusedxml, batas baris | `test_upload_xlsx_macro_and_zip_bomb_rejected`, `test_upload_rejections_keep_active_dataset` |
| Tampering | Formula injection di ekspor CSV | Sel yang diawali `= + - @` diberi tanda kutip | `test_exports_escape_formulas` |
| Repudiation | Menyangkal unggah atau kirim | Audit log terpisah (`DATA_DIR/audit.jsonl`): login, gagal login, unggah, reset data, kirim Telegram, ekspor, dengan request id | `test_telegram_dry_run_and_send`, `test_login_failure_and_lockout` |
| Information disclosure | Head of Region melihat region lain | Scope diterapkan di lapisan data untuk halaman, API, ekspor, ringkasan dan chat | `test_head_of_region_cannot_see_other_regions`, `test_llm_cannot_escape_scope` |
| Information disclosure | XSS dari nama outlet | Autoescape Jinja, `textContent` di JS, CSP tanpa inline, karakter kontrol dibuang | `test_outlet_names_are_html_escaped`, `test_no_inline_script_or_style_in_templates`, e2e tanpa error CSP |
| Information disclosure | Stack trace, header server | Halaman galat generik, header `server` dihapus, docs OpenAPI dimatikan | `test_health_and_404`, `test_security_headers` |
| Information disclosure | Data pribadi di log dan trace | Log JSON tanpa teks pertanyaan, tanpa query string; trace Langfuse menyamarkan pertanyaan | `test_logs_have_no_question_text` |
| Information disclosure | Metrik terbuka | `/metrics` wajib token di production; dev hanya localhost | `test_metrics_protected` |
| Denial of service | Unggahan besar, request bertubi | Batas body, batas MB dan baris unggahan, rate limit per IP dan per pengguna chat, batas memori container | `test_request_body_limit`, `test_rate_limits`, `test_upload_size_and_row_limits` |
| Denial of service | Biaya LLM tak terbatas | Batas token output, batas tool per giliran, timeout, anggaran token harian, alert 80% | `test_daily_budget_exhausted_uses_offline`, `test_tool_call_limit_per_turn` |
| Elevation of privilege | Non-admin mengunggah atau mereset data | Cek peran di setiap rute admin | `test_upload_requires_csrf_and_admin` |
| Elevation of privilege | Lepas dari container | Non-root (uid 10001), root filesystem read-only, `cap_drop: ALL`, `no-new-privileges`, tanpa compiler di image | Smoke test di CI dan `docs/ops/runbook.md` |
| Elevation of privilege | Prompt injection membuat model bertindak | Pemeriksaan awal deterministik, isi file sebagai `tool_result`, tidak ada tool bersisi efek | `test_redteam_set_offline`, `docs/08-guardrails.md` |

## Risiko yang diterima

- Alloy membaca `/var/run/docker.sock` dalam mode baca untuk mengambil log container. Socket itu tetap memberi akses API Docker; di VM produksi, ganti dengan membaca file log JSON (`/var/lib/docker/containers`) atau jalankan Alloy di host dengan akses terbatas.
- Rate limit dan penguncian login disimpan di memori satu proses. Dengan lebih dari satu replika, pindahkan ke Redis atau aturan rate limit di Caddy.
- Akun lokal memakai satu password awal yang sama untuk akun demo; di produksi pakai Entra ID atau ganti password per akun.
- Retur dan nama outlet berasal dari file; kebenaran isinya di luar kendali aplikasi dan ditangani oleh aturan DQ.

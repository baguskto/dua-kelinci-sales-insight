# Keamanan

- [Model ancaman STRIDE](threat-model.md)
- [Checklist OWASP ASVS level 1](asvs-l1.md)
- [Guardrail chat dan pemetaan OWASP Top 10 untuk LLM](../08-guardrails.md)
- [Kebijakan pelaporan](../../SECURITY.md)

## Ringkasan kontrol

| Area | Kontrol |
|---|---|
| Autentikasi | Entra ID OIDC (PKCE, state, nonce, JWKS) atau akun lokal argon2id; kunci setelah 5 gagal; sesi idle 60 menit |
| Otorisasi | Head of Sales, Head of Region (region sendiri), Brand Manager (brand sendiri), Admin (unggah, reset); scope di lapisan data |
| Web | CSP tanpa inline, HSTS di belakang TLS, nosniff, frame-ancestors none, Referrer-Policy, Permissions-Policy, tanpa CORS, CSRF di setiap POST, rate limit, batas body, halaman galat tanpa stack trace |
| Unggahan | Daftar ekstensi, sniffing isi, batas MB dan baris, xlsx tanpa macro dan bukan zip bomb, defusedxml, nama file tidak dipakai sebagai path, ekspor aman formula |
| Konfigurasi | Mode production menolak start bila tidak aman; dev hanya 127.0.0.1; secret hanya lewat `.env` dan docker secrets yang dibuat skrip |
| Container | Non-root, root filesystem read-only, `cap_drop: ALL`, `no-new-privileges`, batas memori, tanpa compiler, dependensi dengan hash |
| Audit | `audit.jsonl` terpisah: login, gagal login, unggah, reset data, kirim Telegram, ekspor |
| Rantai pasok | Lock dengan hash, pip-audit, bandit, gitleaks, Trivy, SBOM CycloneDX, Dependabot, build ulang mingguan di CI |

## Hasil scan lokal (25 November 2026)

| Alat | Hasil | File |
|---|---|---|
| pip-audit 2.x, `requirements-prod.lock` | Tidak ada celah yang diketahui | [scans/pip-audit.txt](scans/pip-audit.txt) |
| bandit, `src/` (5.472 baris) | 0 temuan; 3 pengecualian beralasan (bind 0.0.0.0 di container, `random` untuk sampling trace) | [scans/bandit.txt](scans/bandit.txt) |
| gitleaks, seluruh riwayat git | 0 temuan aktif; 2 temuan lama di `.gitleaksignore` (string SECRET_KEY palsu di fixture test, sekarang dibuat saat test berjalan) | `.gitleaksignore` |
| Trivy 0.59.1, image aplikasi (Debian 13.8) | 0 HIGH/CRITICAL yang punya perbaikan | [scans/trivy-image-vuln.txt](scans/trivy-image-vuln.txt) |
| Trivy secret scan, image | 1 temuan positif palsu: contoh teks di docstring SDK Anthropic (`beta_managed_agents_session_thread_agent.py`) | [scans/trivy-image-secret.txt](scans/trivy-image-secret.txt) |
| SBOM CycloneDX 1.5 | 66 komponen produksi | [scans/sbom.cdx.json](scans/sbom.cdx.json) |

Temuan yang sudah diperbaiki selama scan: base image lama `python:3.12.9-slim-bookworm` (Debian 12.10) membawa 51 celah HIGH/CRITICAL yang sudah ada perbaikannya; diganti ke `python:3.12.13-slim-trixie` dengan `apt-get upgrade` saat build. Bandit menemukan karakter pembalik arah teks yang tertulis langsung di regex `security.py` (risiko trojan source); diganti dengan escape `\u`.

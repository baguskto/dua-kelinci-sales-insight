# Checklist OWASP ASVS 4.0.3 level 1

Status: **ya** = diterapkan dan dites, **sebagian** = diterapkan dengan batasan yang dicatat, **n/a** = tidak relevan untuk aplikasi ini, **belum** = belum dikerjakan.

| ASVS | Persyaratan (ringkas) | Status | Bukti |
|---|---|---|---|
| 2.1.1 | Password minimal 12 karakter | sebagian | Password awal acak 20 karakter dari `gen-secrets.sh`; belum ada UI ganti password (produksi memakai Entra ID) |
| 2.1.7 | Password dicek terhadap daftar bocor | n/a | Autentikasi utama Entra ID; akun lokal hanya fallback dengan password acak |
| 2.2.1 | Perlindungan brute force | ya | Kunci 15 menit setelah 5 gagal per pengguna+IP, metrik `login_failures_total`, `test_login_failure_and_lockout` |
| 2.4.1 | Password disimpan dengan hash adaptif | ya | argon2id (`argon2-cffi`), `auth.hash_password` |
| 2.5.x | Pemulihan kredensial | n/a | Dikelola Entra ID |
| 3.2.1 | Token sesi baru saat login | ya | `_start_session` membersihkan sesi lalu membuat CSRF baru |
| 3.2.3 | Token sesi tidak di URL | ya | Cookie `dk_session` saja |
| 3.3.1 | Logout mengakhiri sesi | ya | `POST /logout` dengan CSRF, `test_logout` |
| 3.3.2 | Batas waktu sesi | ya | `SESSION_TTL_MINUTES` (idle), `test_session_timeout` |
| 3.4.1 | Cookie Secure | ya | `https_only` bila `FORCE_HTTPS=true` (wajib di production), `test_login_required_and_session_cookie_flags` |
| 3.4.2 | Cookie HttpOnly | ya | Starlette SessionMiddleware, dites |
| 3.4.3 | Cookie SameSite | ya | `SameSite=Lax`, dites |
| 4.1.1 | Akses ditegakkan di server | ya | `Scope.apply` di lapisan data, cek peran di rute admin |
| 4.1.3 | Least privilege | ya | Empat peran; pengguna tanpa peran tidak melihat data apa pun |
| 4.2.1 | Perlindungan IDOR | ya | Outlet di luar scope = 404, `test_head_of_region_cannot_see_other_regions` |
| 4.2.2 | Perlindungan CSRF | ya | Token per sesi di setiap POST, `test_csrf_required_on_every_post` |
| 4.3.1 | Antarmuka admin dilindungi | ya | Unggah, reset, ekspor karantina hanya admin |
| 5.1.3 | Validasi input dengan allowlist | ya | Periode, dimensi, metrik, filter, argumen tool, `outlet_id` regex |
| 5.1.4 | Data terstruktur divalidasi | ya | Kontrak 15 kolom, 27 aturan DQ, pandera untuk output |
| 5.2.1 | Sanitasi HTML | ya | Autoescape Jinja, `textContent` di JS |
| 5.2.2 | Teks tidak terstruktur dibersihkan | ya | Karakter kontrol dan bidi dibuang (DQ-04, `strip_control`) |
| 5.3.1 | Output di-encode sesuai konteks | ya | HTML autoescape, JSON `tojson`, CSV formula-safe |
| 5.3.3 | Perlindungan XSS | ya | CSP `script-src 'self'` tanpa inline, `test_outlet_names_are_html_escaped` |
| 5.3.4 | Query aman (SQL injection) | n/a | Tidak ada database atau SQL; input mirip SQL ditolak di chat |
| 5.5.2 | Parsing XML aman (XXE) | ya | openpyxl memakai defusedxml (`openpyxl.xml.DEFUSEDXML = True`) |
| 7.1.1 | Tidak mencatat kredensial atau token | ya | Audit dan log tanpa password, token, cookie; `test_telegram_dry_run_and_send` cek token bot tidak ada di audit |
| 7.1.2 | Tidak mencatat data sensitif lain | ya | Teks pertanyaan tidak dicatat secara default, `test_logs_have_no_question_text` |
| 7.4.1 | Pesan galat generik | ya | Halaman galat tanpa stack trace, request id untuk dilacak |
| 8.2.1 | Header anti-cache untuk data sensitif | ya | `Cache-Control: no-store` kecuali `/static/` |
| 8.3.1 | Data sensitif tidak di URL | sebagian | Filter region/brand ada di query string; bukan data rahasia, tetapi tercatat di log proxy Caddy |
| 9.1.1 | TLS untuk semua koneksi klien | ya | Caddy TLS; production menolak start tanpa `FORCE_HTTPS` |
| 9.1.2 | Konfigurasi TLS kuat | ya | Default Caddy (TLS 1.2+), HSTS 1 tahun |
| 10.3.2 | Dependensi dipantau | ya | pip-audit, Trivy, Dependabot, SBOM CycloneDX |
| 11.1.x | Logika bisnis berurutan dan dibatasi | ya | Rate limit chat dan global, batas tool per giliran, anggaran token |
| 12.1.1 | Batas ukuran unggahan | ya | `MAX_UPLOAD_MB`, `MAX_UPLOAD_ROWS`, body limit, `test_upload_size_and_row_limits` |
| 12.2.1 | Tipe file divalidasi dari isi | ya | Sniffing PK/OLE/biner, `check_upload` |
| 12.3.1 | Nama file dari pengguna tidak dipakai sebagai path | ya | Disimpan sebagai `<sha256>.csv/.xlsx`, nama asli hanya ditampilkan |
| 12.4.1 | File unggahan disimpan di luar web root | ya | `DATA_DIR` terpisah, tidak disajikan |
| 12.5.1 | Server tidak menyajikan file sembarangan | ya | Hanya `/static/` dan ekspor terdaftar |
| 13.1.x | API dilindungi sama dengan UI | ya | API memakai sesi, scope dan CSRF yang sama |
| 14.2.1 | Komponen mutakhir dan bebas celah diketahui | ya | Lihat `scans/`; base image Debian 13 dengan update keamanan |
| 14.3.2 | Mode debug mati di production | ya | Tidak ada debug; docs OpenAPI dimatikan |
| 14.3.3 | Header tidak membocorkan versi | ya | Header `server` dihapus |
| 14.4.1-7 | Header keamanan HTTP | ya | CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, COOP, CORP; `test_security_headers` |
| 14.5.3 | CORS ketat | ya | Tidak ada header CORS (same-origin saja) |

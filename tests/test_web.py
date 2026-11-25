"""Integration tests for the web app with the real sales.csv and broken fixtures."""

from __future__ import annotations

import io
import json
import re
import secrets
import zipfile

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from dk_sales import config
from dk_sales.web import auth
from dk_sales.web.app import create_app
from dk_sales.web.security import csv_safe
from dk_sales.web.settings import ConfigError, Settings, from_env

RAW = (config.ROOT / "sales.csv").read_bytes()
# Generated per test run, so the repo holds no password-like constant.
PASSWORD = secrets.token_urlsafe(16)


def make(tmp_path, **kw) -> TestClient:
    s = Settings(app_env="test", data_dir=tmp_path / "var", **kw)
    return TestClient(create_app(s), base_url="https://testserver" if s.force_https else "http://testserver")


@pytest.fixture
def client(tmp_path):
    with make(tmp_path) as c:
        yield c


def csrf(c: TestClient, path: str = "/") -> str:
    return re.search(r'name="csrf-token" content="([^"]+)"', c.get(path).text).group(1)


def upload(c: TestClient, name: str, data: bytes):
    return c.post("/upload", files={"file": (name, data, "application/octet-stream")}, data={"csrf_token": csrf(c)})


# -- happy path ----------------------------------------------------------------


def test_dashboard_answers_three_questions(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    for h in ["Penjualan per region", "Penjualan per brand", "5 outlet terlemah", "Ringkasan untuk Telegram", "Tanya data", "Kualitas data"]:
        assert h in html
    assert "Rp1,73 miliar" in html
    for oid in ["OUT1003", "OUT1026", "OUT1045", "OUT1042", "OUT1035"]:
        assert oid in html
    assert "kemungkinan data master ganda" in html
    assert "RTR900001" in html


def test_period_toggle_and_invalid_period(client):
    assert "Rp878,4 juta" in client.get("/?period=2026-10").text
    assert client.get("/?period=<script>").status_code == 200


def test_api_endpoints(client):
    o = client.get("/api/overview").json()
    assert o["totals"]["net_sales_idr"] == 1_725_966_000
    assert [w["outlet_id"] for w in o["weakest"]][:1] == ["OUT1003"]
    assert client.get("/api/sales?dimension=brand").json()["rows"][0]["key"] == "Kacang Dua Kelinci"
    assert client.get("/api/sales?dimension=password").status_code == 400
    s = client.get("/api/summary").json()
    assert s["source"] == "template" and s["chars"] <= 1000


def test_health_and_404(client):
    assert client.get("/health").json()["dataset_loaded"] is True
    r = client.get("/does-not-exist")
    assert r.status_code == 404 and "Traceback" not in r.text


def test_chat_endpoint(client):
    tok = csrf(client)
    r = client.post("/api/chat", json={"question": "penjualan per region"}, headers={"X-CSRF-Token": tok})
    d = r.json()
    assert d["mode"] == "offline" and "Jabodetabek" in d["text"] and d["sources"][0]["tool"] == "sales_by"
    assert client.post("/api/chat", json={"question": 123}, headers={"X-CSRF-Token": tok}).status_code == 400
    assert client.post("/api/chat", content=b"not json", headers={"X-CSRF-Token": tok, "content-type": "application/json"}).status_code == 400


def test_telegram_dry_run_and_send(tmp_path):
    with make(tmp_path) as c:
        r = c.post("/api/telegram/send", json={}, headers={"X-CSRF-Token": csrf(c)}).json()
        assert r["dry_run"] is True and "Rp1,73 miliar" in r["text"]
    sent = []
    s = Settings(app_env="test", data_dir=tmp_path / "v2", telegram_bot_token="123:abc", telegram_chat_id="-100")
    with TestClient(create_app(s, telegram_post=lambda t, ch, text: sent.append(text) or True)) as c:
        r = c.post("/api/telegram/send", json={"period": "2026-10"}, headers={"X-CSRF-Token": csrf(c)}).json()
        assert r["sent"] is True and "Oktober 2026" in sent[0]
    audit = (tmp_path / "v2" / "audit.jsonl").read_text()
    assert '"telegram_send"' in audit and "123:abc" not in audit


def test_exports_escape_formulas(client):
    r = client.get("/export/weakest.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(pd.read_csv(io.StringIO(r.text.lstrip("﻿")))["outlet_id"])
    assert rows[0] == "OUT1003"
    assert client.get("/export/../../etc/passwd.csv").status_code == 404
    assert csv_safe("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert csv_safe("+62 812") == "'+62 812"
    assert csv_safe("-528000") == "-528000"
    assert csv_safe("@SUM(A1)") == "'@SUM(A1)"


# -- uploads ---------------------------------------------------------------------


def test_upload_semicolon_cp1252_is_accepted(client):
    text = RAW.decode().replace(",", ";").replace("Toko Mekar", "Toko Mékar")
    r = upload(client, "export.csv", text.encode("cp1252"))
    assert r.status_code == 200 and "diterima" in r.text
    assert "cp1252" in client.get("/").text


def test_upload_xlsx(client):
    df = pd.read_csv(io.BytesIO(RAW), dtype=str)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    r = upload(client, "sales.xlsx", buf.getvalue())
    assert r.status_code == 200 and "diterima" in r.text


@pytest.mark.parametrize(
    "name,data,message",
    [
        ("missing.csv", RAW.decode().replace("net_sales_idr", "nett").encode(), "Kolom wajib tidak ditemukan: net_sales_idr"),
        ("empty.csv", b"", "File kosong"),
        ("evil.exe", b"MZ", "Jenis file tidak didukung"),
        ("fake.csv", b"PK\x03\x04" + b"0" * 100, "bukan CSV"),
        ("binary.csv", b"\x00\x01\x02" * 100, "biner"),
        ("fake.xlsx", b"not a zip", "tidak valid"),
        ("old.xls", b"\xd0\xcf\x11\xe0", "tidak didukung"),
    ],
)
def test_upload_rejections_keep_active_dataset(client, name, data, message):
    r = upload(client, name, data)
    assert r.status_code == 400
    assert message in r.text
    assert "Data yang sedang tampil tidak berubah" in r.text
    assert client.get("/api/overview").json()["totals"]["net_sales_idr"] == 1_725_966_000


def test_upload_bad_dates_are_quarantined_not_fatal(client):
    lines = RAW.decode().splitlines()
    lines[1] = lines[1].replace("2026-09-01", "31/31/2026")
    r = upload(client, "baddate.csv", ("\n".join(lines) + "\n").encode())
    assert r.status_code == 200 and "4 dikarantina" in r.text  # 3 duplicates + the bad date


def test_upload_all_rows_bad_is_rejected(client):
    bad = "\n".join([RAW.decode().splitlines()[0]] + ["x,INV1,a,b,c,d,e,f,g,h,1,1,1,0,1"] * 3)
    r = upload(client, "allbad.csv", bad.encode())
    assert r.status_code == 400 and "tidak ada data bersih" in r.text


def test_upload_size_and_row_limits(tmp_path):
    with make(tmp_path, max_upload_mb=1, max_upload_rows=100) as c:
        r = upload(c, "big.csv", RAW)
        assert r.status_code == 400 and "melebihi batas 100 baris" in r.text
        r = upload(c, "huge.csv", RAW * 5)
        assert r.status_code in (400, 413)


def _xlsx_with(extra: dict[str, bytes], ratio_bomb: bool = False) -> bytes:
    df = pd.read_csv(io.BytesIO(RAW), dtype=str).head(5)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    src = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for i in src.infolist():
            z.writestr(i, src.read(i.filename))
        for k, v in extra.items():
            z.writestr(k, v)
    return out.getvalue()


def test_upload_xlsx_macro_and_zip_bomb_rejected(client):
    r = upload(client, "macro.xlsx", _xlsx_with({"xl/vbaProject.bin": b"x"}))
    assert r.status_code == 400 and "macro" in r.text
    r = upload(client, "bomb.xlsx", _xlsx_with({"xl/media/pad.bin": b"\0" * 30_000_000}))
    assert r.status_code == 400 and "zip bomb" in r.text


def test_upload_requires_csrf_and_admin(tmp_path, users_file):
    with make(tmp_path) as c:
        r = c.post("/upload", files={"file": ("a.csv", RAW, "text/csv")})
        assert r.status_code == 403
    with make(tmp_path, auth_mode="local", local_users_file=users_file) as c:
        login(c, "hos")
        r = upload(c, "a.csv", RAW)
        assert r.status_code == 403


def test_uploaded_dataset_survives_restart(tmp_path):
    text = RAW.decode().replace("Toko Mekar", "Toko Mekar Baru")
    with make(tmp_path) as c:
        upload(c, "baru.csv", text.encode())
    with make(tmp_path) as c:
        assert "baru.csv" in c.get("/").text
        tok = csrf(c)
        c.post("/dataset/reset", data={"csrf_token": tok})
        assert "sales.csv" in c.get("/").text


def test_missing_default_file_shows_empty_state(tmp_path):
    with make(tmp_path, data_file=tmp_path / "nope.csv") as c:
        r = c.get("/")
        assert "Belum ada data" in r.text and "tidak ditemukan" in r.text
        assert c.get("/health").json()["status"] == "degraded"
        assert c.post("/api/chat", json={"question": "total"}, headers={"X-CSRF-Token": csrf(c)}).json()["refusal"] == "no_data"


# -- escaping ----------------------------------------------------------------------


def test_outlet_names_are_html_escaped(client):
    evil = '<script>alert("x")</script>'
    text = RAW.decode().replace("Toko Mekar", evil).replace("Toko Sinar Abadi", "Toko <b>Sinar</b> Abadi")
    upload(client, "xss.csv", text.encode())
    html = client.get("/outlet/OUT1048").text + client.get("/outlet/OUT1003").text
    assert "<script>alert" not in html and "&lt;script&gt;alert" in html
    assert "<b>Sinar</b>" not in html


# -- security headers, CSRF, rate limits, metrics ---------------------------------------


def test_security_headers(client):
    h = client.get("/").headers
    assert "script-src 'self'" in h["content-security-policy"] and "unsafe-inline" not in h["content-security-policy"]
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert "camera=()" in h["permissions-policy"]
    assert "server" not in h
    assert "strict-transport-security" not in h
    assert "access-control-allow-origin" not in h


def test_hsts_when_https(tmp_path):
    with make(tmp_path, force_https=True) as c:
        assert "max-age" in c.get("/health").headers["strict-transport-security"]


def test_no_inline_script_or_style_in_templates():
    for p in (config.ROOT / "src/dk_sales/web/templates").glob("*.html"):
        t = p.read_text()
        assert "<script>" not in t and "style=" not in t and " on" + "click=" not in t, p.name


def test_csrf_required_on_every_post(client):
    for path in ["/api/chat", "/api/telegram/send", "/dataset/reset", "/logout"]:
        assert client.post(path, json={}).status_code == 403, path
    assert client.post("/api/chat", json={"question": "x"}, headers={"X-CSRF-Token": "wrong"}).status_code == 403


def test_rate_limits(tmp_path):
    with make(tmp_path, chat_rate_per_minute=3) as c:
        tok = csrf(c)
        codes = [c.post("/api/chat", json={"question": "total"}, headers={"X-CSRF-Token": tok}).status_code for _ in range(5)]
        assert codes[:3] == [200, 200, 200] and codes[3] == 429
    with make(tmp_path, rate_limit_per_minute=5) as c:
        codes = [c.get("/api/summary").status_code for _ in range(8)]
        assert 429 in codes
        assert c.get("/health").status_code == 200


def test_request_body_limit(tmp_path):
    with make(tmp_path, max_upload_mb=1) as c:
        r = c.post("/api/chat", content=b"x" * (2 * 1024 * 1024), headers={"content-type": "application/json"})
        assert r.status_code == 413


def test_metrics_protected(tmp_path):
    with make(tmp_path, metrics_token="m" * 30) as c:
        assert c.get("/metrics").status_code == 401
        assert c.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        r = c.get("/metrics", headers={"Authorization": "Bearer " + "m" * 30})
        assert r.status_code == 200 and "http_requests_total" in r.text and "dq_issue_rows" in r.text


def test_untrusted_host_rejected(client):
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400


# -- production configuration ---------------------------------------------------------


def test_production_refuses_unsafe_config():
    with pytest.raises(ConfigError) as e:
        from_env({"APP_ENV": "production"})
    msg = str(e.value)
    for part in ["AUTH_MODE", "SECRET_KEY", "ALLOWED_HOSTS", "FORCE_HTTPS", "TRUSTED_PROXIES", "METRICS_TOKEN"]:
        assert part in msg
    with pytest.raises(ConfigError):
        from_env(
            {
                "APP_ENV": "production",
                "AUTH_MODE": "local",
                "SECRET_KEY": "a" * 40,
                "ALLOWED_HOSTS": "*",
                "FORCE_HTTPS": "true",
                "TRUSTED_PROXIES": "10.0.0.2",
                "METRICS_TOKEN": "x" * 30,
            }
        )


def test_production_accepts_safe_config(users_file):
    s = from_env(
        {
            "APP_ENV": "production",
            "AUTH_MODE": "local",
            "LOCAL_USERS_FILE": str(users_file),
            "SECRET_KEY": secrets.token_urlsafe(32),
            "ALLOWED_HOSTS": "sales.duakelinci.local",
            "FORCE_HTTPS": "true",
            "TRUSTED_PROXIES": "172.20.0.10",
            "METRICS_TOKEN": "t" * 32,
        }
    )
    assert s.is_production and s.host == "0.0.0.0"


def test_development_binds_localhost():
    assert from_env({}).host == "127.0.0.1"


# -- authentication and RBAC ---------------------------------------------------------------


@pytest.fixture
def users_file(tmp_path):
    h = auth.hash_password(PASSWORD)
    data = {
        "users": [
            {"username": "hos", "display_name": "Head of Sales", "password_hash": h, "roles": ["head_of_sales"]},
            {"username": "jabar", "display_name": "Head of Region Jabar", "password_hash": h, "roles": ["head_of_region"], "regions": ["Jawa Barat"]},
            {"username": "sukro", "display_name": "BM Sukro", "password_hash": h, "roles": ["brand_manager"], "brands": ["Sukro"]},
            {"username": "admin", "display_name": "Admin", "password_hash": h, "roles": ["admin"]},
        ]
    }
    p = tmp_path / "users.json"
    p.write_text(json.dumps(data))
    return p


def login(c: TestClient, username: str, password: str = PASSWORD):
    tok = csrf(c, "/login")
    return c.post("/login", data={"username": username, "password": password, "csrf_token": tok}, follow_redirects=False)


def test_login_required_and_session_cookie_flags(tmp_path, users_file):
    with make(tmp_path, auth_mode="local", local_users_file=users_file, force_https=True) as c:
        r = c.get("/", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
        assert c.get("/api/overview").status_code == 401
        r = login(c, "hos")
        assert r.status_code == 303
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie


def test_login_failure_and_lockout(tmp_path, users_file):
    with make(tmp_path, auth_mode="local", local_users_file=users_file) as c:
        assert login(c, "hos", "salah").status_code == 401
        assert login(c, "nobody", "salah").status_code == 401
        for _ in range(5):
            login(c, "hos", "salah")
        assert login(c, "hos").status_code == 429
    audit = (tmp_path / "var" / "audit.jsonl").read_text()
    assert '"failed"' in audit and '"locked"' in audit and PASSWORD not in audit


def test_session_timeout(tmp_path, users_file, monkeypatch):
    with make(tmp_path, auth_mode="local", local_users_file=users_file, session_ttl_minutes=1) as c:
        login(c, "hos")
        assert c.get("/api/overview").status_code == 200
        import time as _t

        real = _t.time
        monkeypatch.setattr("dk_sales.web.app.time.time", lambda: real() + 3600)
        assert c.get("/api/overview").status_code == 401


def test_head_of_region_cannot_see_other_regions(tmp_path, users_file):
    with make(tmp_path, auth_mode="local", local_users_file=users_file) as c:
        login(c, "jabar")
        html = c.get("/").text
        assert "Rp310,9 juta" in html and "Jabodetabek" not in html and "Kalimantan" not in html
        o = c.get("/api/overview").json()
        assert {r["key"] for r in o["region"]} == {"Jawa Barat"}
        assert all(w["region"] == "Jawa Barat" for w in o["weakest"])
        assert c.get("/api/sales?dimension=region&region=Jabodetabek").status_code == 403
        assert c.get("/outlet/OUT1004").status_code == 404
        assert "Jabodetabek" not in c.get("/export/region.csv").text
        assert "Jabodetabek" not in c.get("/api/summary").json()["text"]
        tok = csrf(c)
        for q in ["penjualan Jabodetabek", "penjualan per region", "detail OUT1004", "5 outlet terlemah", "total penjualan"]:
            d = c.post("/api/chat", json={"question": q}, headers={"X-CSRF-Token": tok}).json()
            assert "Rp495,8 juta" not in d["text"] and "Rp1,73 miliar" not in d["text"], q
        assert c.post("/upload", files={"file": ("a.csv", RAW, "text/csv")}, data={"csrf_token": tok}).status_code == 403


def test_brand_manager_scope_in_ui(tmp_path, users_file):
    with make(tmp_path, auth_mode="local", local_users_file=users_file) as c:
        login(c, "sukro")
        o = c.get("/api/overview").json()
        assert {r["key"] for r in o["brand"]} == {"Sukro"}


def test_logout(tmp_path, users_file):
    with make(tmp_path, auth_mode="local", local_users_file=users_file) as c:
        login(c, "admin")
        tok = csrf(c)
        assert c.post("/logout", data={"csrf_token": tok}, follow_redirects=False).status_code == 303
        assert c.get("/api/overview").status_code == 401


def test_entra_role_mapping():
    u = auth.map_entra_roles({"roles": ["HeadOfRegion.JawaBarat", "BrandManager.TosTos"], "name": "A", "preferred_username": "a@dk"})
    assert u.roles == ["brand_manager", "head_of_region"] and u.regions == ["Jawa Barat"] and u.brands == ["Tos Tos"]
    with pytest.raises(auth.AuthError):
        auth.map_entra_roles({"roles": ["Viewer"]})
    assert auth.User("x", "x", []).scope().regions == frozenset()


def test_entra_oidc_flow_validates_token(tmp_path):
    jwt = pytest.importorskip("jwt")
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    s = Settings(app_env="test", auth_mode="oidc", oidc_tenant_id="tid", oidc_client_id="cid", oidc_client_secret="sec", oidc_redirect_uri="https://x/cb")
    url, saved = auth.oidc_start(s)
    assert "code_challenge" in url and "tid" in url

    class Jwks:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": key.public_key()})()

    def token(nonce, aud="cid"):
        claims = {
            "iss": "https://login.microsoftonline.com/tid/v2.0",
            "aud": aud,
            "nonce": nonce,
            "roles": ["HeadOfSales"],
            "name": "Rina",
            "preferred_username": "rina@dk",
            "exp": 9_999_999_999,
        }
        return {"id_token": jwt.encode(claims, key, algorithm="RS256")}

    u = auth.oidc_finish(s, {"state": saved["state"], "code": "c"}, saved, http_post=lambda url, data: token(saved["nonce"]), jwks_client=Jwks())
    assert u.roles == ["head_of_sales"] and u.auth_source == "entra"
    with pytest.raises(auth.AuthError):
        auth.oidc_finish(s, {"state": "other", "code": "c"}, saved, http_post=lambda url, data: token(saved["nonce"]), jwks_client=Jwks())
    with pytest.raises(auth.AuthError):
        auth.oidc_finish(s, {"state": saved["state"], "code": "c"}, saved, http_post=lambda url, data: token("wrong"), jwks_client=Jwks())
    with pytest.raises(jwt.InvalidAudienceError):
        auth.oidc_finish(s, {"state": saved["state"], "code": "c"}, saved, http_post=lambda url, data: token(saved["nonce"], aud="other"), jwks_client=Jwks())


# -- observability resilience ---------------------------------------------------------------


def test_langfuse_down_does_not_break_requests(tmp_path):
    s = Settings(app_env="test", data_dir=tmp_path / "var", langfuse_host="http://127.0.0.1:9", langfuse_public_key="pk", langfuse_secret_key="sk")
    with TestClient(create_app(s)) as c:
        tok = csrf(c)
        r = c.post("/api/chat", json={"question": "penjualan per brand"}, headers={"X-CSRF-Token": tok})
        assert r.status_code == 200 and "Kacang Dua Kelinci" in r.json()["text"]
        assert c.get("/api/summary").status_code == 200


def test_logs_have_no_question_text(tmp_path, capsys):
    s = Settings(app_env="development", data_dir=tmp_path / "var")
    with TestClient(create_app(s)) as c:
        tok = csrf(c)
        c.post("/api/chat", json={"question": "penjualan RAHASIA per brand"}, headers={"X-CSRF-Token": tok})
    out = capsys.readouterr().out
    assert '"chat_turn"' in out and "RAHASIA" not in out
    line = next(line for line in out.splitlines() if '"chat_turn"' in line)
    assert json.loads(line)["intent"] == "breakdown"


def test_settings_invalid_values():
    with pytest.raises(ConfigError):
        from_env({"APP_ENV": "staging"})
    with pytest.raises(ConfigError):
        from_env({"PORT": "abc"})


def test_vendored_echarts_hash():
    import hashlib

    p = config.ROOT / "src/dk_sales/web/static/vendor/echarts-5.6.0.min.js"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == "bf4a223524e40b77c304bec67e1222cf551f14880cf42c69dc046558e11c07b1"


def test_filters_and_print(client):
    r = client.get("/?region=Jawa%20Barat&brand=Sukro")
    assert r.status_code == 200 and "Jawa Barat" in r.text and 'class="fchip"' in r.text
    assert client.get("/?region=Atlantis").status_code == 200
    p = client.get("/summary/print?period=2026-10")
    assert p.status_code == 200 and "Oktober 2026" in p.text


def test_view_helpers():
    from dk_sales.web import views

    sp = views.sparkline([1, 3, 2])
    assert sp["points"].count(",") == 3 and sp["last"][0] > 100
    assert views.sparkline([])["points"] == ""
    b = views.bullet(10, 100)
    assert b["bar"] < b["median"] <= b["width"]


def test_upload_json_mode_for_progress_bar(client):
    tok = csrf(client)
    ok = client.post("/upload", files={"file": ("sales.csv", RAW)}, data={"csrf_token": tok}, headers={"Accept": "application/json"})
    assert ok.status_code == 200 and ok.json()["ok"] is True and "diterima" in ok.json()["message"]
    bad = client.post("/upload", files={"file": ("x.csv", b"a,b\n1,2\n")}, data={"csrf_token": tok}, headers={"Accept": "application/json"})
    assert bad.status_code == 400 and bad.json()["ok"] is False and "Kolom wajib" in bad.json()["message"]


def test_summary_llm_polish_is_number_checked(tmp_path):
    from dk_sales.chat.llm import LLMResponse

    class Polisher:
        def __init__(self, text):
            self.text = text

        def create(self, system, messages, tools=None):
            return LLMResponse([{"type": "text", "text": self.text}], "end_turn", 300, 120)

    base = dict(app_env="test", anthropic_api_key="k", llm_polish_summary=True)
    good = "Penjualan Sep-Okt 2026 Rp1,73 miliar; Oktober Rp878,4 juta, naik 3,6% dari September."
    with TestClient(create_app(Settings(data_dir=tmp_path / "a", **base), llm_client=Polisher(good))) as c:
        s = c.get("/api/summary").json()
        assert s["source"] == "llm" and s["text"] == good
    bad = "Penjualan Sep-Okt 2026 Rp2,1 miliar, naik 12%."
    with TestClient(create_app(Settings(data_dir=tmp_path / "b", **base), llm_client=Polisher(bad))) as c:
        s = c.get("/api/summary").json()
        assert s["source"] == "template" and s["fallback_reason"] == "guardrail" and "Rp1,73 miliar" in s["text"]


# -- redesign: greeting, visit actions, brand assets ------------------------------------


def _weak():
    from dk_sales import analytics as an
    from dk_sales.web.dataset import load_bytes

    ds = load_bytes("sales.csv", RAW, 10**8, 10**7)
    return an.weakest_outlets(ds.fact, ds.dim_outlet, "all", 5)


def test_greeting_uses_role_or_neutral_title():
    from datetime import datetime

    from dk_sales.web import views

    hos = auth.User("hos", "Bu Rina", ["head_of_sales"])
    at = lambda h: datetime(2026, 11, 25, h, 0, tzinfo=views.WIB)  # noqa: E731
    assert views.greeting(hos, at(7)) == "Selamat pagi, Head of Sales"
    assert views.greeting(hos, at(13)) == "Selamat siang, Head of Sales"
    assert views.greeting(hos, at(16)) == "Selamat sore, Head of Sales"
    assert views.greeting(hos, at(20)) == "Selamat malam, Head of Sales"
    both = auth.User("x", "X", ["admin", "head_of_region"], regions=["Jawa Barat"])
    assert views.greeting(both, at(7)) == "Selamat pagi, Head of Region"
    assert views.greeting(auth.DEV_USER, at(7)) == "Penjualan Dua Kelinci"


def test_visit_task_text_is_short_and_complete():
    from dk_sales.web import views

    w = _weak()[0]
    t = views.visit_task(w, "Sep-Okt 2026")
    assert t.splitlines()[0] == "Tugas kunjungan: Toko Sinar Abadi (OUT1003), Toko Kelontong, Jakarta Barat, Jabodetabek."
    assert "Sep-Okt 2026: net Rp564 ribu, 4% dari median Toko Kelontong (Rp14,8 juta); 3 order." in t
    assert "Saran: Order jarang" in t and "Cek data: Nomor invoice di luar urutan" in t
    assert len(t) < 700
    assert views.reason_line(w) == "Alasan: 4% dari median Toko Kelontong, order jarang (3 vs median 14)."
    assert views.suggestion(w).startswith("Jadwalkan kunjungan rutin")
    assert [views.note_label(n) for n in w.notes] == ["Invoice di luar urutan", "Nama sama dengan OUT1001"]


def test_visit_ics_is_valid_and_escaped():
    from datetime import date, datetime

    from dk_sales.web import views

    w = _weak()[0]
    w.outlet_name = "Toko; Sinar, Abadi\\Baru\nLantai 2"
    body = views.visit_ics(w, "Sep-Okt 2026", date(2026, 11, 26), datetime(2026, 11, 25, 9, 12, tzinfo=views.WIB))
    assert body.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "\n" not in body.replace("\r\n", "")  # only CRLF line breaks, no raw newline from data
    lines = body.split("\r\n")
    assert all(len(line.encode()) <= 75 for line in lines)
    unfolded = body.replace("\r\n ", "")
    assert "DTSTART;VALUE=DATE:20261126\r\nDTEND;VALUE=DATE:20261127" in unfolded
    assert "DTSTAMP:20261125T021200Z" in unfolded
    assert "UID:kunjungan-OUT1003-20261126@penjualan-dua-kelinci" in unfolded
    assert "SUMMARY:Kunjungi Toko\\; Sinar\\, Abadi\\\\Baru\\nLantai 2 (OUT1003)" in unfolded
    assert "LOCATION:Jakarta Barat\\, Jabodetabek" in unfolded
    assert body.count("BEGIN:VEVENT") == 1


def test_next_workday_skips_weekend():
    from datetime import date

    from dk_sales.web import views

    assert views.next_workday(date(2026, 11, 25)) == date(2026, 11, 26)  # Rabu -> Kamis
    assert views.next_workday(date(2026, 11, 27)) == date(2026, 11, 30)  # Jumat -> Senin


def test_visit_ics_endpoint(client):
    r = client.get("/outlet/OUT1003/kunjungan.ics?period=all")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert r.headers["content-disposition"] == 'attachment; filename="kunjungan-OUT1003.ics"'
    assert "SUMMARY:Kunjungi Toko Sinar Abadi (OUT1003)" in r.text
    assert client.get("/outlet/OUT1010/kunjungan.ics").status_code == 404  # not a weak outlet
    assert client.get("/outlet/..%2Fetc/kunjungan.ics").status_code == 404


def test_visit_ics_respects_scope(tmp_path, users_file):
    with make(tmp_path, auth_mode="local", local_users_file=users_file) as c:
        login(c, "jabar")
        assert c.get("/outlet/OUT1003/kunjungan.ics").status_code == 404  # Jabodetabek outlet
        html = c.get("/").text
        assert "Selamat" in html and "Head of Region" in html
        ids = re.findall(r"/outlet/(OUT\d+)/kunjungan\.ics", html)
        assert ids and all(c.get(f"/outlet/{o}/kunjungan.ics").status_code == 200 for o in ids)


def test_dashboard_redesign_parts(client):
    html = client.get("/").text
    assert "Penjualan Dua Kelinci" in html and "Oktober naik 3,6%" in html and "5 outlet perlu dikunjungi" in html
    assert html.count('class="btn-primary') == 1  # exactly one red primary button
    assert 'id="chart-cum"' in html and "membuat Oktober menutup bulan Rp30,9 juta di atas September" in html
    assert 'id="chart-flow"' in html and 'id="flow-focus"' in html and "Jawa Timur &#9650; +92,4% Sep ke Okt" in html
    for label in ("Buka dashboard", "Lihat 5 outlet", "Region saya", "Tanya data"):
        assert label in html
    for label in ("Ringkasan", "Outlet", "Telegram", "Tanya data", "Kualitas data"):
        assert f'<span class="rail-label">{label}</span>' in html
    assert html.count("Jadwalkan kunjungan</a>") == 5 and html.count("Salin tugas</button>") == 5
    assert "Logo dan nama Dua Kelinci milik PT Dua Kelinci, dipakai hanya untuk keperluan tes rekrutmen." in html
    assert "Kirim ke Telegram</button>" not in html  # sending only when Telegram is configured


def test_send_button_only_when_telegram_configured(tmp_path):
    with make(tmp_path, telegram_bot_token="123:abc", telegram_chat_id="-1") as c:
        html = c.get("/").text
        assert html.count('class="btn-primary js-tg-send"') == 1 and html.count('class="btn-primary') == 1


def test_brand_assets_are_vendored_and_no_cdn():
    static = config.ROOT / "src/dk_sales/web/static"
    font = static / "fonts/plus-jakarta-sans-latin-wght-normal.woff2"
    assert font.read_bytes()[:4] == b"wOF2"
    assert "SIL OPEN FONT LICENSE" in (static / "fonts/OFL.txt").read_text()
    for logo in ("logo-white.png", "logo-red.png"):
        assert (static / "img" / logo).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    for p in [static / "app.css", static / "app.js", *(config.ROOT / "src/dk_sales/web/templates").glob("*.html")]:
        t = p.read_text()
        assert "fonts.googleapis" not in t and "fonts.gstatic" not in t and "cdn." not in t, p.name

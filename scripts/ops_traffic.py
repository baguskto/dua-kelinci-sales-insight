"""Generate realistic traffic against the ops stack (https://localhost:8443) to verify metrics, logs,
alerts and Langfuse traces. Reads the generated local password from ops/secrets/initial-passwords.txt and
never prints it.

    uv run python scripts/ops_traffic.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://localhost:8443"


def password() -> str:
    text = (ROOT / "ops/secrets/initial-passwords.txt").read_text()
    m = re.search(r"admin, hos, jabar, sukro / (\S+)", text)
    if not m:
        sys.exit("password file not found; run make ops-secrets")
    return m.group(1)


def client(user: str, pw: str) -> tuple[httpx.Client, str]:
    c = httpx.Client(base_url=BASE, verify=False, timeout=30, follow_redirects=False)  # noqa: S501 - local CA
    tok = re.search(r'name="csrf-token" content="([^"]+)"', c.get("/login").text).group(1)
    r = c.post("/login", data={"username": user, "password": pw, "csrf_token": tok})
    assert r.status_code == 303, f"login {user}: {r.status_code}"
    page = c.get("/").text
    return c, re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)


def main() -> None:
    pw = password()
    counts: dict[str, int] = {}

    def note(k: str) -> None:
        counts[k] = counts.get(k, 0) + 1

    users = {u: client(u, pw) for u in ("admin", "hos", "jabar", "sukro")}
    # A failed login for the login-failure metric and audit log.
    bad = httpx.Client(base_url=BASE, verify=False)  # noqa: S501
    tok = re.search(r'name="csrf-token" content="([^"]+)"', bad.get("/login").text).group(1)
    bad.post("/login", data={"username": "hos", "password": "salah", "csrf_token": tok})
    note("login_failed")

    for u, (c, _) in users.items():
        for path in [
            "/",
            "/?period=2026-09",
            "/?period=2026-10",
            "/?region=Jawa%20Barat",
            "/?brand=Sukro",
            "/outlet/OUT1003",
            "/outlet/OUT1049",
            "/api/overview",
            "/api/summary",
            "/export/weakest.csv",
            "/export/region.csv",
            "/summary/print",
            "/tidak-ada",
        ]:
            r = c.get(path)
            note(f"{u} GET {r.status_code}")

    admin, atok = users["admin"]
    raw = (ROOT / "sales.csv").read_bytes()
    for name, data in [
        ("sales.csv", raw),
        ("kolom-hilang.csv", raw.replace(b"net_sales_idr", b"nett")),
        ("biner.csv", b"\x00\x01" * 100),
        ("palsu.xlsx", b"bukan zip"),
        ("titik-koma.csv", raw.replace(b",", b";")),
        ("sales.csv", raw),
    ]:
        r = admin.post("/upload", files={"file": (name, data)}, data={"csrf_token": atok}, headers={"Accept": "application/json"})
        note(f"upload {r.status_code}")

    for u in ("hos", "jabar"):
        c, t = users[u]
        r = c.post("/api/telegram/send", json={"period": "all"}, headers={"X-CSRF-Token": t})
        note(f"telegram {r.json().get('dry_run')}")

    questions = [i["q"] for i in json.loads((ROOT / "tests/eval/golden.json").read_text())]
    questions += [i["q"] if i["q"] != "LONG" else "berapa penjualan " * 40 for i in json.loads((ROOT / "tests/eval/redteam.json").read_text())]
    rotation = ["hos", "jabar", "sukro", "admin"]
    for n, q in enumerate(questions):
        c, t = users[rotation[n % len(rotation)]]
        r = c.post("/api/chat", json={"question": q}, headers={"X-CSRF-Token": t})
        d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        note(f"chat {r.status_code} {d.get('mode', '-')} {'refusal' if d.get('refusal') else 'answer'}")
        time.sleep(1.6)

    # A few slow, scrape-like reads and a burst for the rate limiter.
    c, _ = users["hos"]
    for _ in range(5):
        c.get("/api/overview")
    for k in sorted(counts):
        print(f"{counts[k]:4d}  {k}")


if __name__ == "__main__":
    main()

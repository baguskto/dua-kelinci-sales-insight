"""Screenshots of the dashboard for README and docs/img, from a local server on the default sales.csv.
Starts two in-process servers (local mode, and local accounts for the Head of Region greeting); no Docker.

    uv run python scripts/ui_screenshots.py
"""

from __future__ import annotations

import json
import secrets
import socket
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from dk_sales.web import auth
from dk_sales.web.app import create_app
from dk_sales.web.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs/img"


def _serve(settings: Settings) -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    settings.port = port
    srv = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    while not srv.started:
        time.sleep(0.1)
    return f"http://127.0.0.1:{port}"


def _ready(page) -> None:
    page.wait_for_selector("#chart-flow svg")
    page.wait_for_timeout(400)


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    url = _serve(Settings(app_env="test", data_dir=tmp / "a"))
    # Throwaway account with a random password, only for the greeting screenshot.
    pw = secrets.token_urlsafe(16)
    users = tmp / "users.json"
    h = auth.hash_password(pw)
    users.write_text(
        json.dumps(
            {
                "users": [
                    {"username": "jabar", "display_name": "Head of Region Jabar", "password_hash": h, "roles": ["head_of_region"], "regions": ["Jawa Barat"]}
                ]
            }
        )
    )
    url_auth = _serve(Settings(app_env="test", data_dir=tmp / "b", auth_mode="local", local_users_file=users))

    with sync_playwright() as p:
        b = p.chromium.launch()
        desk = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        desk.goto(url)
        _ready(desk)
        desk.screenshot(path=IMG / "dashboard-desktop.png")
        desk.screenshot(path=IMG / "dashboard-desktop-full.png", full_page=True)
        desk.click(".rail-btn[data-open=chat-drawer]")
        desk.click(".chip >> text=Region mana yang turun paling dalam?")
        desk.wait_for_selector(".msg.a .meta")
        desk.screenshot(path=IMG / "chat-drawer.png")
        desk.goto(url)
        _ready(desk)
        desk.click(".dq-badge")
        desk.wait_for_timeout(200)
        desk.screenshot(path=IMG / "data-quality-drawer.png")
        desk.goto(url + "/?period=all&region=Jawa%20Barat")
        _ready(desk)
        desk.screenshot(path=IMG / "filter-jawa-barat.png")
        bad = tmp / "rusak.csv"
        bad.write_text("tanggal;invoice\n2026-09-01;INV1\n")
        desk.goto(url)
        desk.click(".dq-badge")
        desk.set_input_files("#upload-file", str(bad))
        desk.click("#upload-form button[type=submit]")
        desk.wait_for_selector("#upload-status.alert-text")
        desk.locator("#upload-status").scroll_into_view_if_needed()
        desk.screenshot(path=IMG / "upload-error.png")

        mob = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        mob.goto(url)
        _ready(mob)
        mob.screenshot(path=IMG / "dashboard-mobile.png")
        mob.screenshot(path=IMG / "dashboard-mobile-full.png", full_page=True)
        mob.evaluate("document.querySelector('#sec-weak').scrollIntoView({behavior: 'instant'})")
        mob.wait_for_timeout(300)
        mob.screenshot(path=IMG / "dashboard-mobile-outlet.png")
        mob.evaluate("document.querySelector('#sec-tg').scrollIntoView({behavior: 'instant'})")
        mob.wait_for_timeout(300)
        mob.screenshot(path=IMG / "dashboard-mobile-telegram.png")

        reg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        reg.goto(url_auth + "/login")
        reg.fill("input[name=username]", "jabar")
        reg.fill("input[name=password]", pw)
        reg.click("button[type=submit]")
        _ready(reg)
        reg.screenshot(path=IMG / "dashboard-head-of-region.png")
        b.close()


if __name__ == "__main__":
    main()

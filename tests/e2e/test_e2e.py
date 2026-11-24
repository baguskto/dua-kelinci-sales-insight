"""End-to-end: real server, real browser (Playwright, Chromium)."""

from __future__ import annotations

import socket
import threading
import time

import pytest

playwright = pytest.importorskip("playwright.sync_api")

expect = playwright.expect
pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import uvicorn

    from dk_sales.web.app import create_app
    from dk_sales.web.settings import Settings

    port = _free_port()
    s = Settings(app_env="test", data_dir=tmp_path_factory.mktemp("var"), port=port)
    srv = uvicorn.Server(uvicorn.Config(create_app(s), host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=5)


def _page(browser, **kw):
    page = browser.new_page(**kw)
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
    return page


def test_dashboard_shows_three_answers(server, browser):
    page = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(server)
    assert page.locator("#h-region").is_visible()
    assert page.locator("#h-brand").is_visible()
    assert page.locator("#h-weak").is_visible()
    page.wait_for_selector("#chart-region svg")
    page.wait_for_selector("#chart-heat svg")
    assert page.locator(".wcard").count() == 5
    assert "OUT1003" in page.locator(".wcard").first.inner_text()
    assert "Rp1,73 miliar" in page.locator("#tg-text").inner_text()
    assert page.errors == [], page.errors  # also proves no CSP violations from inline code


def test_period_toggle_and_filter(server, browser):
    page = _page(browser)
    page.goto(server)
    page.click("nav.periods a:text-is('Okt')")
    expect(page.locator("#tg-text")).to_contain_text("Oktober 2026")
    page.goto(server + "/?period=all&region=Jawa%20Barat")
    assert page.locator(".fchip").inner_text().startswith("Jawa Barat")
    page.click(".fchip")
    expect(page.locator(".fchip")).to_have_count(0)


def test_chat_drawer_answers_with_source(server, browser):
    page = _page(browser)
    page.goto(server)
    page.click(".fab")
    page.fill("#chat-q", "penjualan per region bulan Oktober")
    page.click("#chat-form button")
    page.wait_for_selector(".msg.a .meta")
    ans = page.locator(".msg.a").first.inner_text()
    assert "Jabodetabek Rp256,8 juta" in ans and "Sumber: sales_by" in ans
    page.click(".chip >> text=Kualitas data")
    expect(page.locator(".msg.a .meta")).to_have_count(2)
    expect(page.locator(".msg.a").first).to_contain_text("dikarantina")


def test_upload_broken_file_shows_error(server, browser, tmp_path):
    bad = tmp_path / "rusak.csv"
    bad.write_text("tanggal;invoice\n2026-09-01;INV1\n")
    page = _page(browser)
    page.goto(server)
    page.click(".dq-badge")
    page.set_input_files("#upload-file", str(bad))
    page.click("#upload-form button[type=submit]")
    expect(page.locator("#upload-status")).to_contain_text("Kolom wajib tidak ditemukan")
    page.goto(server)
    assert "Rp1,73 miliar" in page.locator(".kpi.main").inner_text()


def test_mobile_order(server, browser):
    page = _page(browser, viewport={"width": 390, "height": 844})
    page.goto(server)
    weak_y = page.locator("#sec-weak").bounding_box()["y"]
    tg_y = page.locator("#sec-tg").bounding_box()["y"]
    region_y = page.locator("#sec-region").bounding_box()["y"]
    assert weak_y < tg_y < region_y
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

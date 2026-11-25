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
    for chart in ("#chart-cum", "#chart-region", "#chart-brand", "#chart-flow"):
        page.wait_for_selector(chart + " svg")
    assert page.locator(".wcard").count() == 5
    assert "OUT1003" in page.locator(".wcard").first.inner_text()
    assert "Rp1,73 miliar" in page.locator("#tg-text").inner_text()
    assert page.locator(".btn-primary").count() == 1
    assert page.errors == [], page.errors  # also proves no CSP violations from inline code


def test_cumulative_chart_end_labels(server, browser):
    page = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(server)
    page.wait_for_selector("#chart-cum svg")
    svg = page.eval_on_selector("#chart-cum svg", "e => e.textContent")
    assert "Okt  Rp878,4 juta" in svg and "Sep  Rp847,5 juta" in svg, svg
    assert "membuat Oktober menutup bulan Rp30,9 juta di atas September" in page.locator(".insight").inner_text()


def test_period_toggle_and_filter(server, browser):
    page = _page(browser)
    page.goto(server)
    page.click("nav.periods a:text-is('Okt')")
    expect(page.locator("#tg-text")).to_contain_text("Oktober 2026")
    page.goto(server + "/?period=all&region=Jawa%20Barat")
    assert page.locator(".fchip").inner_text().startswith("Jawa Barat")
    page.click(".fchip")
    expect(page.locator(".fchip")).to_have_count(0)
    page.select_option("#f-brand", "Sukro")
    expect(page.locator(".fchip")).to_have_text("Sukro ×")
    assert "brand=Sukro" in page.url


def test_flow_highlight_follows_selection(server, browser):
    page = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(server)
    page.wait_for_selector("#chart-flow svg")
    expect(page.locator("#flow-badge")).to_have_text("Jawa Timur ▲ +92,4% Sep ke Okt")
    page.select_option("#flow-focus", "Jawa Barat")
    expect(page.locator("#flow-badge")).to_have_text("Jawa Barat ▼ -13,9% Sep ke Okt")
    assert "is-down" in page.locator("#flow-badge").get_attribute("class")
    expect(page.locator(".rl-row.is-focus .rl-name")).to_have_text("Jawa Barat")


def test_chat_drawer_answers_with_source(server, browser):
    page = _page(browser)
    page.goto(server)
    page.click(".rail-btn[data-open=chat-drawer]")
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
    assert "Rp1,73" in page.locator(".kpi-main").inner_text()


def test_visit_actions_work_offline(server, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=server)
    page = ctx.new_page()
    page.goto(server)
    card = page.locator(".wcard").first
    with page.expect_download() as dl:
        card.get_by_role("link", name="Jadwalkan kunjungan").click()
    d = dl.value
    assert d.suggested_filename == "kunjungan-OUT1003.ics"
    ics = open(d.path(), encoding="utf-8").read()
    assert ics.startswith("BEGIN:VCALENDAR") and "SUMMARY:Kunjungi Toko Sinar Abadi (OUT1003)" in ics
    card.get_by_role("button", name="Salin tugas").click()
    expect(card.locator(".w-status")).to_have_text("Tugas tersalin. Tempel di chat salesman.")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied.startswith("Tugas kunjungan: Toko Sinar Abadi (OUT1003)") and "Saran:" in copied
    page.click(".btn-primary")
    expect(page.locator("#tg-status")).to_have_text("Ringkasan tersalin. Tempel di grup Telegram.")
    assert page.evaluate("navigator.clipboard.readText()").startswith("Ringkasan penjualan Dua Kelinci")
    ctx.close()


@pytest.mark.parametrize("width", [390, 1280, 1440, 1600])
def test_kpi_numbers_never_overlap(server, browser, width):
    page = _page(browser, viewport={"width": width, "height": 900})
    page.goto(server)
    page.wait_for_function("document.fonts.status === 'loaded'")
    problems = page.evaluate(
        """() => {
      const out = [];
      const inside = (a, b) => a.left >= b.left - 0.5 && a.right <= b.right + 0.5 && a.top >= b.top - 0.5 && a.bottom <= b.bottom + 0.5;
      const overlap = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
      const cards = [...document.querySelectorAll('.kpi')];
      cards.forEach((k, i) => {
        const box = k.getBoundingClientRect();
        const v = k.querySelector('.v');
        [...v.querySelectorAll('.n, .u')].forEach((n) => { if (!inside(n.getBoundingClientRect(), box)) out.push(`card ${i}: number outside card`); });
        [...k.querySelectorAll('.k, .s')].forEach((t) => { if (overlap(t.getBoundingClientRect(), v.querySelector('.n').getBoundingClientRect())) out.push(`card ${i}: text overlaps number`); });
        if (v.scrollWidth > v.clientWidth + 1) out.push(`card ${i}: number overflows`);
        cards.forEach((o, j) => { if (j > i && overlap(box, o.getBoundingClientRect())) out.push(`cards ${i} and ${j} overlap`); });
      });
      return out;
    }"""
    )
    assert problems == []


def test_mobile_layout(server, browser):
    page = _page(browser, viewport={"width": 390, "height": 844})
    page.goto(server)
    y = {s: page.locator(s).bounding_box()["y"] for s in (".mhero", "#sec-rlist", "#sec-weak", "#sec-tg", ".kpis", "#sec-cum")}
    assert y[".mhero"] < y["#sec-rlist"] < y["#sec-weak"] < y["#sec-tg"] < y[".kpis"] < y["#sec-cum"]
    assert "Rp878,4 juta" in page.locator(".mhero").inner_text()
    assert page.locator(".mhero-spark").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    for sel in ("#sec-rlist", "#sec-weak", "#sec-tg"):
        assert page.locator(sel).bounding_box()["width"] >= 350, sel
    bar = page.locator(".rail").bounding_box()
    assert bar["y"] + bar["height"] >= 843 and bar["width"] >= 389  # rail is the bottom bar
    page.click(".rail-btn[data-open=chat-drawer]")
    sheet = page.locator("#chat-drawer").bounding_box()
    assert sheet["width"] >= 389 and sheet["height"] >= 843  # chat is a full-screen sheet
    assert page.errors == [], page.errors

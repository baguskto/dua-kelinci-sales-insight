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


CARDS = [".c-net", ".c-ex", ".c-day", ".c-map", ".c-wf", ".c-top", ".c-share", ".c-move", ".c-weak", ".c-ctn", ".c-dq", ".c-tg"]

FIT = """() => {
  const out = [];
  document.querySelectorAll('.card').forEach((c) => {
    const cr = c.getBoundingClientRect();
    c.querySelectorAll('*').forEach((e) => {
      if (e.closest('svg') && e.tagName !== 'svg') return;
      const r = e.getBoundingClientRect();
      if (!r.width || getComputedStyle(e).display === 'none') return;
      if (r.right > cr.right + 1 || r.left < cr.left - 1 || r.bottom > cr.bottom + 1) out.push(c.className + ' > ' + e.tagName + '.' + (e.getAttribute('class') || ''));
    });
  });
  return out;
}"""


def test_one_screen_at_1440x900(server, browser):
    page = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(server)
    page.wait_for_function("document.fonts.status === 'loaded'")
    for sel in CARDS:
        box = page.locator(sel).bounding_box()
        assert box and box["y"] + box["height"] <= 900, sel  # every card above the fold
    assert page.evaluate("document.documentElement.scrollHeight") <= 900
    assert page.evaluate(FIT) == []
    assert page.locator(".c-weak tbody tr").count() == 5
    assert "OUT1003" not in page.locator(".c-weak").inner_text() and "Toko Sinar Abadi" in page.locator(".c-weak").inner_text()
    assert page.locator("main .btn-primary").count() == 1
    assert page.errors == [], page.errors  # also proves no CSP violations from inline code


@pytest.mark.parametrize("size", [(1280, 800), (1024, 768), (390, 844)])
def test_nothing_clipped_or_overflowing(server, browser, size):
    page = _page(browser, viewport={"width": size[0], "height": size[1]})
    page.goto(server)
    page.wait_for_function("document.fonts.status === 'loaded'")
    assert page.evaluate(FIT) == []
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert page.errors == [], page.errors


def test_line_chart_tooltip_follows_keyboard(server, browser):
    page = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(server)
    tip = page.locator("#net-tip")
    expect(tip).to_contain_text("Oct 31")  # highlight: the day October passes September
    expect(tip).to_contain_text("Rp 878.4M")
    page.focus('svg[data-chart="net"]')
    page.keyboard.press("ArrowLeft")
    expect(tip).to_contain_text("Oct 30")
    page.keyboard.press("Home")
    expect(tip).to_contain_text("Oct 1")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    assert page.locator(".lc-ring").get_attribute("cx") == page.evaluate("JSON.parse(document.getElementById('net-points').textContent)[0].x + ''")


def test_svg_text_is_sans(server, browser):
    page = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(server)
    fams = page.evaluate("[...document.querySelectorAll('svg text')].map(t => getComputedStyle(t).fontFamily)")
    assert fams and all(f.startswith('"Plus Jakarta Sans"') for f in fams), set(fams)


def test_period_toggle_and_filter(server, browser):
    page = _page(browser)
    page.goto(server)
    page.click("nav.periods a:text-is('Sep')")
    expect(page.locator("#h-net")).to_have_text("Net sales")  # no earlier month to compare with
    page.click("nav.periods a:text-is('Oct')")
    expect(page.locator("#tg-text")).to_contain_text("Oct vs Sep")
    page.goto(server + "/?period=all&region=Jawa%20Barat")
    assert page.locator(".fchip").inner_text().startswith("West Java")
    page.click(".fchip")
    expect(page.locator(".fchip")).to_have_count(0)
    page.select_option("#f-brand", "Sukro")
    expect(page.locator(".fchip")).to_have_text("Sukro ×")
    assert "brand=Sukro" in page.url


def test_map_and_bridge_link_to_filters(server, browser):
    page = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(server)
    page.locator(".bub", has_text="W. Java").locator("circle").click()
    assert "region=Jawa+Barat" in page.url or "region=Jawa%20Barat" in page.url
    expect(page.locator(".fchip")).to_contain_text("West Java")
    page.goto(server)
    page.locator(".wf-lab", has_text="Grosir Lancar Jaya").click()
    assert page.url.endswith("/outlet/OUT1036")


def test_chat_drawer_answers_with_source(server, browser):
    page = _page(browser)
    page.goto(server)
    page.click(".hd-actions [data-open=chat-drawer]")
    page.fill("#chat-q", "penjualan per region bulan Oktober")
    page.click("#chat-form button")
    page.wait_for_selector(".msg.a .meta")
    ans = page.locator(".msg.a").first.inner_text()
    assert "Jabodetabek Rp256,8 juta" in ans and "Source: sales_by" in ans
    page.click(".chip >> text=Kualitas data")
    expect(page.locator(".msg.a .meta")).to_have_count(2)
    page.keyboard.press("Escape")
    expect(page.locator("#chat-drawer")).not_to_be_visible()


def test_upload_broken_file_shows_error(server, browser, tmp_path):
    bad = tmp_path / "rusak.csv"
    bad.write_text("tanggal;invoice\n2026-09-01;INV1\n")
    page = _page(browser)
    page.goto(server)
    page.click(".dq-badge")
    page.set_input_files("#upload-file", str(bad))
    page.click("#upload-form button[type=submit]")
    expect(page.locator("#upload-status")).to_contain_text("File rejected.")
    page.goto(server)
    assert "878.4" in page.locator(".c-net .v").inner_text()


def test_visit_actions_work_offline(server, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=server)
    page = ctx.new_page()
    page.goto(server)
    row = page.locator(".c-weak tbody tr").first
    with page.expect_download() as dl:
        row.get_by_role("link", name="Schedule a visit to Toko Sinar Abadi (.ics)").click()
    d = dl.value
    assert d.suggested_filename == "visit-OUT1003.ics"
    ics = open(d.path(), encoding="utf-8").read()
    assert ics.startswith("BEGIN:VCALENDAR") and "SUMMARY:Visit Toko Sinar Abadi (OUT1003)" in ics
    row.get_by_role("button", name="Copy the visit task for Toko Sinar Abadi").click()
    expect(page.locator("#weak-status")).to_have_text("Task copied.")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert copied.startswith("Visit task: Toko Sinar Abadi (OUT1003)") and "Suggestion:" in copied
    page.click(".c-tg .btn-primary")
    page.click("#copy-btn")
    expect(page.locator("#tg-status")).to_have_text("Summary copied. Paste it into the Telegram group.")
    assert page.evaluate("navigator.clipboard.readText()").startswith("Dua Kelinci, Oct vs Sep")
    ctx.close()


def test_mobile_layout_is_one_column_in_order(server, browser):
    page = _page(browser, viewport={"width": 390, "height": 844})
    page.goto(server)
    boxes = [page.locator(s).bounding_box() for s in CARDS]
    assert all(b["width"] >= 350 for b in boxes)
    assert [b["y"] for b in boxes] == sorted(b["y"] for b in boxes)  # same order as desktop
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.click(".hd-actions [data-open=chat-drawer]")
    sheet = page.locator("#chat-drawer").bounding_box()
    assert sheet["width"] >= 389 and sheet["height"] >= 843  # chat is a full-screen sheet
    assert page.errors == [], page.errors

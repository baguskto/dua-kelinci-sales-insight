"""Click through the static site in a real browser (Playwright, Chromium) and screenshot three views.

Run it against a local copy served under the same subpath as GitHub Pages, or against the live site:

    mkdir -p /tmp/pages && ln -sfn "$PWD/_site" /tmp/pages/dua-kelinci-sales-insight
    python -m http.server 8765 -d /tmp/pages &
    uv run python scripts/showcase/click_site.py http://127.0.0.1:8765/dua-kelinci-sales-insight/ var/click
    uv run python scripts/showcase/click_site.py https://baguskto.github.io/dua-kelinci-sales-insight/ var/click-live

Prints one line per element (PASS/FAIL and what happened) and exits 1 on any failure or console error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

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

# Content of different cells in one table row must not overlap (a wide value pushing into the next cell).
OVERLAP = """() => {
  const out = [];
  document.querySelectorAll('table tr').forEach((tr) => {
    const boxes = [];
    [...tr.children].forEach((cell, ci) => cell.querySelectorAll('span, a, svg, button').forEach((e) => {
      const r = e.getBoundingClientRect();
      if (r.width && getComputedStyle(e).display !== 'none' && !e.closest('.sr-only')) boxes.push([ci, r, e]);
    }));
    for (const [ci, a, ea] of boxes) for (const [cj, b] of boxes) {
      if (ci < cj && a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) out.push(tr.innerText.split('\\n')[0].slice(0, 40) + ': ' + (ea.getAttribute('class') || ea.tagName));
    }
  });
  return out;
}"""

VIEWS = {"default": "", "oct-west-java": "v/2026-10/jawa-barat/all/", "sep-sukro": "v/2026-09/all/sukro/"}


class Run:
    def __init__(self, base: str):
        self.base = base
        self.results: list[tuple[str, bool, str]] = []
        self.errors: list[str] = []

    def watch(self, page: Page) -> Page:
        page.on("pageerror", lambda e: self.errors.append(f"{page.url}: {e}"))
        page.on("console", lambda m: self.errors.append(f"{page.url}: {m.text}") if m.type == "error" else None)
        page.on("response", lambda r: self.errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
        return page

    def step(self, name: str, fn) -> None:
        try:
            detail = fn() or "ok"
            self.results.append((name, True, detail))
        except Exception as exc:  # noqa: BLE001 - report every failing element, then fail the run
            self.results.append((name, False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"))

    def path(self, page: Page) -> str:
        return page.url.removeprefix(self.base)


def click_through(base: str, shots: Path) -> Run:
    run = Run(base)
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base.split("/", 3)[0] + "//" + base.split("/", 3)[2])
        page = run.watch(ctx.new_page())

        def home():
            page.goto(base)
            page.wait_for_function("document.fonts.status === 'loaded'")

        def period_chips():
            home()
            page.click("nav.periods a:text-is('Oct')")
            expect(page.locator("nav.periods a[aria-current=page]")).to_have_text("Oct")
            a = run.path(page)
            page.click("nav.periods a:text-is('Sep')")
            b = run.path(page)
            page.click("nav.periods a:has-text('Sep')>>nth=-1")  # Sep-Oct
            assert run.path(page) == "", run.path(page)
            return f"Oct -> {a}, Sep -> {b}, Sep-Oct -> root"

        def region_select():
            home()
            page.select_option("#f-region", "Jawa Barat")
            page.wait_for_url("**/v/all/jawa-barat/all/")
            expect(page.locator(".fchip")).to_contain_text("West Java")
            return f"West Java -> {run.path(page)}, chip shown"

        def brand_select():
            page.select_option("#f-brand", "Sukro")
            page.wait_for_url("**/v/all/jawa-barat/sukro/")
            expect(page.locator(".fchip")).to_have_count(2)
            return f"Sukro -> {run.path(page)}, two chips, title '{page.title()}'"

        def remove_chip():
            page.locator(".fchip", has_text="West Java").click()
            page.wait_for_url("**/v/all/all/sukro/")
            assert page.locator("#f-region").input_value() == ""
            return f"remove West Java -> {run.path(page)}"

        def map_bubble():
            home()
            page.locator(".bub", has_text="W. Java").locator("circle").click()
            page.wait_for_url("**/v/all/jawa-barat/all/")
            return f"W. Java bubble -> {run.path(page)}"

        def bridge_outlet():
            home()
            page.locator(".wf-lab", has_text="Grosir Lancar Jaya").click()
            page.wait_for_url("**/outlet/OUT1036/")
            expect(page.locator("h1")).to_contain_text("Grosir Lancar Jaya")
            return f"bridge label -> {run.path(page)}"

        def outlet_row():
            home()
            row = page.locator(".c-weak a.w-o").first
            name = row.locator(".w-n").inner_text().strip()
            row.click()
            page.wait_for_url("**/outlet/OUT*/")
            expect(page.locator("h1")).to_contain_text(name)
            path = run.path(page)
            page.click("text=Dashboard")
            assert run.path(page) == "", run.path(page)
            return f"'{name}' -> {path} -> back to dashboard"

        def ics():
            home()
            with page.expect_download() as d:
                page.locator(".c-weak .w-act a").first.click()
            body = Path(d.value.path()).read_text()
            assert body.startswith("BEGIN:VCALENDAR") and "SUMMARY:Visit" in body
            return f"download {d.value.suggested_filename}, VCALENDAR with SUMMARY"

        def csv():
            home()
            with page.expect_download() as d:
                page.click(".c-weak a.hlink")
            body = Path(d.value.path()).read_text(encoding="utf-8-sig")
            assert body.startswith("rank,outlet_id"), body[:40]
            return f"download {d.value.suggested_filename}, {len(body.splitlines()) - 1} rows"

        def drawers():
            home()
            out = []
            for opener, dlg in ((".dq-badge", "#dq-drawer"), ("[data-open=def-drawer]", "#def-drawer"), (".c-tg .btn-primary", "#tg-drawer")):
                page.click(opener)
                expect(page.locator(dlg)).to_be_visible()
                page.keyboard.press("Escape")
                expect(page.locator(dlg)).not_to_be_visible()
                out.append(dlg)
            page.click(".c-dq .btn-sec")
            page.locator("#dq-drawer [data-close]").click()
            expect(page.locator("#dq-drawer")).not_to_be_visible()
            return "open + Escape: " + ", ".join(out) + "; close button works"

        def print_summary():
            home()
            page.click(".c-tg .btn-primary")
            with page.expect_popup() as pop:
                page.click("#tg-drawer a:has-text('Print')")
            pp = run.watch(pop.value)
            pp.wait_for_load_state()
            expect(pp.locator("h1")).to_have_text("Dua Kelinci sales summary")
            text = pp.locator(".print-text").inner_text()
            assert text == page.locator("#tg-text").inner_text(), "print text differs from the drawer"
            path = pp.url.removeprefix(base)
            pp.close()
            page.keyboard.press("Escape")
            return f"Print -> {path}, same text as the drawer"

        def copy_summary():
            home()
            page.click(".c-tg .btn-primary")
            page.click("#copy-btn")
            expect(page.locator("#tg-status")).to_have_text("Summary copied. Paste it into the Telegram group.")
            assert page.evaluate("navigator.clipboard.readText()") == page.locator("#tg-text").inner_text()
            page.keyboard.press("Escape")
            return "clipboard = summary text"

        def copy_task():
            home()
            page.locator(".c-weak [data-copy]").first.click()
            expect(page.locator("#weak-status")).to_have_text("Task copied.")
            clip = page.evaluate("navigator.clipboard.readText()")
            assert clip.startswith("Visit task:"), clip[:40]
            return f"clipboard = '{clip[:40]}...'"

        def tooltips():
            home()
            info = page.locator(".card .info").first
            info.hover()
            tip = page.evaluate("(e) => getComputedStyle(e, '::after').display", info.element_handle())
            assert tip == "block", tip
            page.focus('svg[data-chart="net"]')
            page.keyboard.press("Home")
            expect(page.locator("#net-tip")).to_contain_text("Oct 1")
            return "info tip shows on hover; line chart tip follows Home key"

        def chat():
            home()
            answers = json.loads(page.evaluate("fetch(document.getElementById('chat-drawer').dataset.answers).then(r => r.text())"))
            page.click(".hd-actions [data-open=chat-drawer]")
            expect(page.locator("label.chat-local")).to_be_visible()
            expect(page.locator("label.chat-local")).to_have_text("Free questions need the local app")
            assert page.locator("#chat-q").is_disabled() and page.locator("#chat-form button").is_disabled()
            chips = page.locator("#chat-drawer .chip")
            for i in range(chips.count()):
                q = chips.nth(i).get_attribute("data-q")
                chips.nth(i).click()
                expect(page.locator(".msg.a .meta")).to_have_count(i + 1)
                got = page.locator(".msg.a").first.inner_text()
                assert answers[q]["text"].splitlines()[0][:60] in got, q
            page.keyboard.press("Escape")
            return f"{chips.count()} example questions answered from saved engine output; free text disabled with visible label"

        def screenshots():
            out = []
            for w, h in ((1440, 900), (390, 844)):
                sp = run.watch(browser.new_page(viewport={"width": w, "height": h}))
                for name, path in VIEWS.items():
                    sp.goto(base + path)
                    sp.wait_for_function("document.fonts.status === 'loaded'")
                    clipped = sp.evaluate(FIT) + sp.evaluate(OVERLAP)
                    assert clipped == [], f"{name} {w}: {clipped[:3]}"
                    assert sp.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"{name} {w}: horizontal scroll"
                    sp.screenshot(path=shots / f"{name}-{w}.png", full_page=w < 1000)
                    out.append(f"{name}-{w}")
                sp.close()
            return "no clipping, no horizontal scroll: " + ", ".join(out)

        def every_view():
            # All period x region x brand views, from the links on the root page, at desktop and phone width.
            home()
            segs = page.evaluate(
                """() => ({
                  p: [...document.querySelectorAll('nav.periods a')].map((a) => a.href),
                  r: [...document.querySelectorAll('#f-region option')].map((o) => new URL(o.dataset.href, location.href).href),
                  b: [...document.querySelectorAll('#f-brand option')].map((o) => new URL(o.dataset.href, location.href).href),
                })"""
            )

            def part(url: str, i: int) -> str:
                rest = url.removeprefix(base)
                return rest.split("/")[i + 1] if rest.startswith("v/") else "all"

            periods = sorted({part(u, 0) for u in segs["p"]})
            regions = sorted({part(u, 1) for u in segs["r"]})
            brands = sorted({part(u, 2) for u in segs["b"]})
            paths = ["" if (p, r, b) == ("all", "all", "all") else f"v/{p}/{r}/{b}/" for p in periods for r in regions for b in brands]
            bad = []
            for w, h in ((1440, 900), (390, 844)):
                vp = run.watch(browser.new_page(viewport={"width": w, "height": h}))
                for path in paths:
                    vp.goto(base + path)
                    vp.wait_for_function("document.fonts.status === 'loaded'")
                    found = vp.evaluate(FIT) + vp.evaluate(OVERLAP)
                    if not vp.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"):
                        found.append("horizontal scroll")
                    bad += [f"{w} {path}: {f}" for f in found]
                vp.close()
            assert not bad, f"{len(bad)} problems, first: {bad[:3]}"
            return f"{len(paths)} views x 2 widths: nothing clipped, overlapping or scrolling sideways"

        for name, fn in (
            ("period chips", period_chips),
            ("region select", region_select),
            ("brand select", brand_select),
            ("filter chip remove", remove_chip),
            ("map bubble", map_bubble),
            ("bridge outlet link", bridge_outlet),
            ("outlet row", outlet_row),
            ("visit .ics", ics),
            ("CSV export", csv),
            ("drawers", drawers),
            ("print summary", print_summary),
            ("copy summary", copy_summary),
            ("copy task", copy_task),
            ("tooltips", tooltips),
            ("chat examples", chat),
            ("screenshots 1440 + 390", screenshots),
            ("every view, 1440 + 390", every_view),
        ):
            run.step(name, fn)
        browser.close()
    return run


def main() -> None:
    base = sys.argv[1]
    base = base if base.endswith("/") else base + "/"
    run = click_through(base, Path(sys.argv[2] if len(sys.argv) > 2 else "var/click"))
    for name, ok, detail in run.results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    print(f"console/page/HTTP errors: {len(run.errors)}")
    for e in run.errors[:20]:
        print("  ", e)
    sys.exit(0 if all(ok for _, ok, _ in run.results) and not run.errors else 1)


if __name__ == "__main__":
    main()

"""Build the GitHub Pages site into _site/: one page, the static snapshot of the dashboard exported
from the running app (default view, real data). The shot and the motion GIFs live in the README only.

In the snapshot every control that needs the server (period, filters, chat, upload, Telegram send,
print, .ics, CSV, links to filtered views and outlet pages) is disabled or turned into plain text,
and labelled; drawers, tooltips, the line-chart tooltip and "Copy task" keep working offline.

    uv run python scripts/showcase/build_site.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from ui_screenshots import _serve  # noqa: E402

from dk_sales.web.settings import Settings  # noqa: E402

OUT = ROOT / "_site"
STATIC = ROOT / "src/dk_sales/web/static"
REPO = "https://github.com/baguskto/dua-kelinci-sales-insight"

# Runs in the page before serialising it: makes the snapshot honest about what works without a server.
FREEZE = """(repo) => {
  const note = (el, text) => { el.setAttribute('title', text); el.setAttribute('aria-disabled', 'true'); };
  const FULL = 'Needs the full app';
  // Plain text instead of links that need the server (filters, outlet pages, CSV, print, .ics).
  document.querySelectorAll('a[href]').forEach((a) => {
    const h = a.getAttribute('href');
    if (h.startsWith('#') || h.startsWith('http')) return;
    if (a.matches('.btn-sec.sm, .hlink, #tg-drawer a.btn-sec')) {
      const s = document.createElement('span'); s.className = a.className + ' is-off'; s.innerHTML = a.innerHTML; note(s, FULL);
      if (a.matches('.hlink, #tg-drawer a.btn-sec')) s.append(' (full app)');
      a.replaceWith(s); return;
    }
    a.removeAttribute('href');  // plain text now: same look, no dead link
  });
  document.querySelectorAll('.filt select, .filt button').forEach((el) => { el.disabled = true; note(el, FULL); });
  document.querySelectorAll('.filt select option:first-child').forEach((o) => { o.textContent += ' (full app)'; });
  const ask = document.querySelector('.hd-actions [data-open=chat-drawer]');
  if (ask) { ask.disabled = true; ask.removeAttribute('data-open'); note(ask, FULL); ask.append(' (full app)'); }
  document.querySelectorAll('#upload-form, .js-tg-send, form[action="/dataset/reset"], #chat-drawer').forEach((el) => el.remove());
  document.querySelectorAll('.who').forEach((el) => el.remove());
  document.querySelectorAll('.seg a').forEach((el) => note(el, FULL));
  const bar = document.createElement('a');
  bar.className = 'snapshot-note';
  bar.href = repo;
  bar.title = 'Static snapshot of sales.csv. Period, filters, chat, upload, Telegram and links need the server.';
  bar.textContent = 'Snapshot: full app on GitHub';
  document.querySelector('.filt').after(bar);
  document.querySelector('meta[name=csrf-token]')?.remove();
  return '<!doctype html>\\n' + document.documentElement.outerHTML;
}"""

SNAPSHOT_CSS = """
/* Static snapshot only (build_site.py). */
.snapshot-note { font-size: 13px; color: var(--muted-on-canvas); white-space: nowrap; }
.snapshot-note:hover { color: var(--ink); }
.is-off, .filt select:disabled, .hd-actions button:disabled, .seg a { opacity: .55; cursor: not-allowed; }
.seg a[aria-current="page"] { opacity: 1; }
a:not([href]) { cursor: default; }
a:not([href]):hover, a:not([href]):hover * { background: none; text-decoration: none; }
"""


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    dash = OUT
    for sub in ("fonts", "img", "vendor/lucide"):
        shutil.copytree(STATIC / sub, dash / "static" / sub)
    shutil.copy(STATIC / "app.js", dash / "static/app.js")
    shutil.copy(STATIC / "favicon.svg", dash / "static/favicon.svg")
    (dash / "static/app.css").write_text((STATIC / "app.css").read_text().replace('url("/static/', 'url("../static/') + SNAPSHOT_CSS)

    url = _serve(Settings(app_env="test", data_dir=Path(tempfile.mkdtemp()) / "var"))
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url)
        page.wait_for_function("document.fonts.status === 'loaded'")
        html = page.evaluate(FREEZE, REPO)
        b.close()
    # The live page ran app.js already (class "js", tooltip placed); ship the markup clean, relative paths.
    html = html.replace('<html lang="en" class="js">', '<html lang="en">').replace('"/static/', '"static/').replace("url(/static/", "url(static/")
    (dash / "index.html").write_text(html)
    print(f"{OUT}: {sum(1 for _ in OUT.rglob('*') if _.is_file())} files")


if __name__ == "__main__":
    main()

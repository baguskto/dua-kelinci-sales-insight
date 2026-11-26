"""Crawl the static site from its root page and check that every internal link and asset resolves.

Follows href, src, data-href (filter options) and data-answers (saved chat answers) on every HTML page reached,
plus url(...) in CSS. Works on the built folder or on the live site:

    uv run python scripts/showcase/check_site.py _site
    uv run python scripts/showcase/check_site.py https://baguskto.github.io/dua-kelinci-sales-insight/

Exits 1 when a link is broken, or when an app URL (starting with "/" or "?") survived the rewrite.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from dk_sales.web.static_site import URL_ATTRS, unescape_attr  # noqa: E402

ATTR = re.compile(r"\s(?:" + "|".join(URL_ATTRS) + r')="([^"]*)"')
CSS_URL = re.compile(r'url\("?([^")]+)"?\)')


def _fetch_http(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310  # nosec B310 - https URL given on the command line
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, "", b""


def _fetch_file(root: Path, url: str) -> tuple[int, str, bytes]:
    p = root / urlsplit(url).path.lstrip("/")
    if p.is_dir() or url.endswith("/"):
        p = p / "index.html"
    if not p.is_file():
        return 404, "", b""
    kind = {".html": "text/html", ".css": "text/css"}.get(p.suffix, "application/octet-stream")
    return 200, kind, p.read_bytes()


def crawl(target: str) -> dict:
    live = target.startswith(("http://", "https://"))
    base = target if target.endswith("/") else target + "/"
    if not live:
        root = Path(target).resolve()
        base = "file:///"

    def fetch(url: str) -> tuple[int, str, bytes]:
        return _fetch_http(url) if live else _fetch_file(root, url[len(base) - 1 :])

    seen: dict[str, int] = {}
    pages, broken, unrewritten, size = 0, [], [], 0
    frontier = [base]
    with ThreadPoolExecutor(16 if live else 1) as pool:
        while frontier:
            batch = [u for u in dict.fromkeys(frontier) if u not in seen]
            frontier = []
            for url, (status, ctype, body) in zip(batch, pool.map(fetch, batch), strict=True):
                seen[url] = status
                if status != 200:
                    broken.append(url)
                    continue
                size += len(body)
                if ctype.startswith("text/html"):
                    pages += 1
                    text = body.decode("utf-8")
                    for raw in ATTR.findall(text):
                        link = unescape_attr(raw)
                        if link.startswith(("/", "?")):
                            unrewritten.append(f"{url}: {link}")
                        elif not link.startswith(("#", "http:", "https:", "mailto:", "data:")):
                            frontier.append(urldefrag(urljoin(url, link)).url)
                elif ctype.startswith("text/css"):
                    for raw in CSS_URL.findall(body.decode("utf-8")):
                        if not raw.startswith("data:"):
                            frontier.append(urljoin(url, raw))
    return {"urls": len(seen), "pages": pages, "bytes": size, "broken": broken, "unrewritten": unrewritten}


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "_site"
    r = crawl(target)
    print(
        f"{target}: {r['urls']} URLs reached, {r['pages']} HTML pages, {r['bytes'] / 1e6:.1f} MB, {len(r['broken'])} broken, {len(r['unrewritten'])} app URLs left"
    )
    for line in (r["broken"] + r["unrewritten"])[:30]:
        print("  ", line)
    sys.exit(1 if r["broken"] or r["unrewritten"] else 0)


if __name__ == "__main__":
    main()

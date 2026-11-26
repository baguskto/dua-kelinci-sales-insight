"""Static export of the dashboard for GitHub Pages: map every server GET URL to a file path and rewrite links.

GitHub Pages ignores query strings, so each server URL gets its own path:

    /?period=P&region=R&brand=B         -> v/P/<region-slug>/<brand-slug>/   ("" for the default view)
    /outlet/ID                          -> outlet/ID/
    /outlet/ID/kunjungan.ics?...        -> ics/P/<region-slug>/<brand-slug>/visit-ID.ics
    /summary/print?period=P             -> print/P/
    /export/KIND.csv?period=P           -> export/KIND-P.csv   (quarantine: export/quarantine.csv)
    /static/...                         -> static/...

"all" stands for "no filter" in the region and brand segments. Every path is written relative to the page that
links to it, because the site is served under /dua-kelinci-sales-insight/. scripts/showcase/build_site.py renders
each route with the real app and writes it to the path below.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit

ALL = "all"
# Attributes that may hold an app URL. data-href: filter options; data-answers: saved chat answers (static build).
URL_ATTRS = ("href", "src", "action", "data-href", "data-answers")
_ATTR_RE = re.compile(r"(\s(?:" + "|".join(URL_ATTRS) + r')=")([^"]*)(")')
_OUTLET_RE = re.compile(r"^/outlet/(OUT\d{1,9})(/kunjungan\.ics)?$")
_EXPORT_RE = re.compile(r"^/export/([a-z]+)\.csv$")
EXPORT_KINDS = ("region", "brand", "weakest")


_ENTITY_RE = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")


def unescape_attr(value: str) -> str:
    """Decode character references the way browsers do inside an attribute: only the ones closed by ';'.

    html.unescape would turn the '&reg' of '?period=all&region=X' into the registered sign; a browser does not."""
    return _ENTITY_RE.sub(lambda m: html.unescape(m.group(0)), value)


class UnknownRoute(ValueError):
    """A link to an app URL that has no static counterpart: the build stops instead of shipping a dead link."""


def slug(value: str) -> str:
    """'Jawa Barat' -> 'jawa-barat'. ASCII, lowercase, words joined by '-'."""
    s = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        raise ValueError(f"cannot slug {value!r}")
    return s


@dataclass(frozen=True)
class Route:
    """One file of the static site: where it goes (relative to the site root) and the app URL that renders it."""

    path: str
    url: str

    @property
    def file(self) -> str:
        """The file to write: directory paths get index.html."""
        return self.path + "index.html" if self.path == "" or self.path.endswith("/") else self.path


class SiteMap:
    """Slugs for the regions and brands in the data, and the URL -> Route mapping that uses them."""

    def __init__(self, regions: list[str], brands: list[str], periods: list[str]):
        self.periods = list(periods)
        self.region_slug = {r: slug(r) for r in regions}
        self.brand_slug = {b: slug(b) for b in brands}
        for kind, m in (("region", self.region_slug), ("brand", self.brand_slug)):
            if len(set(m.values())) != len(m) or ALL in m.values():
                raise ValueError(f"{kind} slugs are not unique or collide with '{ALL}': {m}")
        bad = [p for p in self.periods if not re.fullmatch(r"all|\d{4}-\d{2}", p)]
        if bad:
            raise ValueError(f"unexpected periods {bad}")

    # -- the three view segments ------------------------------------------------------

    def _seg(self, q: dict[str, str]) -> tuple[str, str, str]:
        period = q.get("period") or ALL
        if period not in self.periods:
            raise UnknownRoute(f"period {period!r}")
        region, brand = q.get("region"), q.get("brand")
        if region and region not in self.region_slug:
            raise UnknownRoute(f"region {region!r}")
        if brand and brand not in self.brand_slug:
            raise UnknownRoute(f"brand {brand!r}")
        return period, self.region_slug[region] if region else ALL, self.brand_slug[brand] if brand else ALL

    @staticmethod
    def _query(**kw: str | None) -> str:
        q = {k: v for k, v in kw.items() if v}
        return "?" + urlencode(q) if q else ""

    def view(self, period: str = ALL, region: str | None = None, brand: str | None = None) -> Route:
        p, r, b = self._seg({"period": period, "region": region or "", "brand": brand or ""})
        path = "" if (p, r, b) == (ALL, ALL, ALL) else f"v/{p}/{r}/{b}/"
        return Route(path, "/" + self._query(period=p, region=region, brand=brand))

    def all_views(self) -> list[Route]:
        return [self.view(p, r, b) for p in self.periods for r in [None, *self.region_slug] for b in [None, *self.brand_slug]]

    # -- URL -> Route -------------------------------------------------------------------

    def route(self, url: str) -> Route | None:
        """The static Route for an app URL, None for URLs that stay as they are (anchors, external links)."""
        if not url or url.startswith(("#", "http://", "https://", "mailto:", "data:", "tel:")):
            return None
        parts = urlsplit(url)
        path = parts.path or "/"
        q = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        if path == "/":
            return self.view(q.get("period") or ALL, q.get("region"), q.get("brand"))
        if path.startswith("/static/"):
            return Route(path[1:], path)
        if m := _OUTLET_RE.match(path):
            oid = m.group(1)
            if not m.group(2):
                return Route(f"outlet/{oid}/", path)
            p, r, b = self._seg(q)
            return Route(f"ics/{p}/{r}/{b}/visit-{oid}.ics", path + self._query(period=p, region=q.get("region"), brand=q.get("brand")))
        if path == "/summary/print":
            p, _, _ = self._seg({"period": q.get("period", ALL)})
            return Route(f"print/{p}/", path + self._query(period=p))
        if m := _EXPORT_RE.match(path):
            kind = m.group(1)
            if kind == "quarantine":
                return Route("export/quarantine.csv", path)
            if kind in EXPORT_KINDS:
                p, _, _ = self._seg({"period": q.get("period", ALL)})
                return Route(f"export/{kind}-{p}.csv", path + self._query(period=p))
        raise UnknownRoute(url)


def relative(from_path: str, to_path: str) -> str:
    """Link from the page at from_path to to_path, both relative to the site root ('' is the root page)."""
    return ("../" * from_path.count("/") + to_path) or "./"


def rewrite_html(page: str, from_path: str, site: SiteMap, found: set[Route] | None = None) -> str:
    """Point every app URL in page (href, src, action, data-href, data-answers) at its static file.

    Routes it links to are added to found, so the build can render them too. Fragments are kept."""

    def sub(m: re.Match[str]) -> str:
        base, _, frag = unescape_attr(m.group(2)).partition("#")
        r = site.route(base)
        if r is None:
            return m.group(0)
        if found is not None:
            found.add(r)
        new = relative(from_path, r.path) + (f"#{frag}" if frag else "")
        return m.group(1) + html.escape(new, quote=True) + m.group(3)

    return _ATTR_RE.sub(sub, page)

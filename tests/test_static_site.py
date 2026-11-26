"""Static export for GitHub Pages: slug and path mapping, link rewrite, the static_export pages, and a full build."""

from __future__ import annotations

import importlib.util
import json

import pytest
from fastapi.testclient import TestClient

from dk_sales import config
from dk_sales.web.app import create_app
from dk_sales.web.settings import Settings
from dk_sales.web.static_site import Route, SiteMap, UnknownRoute, relative, rewrite_html, slug, unescape_attr

SITE = SiteMap(["Jabodetabek", "Jawa Barat"], ["Kacang Dua Kelinci", "Sukro", "Tos Tos"], ["2026-09", "2026-10", "all"])


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, config.ROOT / f"scripts/showcase/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_slug():
    assert slug("Jawa Barat") == "jawa-barat"
    assert slug("Tos Tos") == "tos-tos" and slug("  Kacang  Dua-Kelinci ") == "kacang-dua-kelinci"
    assert slug("Café 2") == "cafe-2"
    with pytest.raises(ValueError):
        slug("!!")


def test_sitemap_rejects_colliding_slugs():
    with pytest.raises(ValueError):
        SiteMap(["Jawa Barat", "jawa  barat"], [], ["all"])
    with pytest.raises(ValueError):
        SiteMap(["All"], [], ["all"])


def test_view_paths_cover_every_combination():
    views = SITE.all_views()
    assert len(views) == 3 * 3 * 4 and len({v.path for v in views}) == len(views)
    assert SITE.view() == Route("", "/?period=all")
    assert SITE.view("2026-10", "Jawa Barat", "Tos Tos") == Route("v/2026-10/jawa-barat/tos-tos/", "/?period=2026-10&region=Jawa+Barat&brand=Tos+Tos")
    assert SITE.view("all", None, "Sukro").path == "v/all/all/sukro/"


@pytest.mark.parametrize(
    ("url", "path"),
    [
        ("/", ""),
        ("?period=all", ""),
        ("?period=2026-09&region=Jawa%20Barat", "v/2026-09/jawa-barat/all/"),
        ("/?brand=Sukro&period=2026-10", "v/2026-10/all/sukro/"),
        ("/outlet/OUT1036", "outlet/OUT1036/"),
        ("/outlet/OUT1036/kunjungan.ics?period=2026-10&region=Jawa+Barat", "ics/2026-10/jawa-barat/all/visit-OUT1036.ics"),
        ("/summary/print?period=2026-10&region=Jawa+Barat", "print/2026-10/"),
        ("/export/weakest.csv?period=all&brand=Sukro", "export/weakest-all.csv"),
        ("/export/quarantine.csv", "export/quarantine.csv"),
        ("/static/app.css", "static/app.css"),
    ],
)
def test_route_mapping(url, path):
    r = SITE.route(url)
    assert r is not None and r.path == path
    # The URL the build renders keeps only what the app reads for that route.
    if path.startswith(("print/", "export/weakest")):
        assert "region" not in r.url and "brand" not in r.url


@pytest.mark.parametrize("url", ["#main", "https://github.com/x", "mailto:a@b.c", "data:image/png;base64,xx"])
def test_route_leaves_anchors_and_external_links(url):
    assert SITE.route(url) is None


@pytest.mark.parametrize("url", ["/login", "/api/chat", "/?period=2025-01", "/?region=Atlantis", "/export/secret.csv", "/outlet/../etc"])
def test_route_refuses_urls_without_a_static_file(url):
    with pytest.raises(UnknownRoute):
        SITE.route(url)


def test_route_file():
    assert Route("", "/").file == "index.html" and Route("outlet/OUT1/", "").file == "outlet/OUT1/index.html"
    assert Route("export/weakest-all.csv", "").file == "export/weakest-all.csv"


def test_relative():
    assert relative("", "") == "./" and relative("", "outlet/OUT1/") == "outlet/OUT1/"
    assert relative("v/all/jawa-barat/all/", "") == "../../../../"
    assert relative("outlet/OUT1/", "static/app.css") == "../../static/app.css"


def test_unescape_attr_matches_browsers():
    # '&reg' without ';' stays as written inside an attribute; '&amp;' decodes.
    assert unescape_attr("?period=all&region=Jawa") == "?period=all&region=Jawa"
    assert unescape_attr("?period=all&amp;brand=Sukro&#38;x=1") == "?period=all&brand=Sukro&x=1"


def test_rewrite_html():
    page = (
        '<a href="?period=all&region=Jawa%20Barat">W</a> <a class="x" href="/outlet/OUT1#top">o</a> '
        '<option value="Sukro" data-href="?period=2026-10&amp;brand=Sukro"></option> <img src="/static/img/logo.png" alt=""> '
        '<a href="#main">skip</a> <a href="https://github.com/x">gh</a> <dialog data-answers="/static/chat-answers.json"></dialog>'
    )
    found: set[Route] = set()
    out = rewrite_html(page, "v/2026-10/all/sukro/", SITE, found)
    up = "../../../../"
    assert f'href="{up}v/all/jawa-barat/all/"' in out
    assert f'href="{up}outlet/OUT1/#top"' in out
    assert f'data-href="{up}v/2026-10/all/sukro/"' in out
    assert f'src="{up}static/img/logo.png"' in out and f'data-answers="{up}static/chat-answers.json"' in out
    assert 'href="#main"' in out and 'href="https://github.com/x"' in out
    assert {r.path for r in found} == {"v/all/jawa-barat/all/", "outlet/OUT1/", "v/2026-10/all/sukro/", "static/img/logo.png", "static/chat-answers.json"}
    with pytest.raises(UnknownRoute):
        rewrite_html('<form action="/logout"></form>', "", SITE)


def test_static_export_pages_label_what_needs_the_server(tmp_path):
    s = Settings(app_env="test", data_dir=tmp_path / "var", static_export=True)
    with TestClient(create_app(s)) as c:
        html = c.get("/?period=2026-10&region=Jawa%20Barat").text
        outlet = c.get("/outlet/OUT1036").text
    assert "<title>October 2026, West Java - Dua Kelinci Sales</title>" in html
    assert 'data-answers="/static/chat-answers.json"' in html
    assert '<label class="chat-local" for="chat-q">Free questions need the local app</label>' in html
    assert '<input id="chat-q" name="question" disabled>' in html
    assert 'id="upload-form"' not in html and "/dataset/reset" not in html and 'class="who"' not in html
    assert "js-tg-send" not in html and "Sending needs the local app" in html
    assert 'method="get"' not in html and "btn-sec apply" not in html
    assert "Static export of sales.csv" in html and "python app.py" in html and "Static export of sales.csv" in outlet


def test_server_pages_unchanged_by_the_flag(tmp_path):
    with TestClient(create_app(Settings(app_env="test", data_dir=tmp_path / "var"))) as c:
        html = c.get("/").text
    assert "data-answers" not in html and "Static export" not in html and 'method="get" action="/"' in html
    assert 'data-href="?period=all&brand=Sukro"' in html  # filter options navigate by URL on the server too


def test_build_and_crawl(tmp_path):
    """The whole export: every view, outlet, .ics, print and CSV, and the crawl finds no broken link."""
    stats = _load("build_site").build(tmp_path / "site")
    assert stats["views"] == 3 * 7 * 9  # periods x (all + 6 regions) x (all + 8 brands)
    assert stats["pages"] == stats["views"] + 52 + 3  # dashboards, outlet pages, print summaries
    r = _load("check_site").crawl(str(tmp_path / "site"))
    assert r["broken"] == [] and r["unrewritten"] == [] and r["pages"] == stats["pages"]
    answers = json.loads((tmp_path / "site/static/chat-answers.json").read_text())
    assert all(a["text"] and not a["refusal"] for a in answers.values()) and len(answers) == 5

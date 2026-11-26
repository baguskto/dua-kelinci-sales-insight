"""Build the GitHub Pages site into _site/: a static export of every GET view of the dashboard, real data.

The app runs in-process with static_export=True and each view is rendered by its own route, then written to a
path GitHub Pages can serve (it ignores query strings): every period x region x brand dashboard, the 52 outlet
pages, the visit .ics files, the print summaries and the CSV exports. dk_sales.web.static_site maps the URLs and
rewrites the links relative to each page, because the site lives under /dua-kelinci-sales-insight/.

Chat: the offline engine answers the example questions here, at build time, and the drawer reads those answers.
Free questions, upload and Telegram send need a server; the pages say so next to the control.

    uv run python scripts/showcase/build_site.py
    uv run python scripts/showcase/check_site.py _site     # every link resolves
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from dk_sales import analytics as an
from dk_sales.web import auth, views
from dk_sales.web.app import create_app
from dk_sales.web.settings import Settings
from dk_sales.web.static_site import Route, SiteMap, rewrite_html

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_site"
STATIC = ROOT / "src/dk_sales/web/static"


def build(out: Path = OUT) -> dict[str, int]:
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(STATIC, out / "static")
    # One in-process client renders ~800 routes: the per-IP request limit is for real visitors, not the build.
    settings = Settings(app_env="test", data_dir=Path(tempfile.mkdtemp()) / "var", static_export=True, rate_limit_per_minute=1_000_000)
    app = create_app(settings)
    with TestClient(app) as client:  # the lifespan loads sales.csv
        ds = app.state.store.active
        site = SiteMap(sorted(set(ds.fact["region"])), sorted(set(ds.fact["brand"])), sorted(an.valid_periods(ds.fact)))

        answers = {q: app.state.chat.answer(q, ds, auth.DEV_USER, f"static-{i}").to_dict() for i, q in enumerate(views.CHAT_EXAMPLES)}
        (out / "static/chat-answers.json").write_text(json.dumps(answers, ensure_ascii=False, default=str))

        todo: list[Route] = [*site.all_views(), *(site.route(f"/outlet/{o}") for o in sorted(ds.dim_outlet["outlet_id"]))]  # type: ignore[misc]
        done: dict[str, str] = {}
        linked_static: set[str] = set()
        while todo:
            r = todo.pop()
            if r.path in done:
                if done[r.path] != r.url:
                    raise SystemExit(f"two URLs map to {r.path}: {done[r.path]} and {r.url}")
                continue
            done[r.path] = r.url
            if r.path.startswith("static/"):
                linked_static.add(r.path)
                continue
            resp = client.get(r.url)
            if resp.status_code != 200:
                raise SystemExit(f"{r.url} -> HTTP {resp.status_code}")
            dest = out / r.file
            dest.parent.mkdir(parents=True, exist_ok=True)
            if resp.headers["content-type"].startswith("text/html"):
                found: set[Route] = set()
                dest.write_text(rewrite_html(resp.text, r.path, site, found))
                todo.extend(found)
            else:
                dest.write_bytes(resp.content)
    missing = sorted(p for p in linked_static if not (out / p).is_file())
    if missing:
        raise SystemExit(f"linked static files missing: {missing}")
    files = [f for f in out.rglob("*") if f.is_file()]
    return {
        "pages": sum(1 for f in files if f.suffix == ".html"),
        "files": len(files),
        "bytes": sum(f.stat().st_size for f in files),
        "views": len(site.all_views()),
    }


def main() -> None:
    stats = build()
    print(f"{OUT}: {stats['pages']} pages ({stats['views']} dashboard views), {stats['files']} files, {stats['bytes'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

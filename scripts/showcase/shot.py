"""Dribbble-style still of the dashboard: 1440x900 at deviceScaleFactor 2, cropped to 1920x1600.

Crop: the first three columns, from the top of the first card row. That area holds the densest
charts on the screen (the cumulative line chart with its tooltip, growth with and without the top
outlet, trading-day ticks, the region bridge, the top-outlet bars and the weakest-outlet tick
meters). The map sits in columns 4-5 and cannot share a 960 CSS px wide crop with the bridge.

    uv run python scripts/showcase/shot.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_screenshots import _serve  # noqa: E402

from dk_sales.web.settings import Settings  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs/img/shot-2x-1920x1600.png"


def main() -> None:
    url = _serve(Settings(app_env="test", data_dir=Path(tempfile.mkdtemp()) / "var"))
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page.goto(url)
        page.wait_for_function("document.fonts.status === 'loaded'")
        page.wait_for_timeout(300)
        first = page.locator(".c-net").bounding_box()
        x, y = first["x"] - 12, first["y"] - 12
        page.screenshot(path=OUT, clip={"x": x, "y": y, "width": 960, "height": 800})
        b.close()
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()

"""Screenshots of the running ops stack for docs/img (Grafana dashboards, alert rules, Langfuse traces).
Reads the generated admin passwords from ops/secrets; never prints them.

    uv run python scripts/ops_screenshots.py
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs/img"


def main() -> None:
    grafana_pw = (ROOT / "ops/secrets/grafana_admin_password").read_text().strip()
    lf_pw = re.search(r"admin@duakelinci.local / (\S+)", (ROOT / "ops/secrets/initial-passwords.txt").read_text()).group(1)
    app_pw = re.search(r"admin, hos, jabar, sukro / (\S+)", (ROOT / "ops/secrets/initial-passwords.txt").read_text()).group(1)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1.25, ignore_https_errors=True)
        page = ctx.new_page()

        # App in production mode behind Caddy, logged in as Head of Region Jawa Barat.
        page.goto("https://localhost:8443/login")
        page.fill("input[name=username]", "jabar")
        page.fill("input[name=password]", app_pw)
        page.click("button[type=submit]")
        page.wait_for_selector("#chart-region svg")
        page.screenshot(path=str(IMG / "prod-head-of-region-jabar.png"))

        page.goto("http://localhost:3000/login")
        page.fill("input[name=user]", "admin")
        page.fill("input[name=password]", grafana_pw)
        page.click("button[type=submit]")
        page.wait_for_url(re.compile(r".*localhost:3000/(\?.*)?$|.*/home.*"), timeout=15000)
        for uid, name in [
            ("dk-service-health", "grafana-service-health"),
            ("dk-sales-usage", "grafana-sales-usage"),
            ("dk-chat-guardrails", "grafana-chat-guardrails"),
            ("dk-data-quality", "grafana-data-quality"),
        ]:
            page.goto(f"http://localhost:3000/d/{uid}?orgId=1&from=now-30m&to=now&kiosk")
            page.wait_for_timeout(4000)
            page.screenshot(path=str(IMG / f"{name}.png"))
        page.goto("http://localhost:3000/alerting/list?view=list")
        page.wait_for_timeout(3000)
        page.get_by_text("Dua Kelinci", exact=True).first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(IMG / "grafana-alert-rules.png"))

        page.goto("http://localhost:3001/auth/sign-in")
        page.fill("input[name=email]", "admin@duakelinci.local")
        page.fill("input[type=password]", lf_pw)
        page.click("button[type=submit]")
        page.wait_for_timeout(4000)
        page.goto("http://localhost:3001/project/sales-insight/traces")
        page.wait_for_timeout(5000)
        page.screenshot(path=str(IMG / "langfuse-traces.png"))
        rows = page.locator("table tbody tr")
        if rows.count():
            rows.first.click()
            page.wait_for_timeout(4000)
            page.screenshot(path=str(IMG / "langfuse-trace-detail.png"))
        page.goto("http://localhost:3001/project/sales-insight/datasets")
        page.wait_for_timeout(4000)
        page.screenshot(path=str(IMG / "langfuse-datasets.png"))
        b.close()
    print("ok")


if __name__ == "__main__":
    main()

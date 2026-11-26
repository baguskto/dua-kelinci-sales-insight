"""Lucide icons (ISC, vendored in static/vendor/lucide), inlined as SVG so they inherit the text color."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from markupsafe import Markup

DIR = Path(__file__).parent / "static" / "vendor" / "lucide"
_BODY = re.compile(r"<svg[^>]*>(.*)</svg>", re.S)


@cache
def _inner(name: str) -> str:
    m = _BODY.search((DIR / f"{name}.svg").read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"not an svg icon: {name}")
    return re.sub(r"\s+", " ", m.group(1)).strip()


def icon(name: str, cls: str = "", size: int = 18) -> Markup:
    """Decorative icon; the element next to it carries the accessible text."""
    return Markup(  # noqa: S704  # nosec B704 - fixed attributes plus a vendored Lucide file, no user input
        f'<svg class="ic{" " + cls if cls else ""}" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="currentColor" '
        f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{_inner(name)}</svg>'
    )


OUTLET_TYPE_ICON = {"Grosir": "warehouse", "Minimarket": "store", "Toko Kelontong": "shopping-basket", "Warung": "house"}

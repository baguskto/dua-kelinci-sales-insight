"""Small presentation helpers: SVG geometry for sparklines and bullet bars, chart payloads."""

from __future__ import annotations

from dk_sales import fmt


def sparkline(values: list[float], width: int = 120, height: int = 28, pad: int = 2) -> dict:
    """Polyline points for a sparkline plus the last point, as plain numbers for SVG attributes."""
    if not values:
        return {"points": "", "last": None, "width": width, "height": height}
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = pad + (width - 2 * pad) * (i / (n - 1) if n > 1 else 0.5)
        y = pad + (height - 2 * pad) * (1 - (v - lo) / span)
        pts.append((round(x, 1), round(y, 1)))
    return {"points": " ".join(f"{x},{y}" for x, y in pts), "last": pts[-1], "width": width, "height": height}


def bullet(value: float, median: float, width: int = 220) -> dict:
    """Geometry for a bullet bar: the outlet's value against the median of its peers."""
    top = max(value, median) * 1.1 or 1
    return {
        "width": width,
        "bar": round(max(value, 0) / top * width, 1),
        "median": round(median / top * width, 1),
    }


def chart_payload(region: list[dict], brand: list[dict], heat: dict, period: str) -> dict:
    def lab(v: int) -> str:
        return fmt.rupiah_short(v)

    reg = [
        {
            "key": r["key"],
            "value": r["value"],
            "label": lab(r["value"]),
            "prev": r.get("prev"),
            "curr": r.get("curr"),
            "prev_label": lab(r["prev"]) if r.get("prev") is not None else None,
            "curr_label": lab(r["curr"]) if r.get("curr") is not None else None,
            "mom": r.get("mom_pct"),
            "mom_label": fmt.pct(r.get("mom_pct"), 1, True) if r.get("mom_pct") is not None else "",
        }
        for r in region
    ]
    br = [{"key": r["key"], "value": r["value"], "label": f"{lab(r['value'])} · {fmt.pct(r['share_pct'])}"} for r in brand]
    cells = [
        {"region": c["region"], "brand": c["brand"], "value": c["value"], "label": fmt._dec(c["value"] / 1e6, 1), "full": fmt.rupiah(c["value"])}
        for c in heat["cells"]
    ]
    months = [r["prev_month"] for r in region[:1] if r.get("prev_month")] + [r["curr_month"] for r in region[:1] if r.get("curr_month")]
    return {
        "period": period,
        "months": [fmt.month_label(m).split()[0] for m in months],
        "region": reg,
        "brand": br,
        "heat": {"regions": heat["regions"], "brands": heat["brands"], "cells": cells},
    }

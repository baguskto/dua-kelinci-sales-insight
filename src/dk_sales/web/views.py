"""Small presentation helpers: SVG chart geometry, greeting, visit task text, calendar file (English UI)."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta, timezone
from functools import cache
from pathlib import Path

from dk_sales import fmt

WIB = timezone(timedelta(hours=7), "WIB")
# Most senior role first: the greeting names the role the person is most likely signed in for.
_ROLE_ORDER = ("head_of_sales", "head_of_region", "brand_manager", "admin")


def line_chart(prev: list[float], curr: list[float], prev_label: str, curr_label: str, width: int = 240, height: int = 104) -> dict:
    """Cumulative net sales by day: geometry for the two lines, the band under the current month, sparse
    day gridlines, and the highlight point (the day the current month passes the previous one for
    good, else its last day). ``points`` feeds the hover/focus tooltip in app.js."""
    left, right, top, bottom = 4.0, width - 4.0, 10.0, height - 18.0
    n = max(len(prev), len(curr), 2)
    hi = max(prev + curr + [1])

    def xy(i: int, v: float) -> tuple[float, float]:
        return round(left + (right - left) * i / (n - 1), 1), round(bottom - (bottom - top) * v / hi, 1)

    def line(vals: list[float]) -> str:
        return " ".join("{},{}".format(*xy(i, v)) for i, v in enumerate(vals))

    pv = [prev[min(i, len(prev) - 1)] for i in range(len(curr))] if prev else []
    hl = len(curr) - 1
    if pv and curr[-1] >= pv[-1]:
        behind = [i for i, (c, p) in enumerate(zip(curr, pv, strict=True)) if c < p]
        if behind and behind[-1] + 1 < len(curr):
            hl = behind[-1] + 1
    c = line(curr)
    band = f"{c} {xy(len(curr) - 1, 0)[0]},{bottom} {left},{bottom}" if curr else ""
    days = sorted({1, 10, 20, n})
    points = []
    for i, v in enumerate(curr):
        x, y = xy(i, v)
        points.append({"x": x, "y": y, "day": i + 1, "curr": fmt.rpm(v), "prev": fmt.rpm(pv[i]) if pv else ""})
    return {
        "width": width,
        "height": height,
        "bottom": bottom,
        "prev": line(prev),
        "curr": c,
        "band": band,
        "grid": [{"x": xy(d - 1, 0)[0], "day": d} for d in days],
        "hl": points[hl] if points else None,
        "points": points,
        "prev_label": prev_label,
        "curr_label": curr_label,
    }


def greeting(user, now: datetime) -> str:
    """'Good morning, Head of Sales' for a signed-in role; a neutral title in local mode."""
    from dk_sales.web.auth import ROLE_LABELS

    if user is None or user.auth_source == "dev":
        return "Dua Kelinci Sales"
    h = now.astimezone(WIB).hour
    part = "morning" if 4 <= h < 12 else "afternoon" if 12 <= h < 18 else "evening"
    role = next((r for r in _ROLE_ORDER if r in user.roles), None)
    return f"Good {part}, {ROLE_LABELS[role] if role else user.display_name}"


_LATE = "di luar urutan"
_SAME_NAME = re.compile(r"^Nama sama dengan (.+) di cabang (.+?):")
_RETURN = re.compile(r"^Retur (\d+) karton (.+) \((\w+)\) melebihi pembelian (\d+) karton")
_OFFER = re.compile(r"Tawarkan SKU yang laku di .+? lain: (.+)\.$")


def note_en(note: str) -> str:
    """English text for a data-quality note from analytics.outlet_notes (computed in Indonesian for the chat)."""
    if _LATE in note:
        return "Invoice number out of sequence: check the entry (new outlet or late order?)."
    if m := _SAME_NAME.match(note):
        return f"Same name as {m[1]} in branch {m[2]}: possible duplicate master record, check with admin."
    if m := _RETURN.match(note):
        return f"Return of {m[1]} cartons {m[2]} ({m[3]}) exceeds purchases of {m[4]} cartons in this period: confirm with the team."
    return note


def action_en(w) -> str:
    """English version of the suggested action for a weak outlet (same rules as analytics._action)."""
    m = _OFFER.search(w.action)
    offer = f" Offer SKUs that sell at other {w.outlet_type} outlets: {m[1]}." if m else ""
    median = f"{w.peer_median_invoices:.1f}".rstrip("0").rstrip(".")
    if w.invoices == 0:
        return f"No orders in this period. Confirm the outlet is still active and on the visit route.{offer}"
    if w.invoices <= max(1, w.peer_median_invoices * 0.5):
        return f"Rare orders ({w.invoices}, {w.outlet_type} median {median}). Schedule regular visits and check the outlet is still active.{offer}"
    if w.mom_pct is not None and w.mom_pct <= -30:
        last = fmt.mon(sorted(w.month_values)[-1])
        return f"Orders in {last} fell {abs(w.mom_pct):.0f}%. Visit this week and ask why (stock, competitor price, payment).{offer}"
    return f"Small order value.{offer or ' Offer a mixed-carton bundle.'}"


def visit_task(w, period_label: str) -> str:
    """Short visit task a manager can paste into a chat with the salesman."""
    lines = [
        f"Visit task: {w.outlet_name} ({w.outlet_id}), {w.outlet_type}, {w.branch}, {fmt.region(w.region)}.",
        f"{period_label}: net {fmt.rpm(w.net_sales_idr)}, {w.index_pct:.0f}% of the {w.outlet_type} median "
        f"({fmt.rpm(w.peer_median_idr)}); {w.invoices} orders.",
        f"Suggestion: {action_en(w)}",
    ]
    if w.notes:
        lines.append("Check data: " + " ".join(note_en(n) for n in w.notes))
    return "\n".join(lines)


def next_workday(today: date) -> date:
    d = today + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _ics_text(v: str) -> str:
    """Escape a TEXT value (RFC 5545 3.3.11): backslash, semicolon, comma and line breaks."""
    v = v.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return v.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _ics_fold(line: str) -> str:
    """Fold content lines at 75 octets without splitting a UTF-8 character (RFC 5545 3.1)."""
    out: list[str] = []
    cur = b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode())
            cur = b""
        cur += b
    out.append(cur.decode())
    return "\r\n ".join(out)


def visit_ics(w, period_label: str, day: date, stamp: datetime) -> str:
    """All-day calendar event for a visit to a weak outlet, ready to import in any calendar app."""
    desc = visit_task(w, period_label) + "\nMove the visit time in your calendar to fit the route."
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Dua Kelinci Sales//Outlet visit//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:visit-{w.outlet_id}-{day:%Y%m%d}@dua-kelinci-sales",
        f"DTSTAMP:{stamp.astimezone(UTC):%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
        f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
        "SUMMARY:" + _ics_text(f"Visit {w.outlet_name} ({w.outlet_id})"),
        "LOCATION:" + _ics_text(f"{w.branch}, {fmt.region(w.region)}"),
        "DESCRIPTION:" + _ics_text(desc),
        "CATEGORIES:Outlet visit",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_ics_fold(x) for x in lines) + "\r\n"


def waterfall(st: dict) -> list[dict]:
    """Rows for the horizontal bridge chart: previous total, one step per contribution, current total.

    x positions are percent of the track (0..100). The axis starts below the lowest running total,
    not at zero, so the steps stay readable; total bars carry a break mark and their exact number.
    """
    steps = st["bridge"]
    points = [st["prev"], st["curr"], *(s["start"] for s in steps), *(s["end"] for s in steps)]
    lo, hi = min(points), max(points)
    span = (hi - lo) or abs(hi) or 1
    axis_lo, axis_hi = lo - span * 0.18, hi + span * 0.04

    def x(v: float) -> float:
        return round((v - axis_lo) / (axis_hi - axis_lo) * 100, 2)

    rows = [{"kind": "total", "label": fmt.mon(st["prev_month"]), "value": st["prev"], "x0": 0.0, "x1": x(st["prev"]), "next": x(st["prev"])}]
    for s in steps:
        a, b = sorted((x(s["start"]), x(s["end"])))
        rows.append({"kind": "step", **s, "x0": a, "x1": max(b, a + 0.4), "from": x(s["start"]), "next": x(s["end"]), "up": s["change"] >= 0})
    rows.append({"kind": "total", "label": fmt.mon(st["curr_month"]), "value": st["curr"], "x0": 0.0, "x1": x(st["curr"]), "from": x(st["curr"]), "end": True})
    return rows


GEO = Path(__file__).parent / "static" / "geo" / "indonesia-west.json"
# Approximate centre of each sales region (lon, lat). An unknown region gets no circle.
REGION_LONLAT = {
    "Sumatera": (101.4, -0.4),
    "Jabodetabek": (106.8, -6.2),
    "Jawa Barat": (107.7, -7.0),
    "Jawa Tengah": (110.3, -7.2),
    "Jawa Timur": (112.6, -7.7),
    "Kalimantan": (113.9, -0.9),
}


@cache
def _geo() -> dict:
    return json.loads(GEO.read_text(encoding="utf-8"))


def bubble_map(regions: list[dict], rmax: float = 15.0) -> dict:
    """Circles at each region's position: area = current-month sales, color and arrow = change.

    Java's four regions sit close together, so their labels drop into a row of slots under the
    island with a leader line; the others are labelled beside their circle.
    """
    g = _geo()
    lon0, _, _, lat1 = g["bbox"]
    k = g["scale"]
    top = max([r["curr"] for r in regions] + [1])
    pts = []
    for r in regions:
        if r["key"] not in REGION_LONLAT:
            continue
        lon, lat = REGION_LONLAT[r["key"]]
        pts.append(
            {**r, "x": round((lon - lon0) * k, 1), "y": round((lat1 - lat) * k, 1), "r": round(rmax * (max(r["curr"], 0) / top) ** 0.5, 1), "java": lat < -5}
        )
    java = sorted((p for p in pts if p["java"]), key=lambda p: p["x"])
    # Java's regions sit closer together than their circles are wide: nudge them apart along the
    # island (left to right, 6 units apart), then re-centre the row on the original positions.
    if java:
        centre = sum(p["x"] for p in java) / len(java)
        for a, b in zip(java, java[1:], strict=False):
            b["x"] = max(b["x"], round(a["x"] + max(a["r"], 3) + max(b["r"], 3) + 6, 1))
        shift = centre - sum(p["x"] for p in java) / len(java)
        for p in java:
            p["x"] = round(p["x"] + shift, 1)
    label_y = g["height"] + 16
    for i, p in enumerate(java):
        p.update(lx=round(g["width"] * (0.14 + 0.72 * (i + 0.5) / len(java)), 1), ly=label_y, anchor="middle")
    for p in pts:
        if not p["java"]:
            p.update(lx=p["x"], ly=round(p["y"] + max(p["r"], 3) + 10, 1), anchor="middle")
        p["short"] = fmt.region_short(p["key"])
        p["dlabel"] = fmt.rpm_parts(p["change"], signed=True)
    return {"width": g["width"], "height": g["height"] + (34 if java else 4), "path": g["path"], "points": pts}


def day_tiles(ym: str) -> list[bool]:
    """One entry per calendar day of the month: True on a trading day (Monday to Saturday)."""
    import calendar

    y, m = (int(x) for x in ym.split("-"))
    return [calendar.weekday(y, m, d) != 6 for d in range(1, calendar.monthrange(y, m)[1] + 1)]

"""Small presentation helpers: SVG geometry, greeting, visit task text, calendar file, chart payloads."""

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
    line = " ".join(f"{x},{y}" for x, y in pts)
    area = f"{line} {pts[-1][0]},{height} {pts[0][0]},{height}"
    return {"points": line, "area": area, "last": pts[-1], "width": width, "height": height}


def spark_pair(prev: list[float], curr: list[float], width: int = 120, height: int = 32, pad: int = 2) -> dict:
    """Two running-total lines on one scale (previous month grey, current month ink) for a KPI card."""
    n = max(len(prev), len(curr), 2)
    hi = max(prev + curr + [1])

    def pts(vals: list[float]) -> str:
        return " ".join(f"{round(pad + (width - 2 * pad) * i / (n - 1), 1)},{round(height - pad - (height - 2 * pad) * v / hi, 1)}" for i, v in enumerate(vals))

    c = pts(curr)
    last = c.split()[-1] if c else f"{pad},{height - pad}"
    area = f"{c} {last.split(',')[0]},{height} {pad},{height}" if c else ""
    return {"prev": pts(prev), "curr": c, "area": area, "last": [float(v) for v in last.split(",")], "width": width, "height": height}


def bullet(value: float, median: float, width: int = 220) -> dict:
    """Geometry for a bullet bar: the outlet's value against the median of its peers."""
    top = max(value, median) * 1.1 or 1
    return {
        "width": width,
        "bar": round(max(value, 0) / top * width, 1),
        "median": round(median / top * width, 1),
    }


def bar_pct(value: float, top: float) -> float:
    """Bar length in percent of the largest value, for SVG bars with a 0..100 viewBox."""
    return round(max(value, 0) / top * 100, 1) if top > 0 else 0.0


def greeting(user, now: datetime) -> str:
    """'Selamat pagi, Head of Sales' for a signed-in role; a neutral title in local mode."""
    from dk_sales.web.auth import ROLE_LABELS

    if user is None or user.auth_source == "dev":
        return "Penjualan Dua Kelinci"
    h = now.astimezone(WIB).hour
    part = "pagi" if 4 <= h < 11 else "siang" if 11 <= h < 15 else "sore" if 15 <= h < 18 else "malam"
    role = next((r for r in _ROLE_ORDER if r in user.roles), None)
    return f"Selamat {part}, {ROLE_LABELS[role] if role else user.display_name}"


def last_month_value(w) -> tuple[str, int] | None:
    """Short label and value of the outlet's last month in the data, e.g. ('Okt', 372000)."""
    if not w.month_values:
        return None
    m = sorted(w.month_values)[-1]
    return fmt.month_label(m).split()[0], w.month_values[m]


def reason_line(w) -> str:
    """One-line reason for a weak outlet; the full reasoning stays in the visit task and the outlet page."""
    parts = [f"{fmt.pct(w.index_pct, 0)} dari median {w.outlet_type}"]
    if w.invoices == 0:
        parts.append("belum ada order")
    elif w.invoices <= max(1, w.peer_median_invoices * 0.5):
        parts.append(f"order jarang ({w.invoices} vs median {fmt._dec(w.peer_median_invoices, 1)})")
    elif w.mom_pct is not None and w.mom_pct <= -30:
        parts.append(f"bulan terakhir turun {fmt.pct(abs(w.mom_pct), 0)}")
    else:
        parts.append("nilai per order kecil")
    return "Alasan: " + ", ".join(parts) + "."


_DIAGNOSIS = re.compile(r"^(Order jarang \([^)]*\)|Order \w+ turun [^.]*|Nilai per order kecil|Belum ada order di periode ini)\.\s*")


def suggestion(w) -> str:
    """The action without its opening diagnosis, which the reason line already states."""
    rest = _DIAGNOSIS.sub("", w.action, count=1)
    return rest or w.action


def note_label(note: str) -> str:
    """Short chip text for a data-quality note; the full note is shown next to it on request."""
    if "di luar urutan" in note:
        return "Invoice di luar urutan"
    if note.startswith("Nama sama dengan"):
        return note.split(" di cabang")[0]
    if note.startswith("Retur"):
        return "Retur melebihi pembelian"
    return note.split(":")[0]


def visit_task(w, period_label: str) -> str:
    """Short visit task a manager can paste into a chat with the salesman."""
    lines = [
        f"Tugas kunjungan: {w.outlet_name} ({w.outlet_id}), {w.outlet_type}, {w.branch}, {w.region}.",
        f"{period_label}: net {fmt.rupiah_short(w.net_sales_idr)}, {fmt.pct(w.index_pct, 0)} dari median {w.outlet_type} "
        f"({fmt.rupiah_short(w.peer_median_idr)}); {w.invoices} order.",
        f"Saran: {w.action}",
    ]
    if w.notes:
        lines.append("Cek data: " + " ".join(w.notes))
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
    desc = visit_task(w, period_label) + "\nJam kunjungan bisa diubah di kalender sesuai rute."
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Penjualan Dua Kelinci//Kunjungan outlet//ID",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:kunjungan-{w.outlet_id}-{day:%Y%m%d}@penjualan-dua-kelinci",
        f"DTSTAMP:{stamp.astimezone(UTC):%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
        f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
        "SUMMARY:" + _ics_text(f"Kunjungi {w.outlet_name} ({w.outlet_id})"),
        "LOCATION:" + _ics_text(f"{w.branch}, {w.region}"),
        "DESCRIPTION:" + _ics_text(desc),
        "CATEGORIES:Kunjungan outlet",
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

    rows = [{"kind": "total", "label": fmt.month_label(st["prev_month"]).split()[0], "value": st["prev"], "x0": 0.0, "x1": x(st["prev"]), "next": x(st["prev"])}]
    for s in steps:
        a, b = sorted((x(s["start"]), x(s["end"])))
        rows.append({"kind": "step", **s, "x0": a, "x1": max(b, a + 0.4), "from": x(s["start"]), "next": x(s["end"]), "up": s["change"] >= 0})
    rows.append({"kind": "total", "label": fmt.month_label(st["curr_month"]).split()[0], "value": st["curr"], "x0": 0.0, "x1": x(st["curr"]), "from": x(st["curr"]), "end": True})
    return rows


def heat_bucket(pct: float | None) -> str:
    """Diverging color class for a region x brand change; the cell also shows the arrow and the number."""
    if pct is None or pct == 0:
        return "z"
    a = abs(pct)
    level = 3 if a >= 20 else 2 if a >= 8 else 1
    return f"{'p' if pct > 0 else 'n'}{level}"


def bars(rows: list[dict], key: str = "curr") -> dict:
    """Bar length (percent of the largest value) for each row, plus the previous-month tick."""
    top = max([r[key] for r in rows] + [r.get("prev", 0) for r in rows] + [0]) or 1
    return {r["key"]: {"w": round(max(r[key], 0) / top * 100, 1), "prev": round(max(r.get("prev", 0), 0) / top * 100, 1)} for r in rows}


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
REGION_SHORT = {"Jabodetabek": "Jabo", "Jawa Barat": "Jabar", "Jawa Tengah": "Jateng", "Jawa Timur": "Jatim"}


@cache
def _geo() -> dict:
    return json.loads(GEO.read_text(encoding="utf-8"))


def bubble_map(regions: list[dict], rmax: float = 19.0) -> dict:
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
        pts.append({**r, "x": round((lon - lon0) * k, 1), "y": round((lat1 - lat) * k, 1), "r": round(rmax * (max(r["curr"], 0) / top) ** 0.5, 1), "java": lat < -5})
    java = sorted((p for p in pts if p["java"]), key=lambda p: p["x"])
    label_y = g["height"] + 16
    for i, p in enumerate(java):
        p.update(lx=round(g["width"] * (0.14 + 0.72 * (i + 0.5) / len(java)), 1), ly=label_y, anchor="middle")
    for p in pts:
        if not p["java"]:
            p.update(lx=p["x"], ly=round(p["y"] + max(p["r"], 3) + 10, 1), anchor="middle")
        p["short"] = REGION_SHORT.get(p["key"], p["key"])
        p["dlabel"] = fmt.jt_parts(p["change"], signed=True)
    return {"width": g["width"], "height": g["height"] + (34 if java else 4), "path": g["path"], "points": pts}


def day_tiles(ym: str) -> list[bool]:
    """One entry per calendar day of the month: True on a trading day (Monday to Saturday)."""
    import calendar

    y, m = (int(x) for x in ym.split("-"))
    return [calendar.weekday(y, m, d) != 6 for d in range(1, calendar.monthrange(y, m)[1] + 1)]

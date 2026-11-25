"""Small presentation helpers: SVG geometry, greeting, visit task text, calendar file, chart payloads."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta, timezone

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


def sankey_focus(region: list[dict]) -> str | None:
    """Region highlighted by default in the region x brand flow: the largest absolute change."""
    movers = [r for r in region if r.get("change") is not None]
    if movers:
        return max(movers, key=lambda r: (abs(r["change"]), r["key"]))["key"]
    return region[0]["key"] if region else None


def chart_payload(region: list[dict], brand: list[dict], heat: dict, period: str, cumulative: list[dict] | None = None) -> dict:
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
    br = [
        {
            "key": r["key"],
            "value": r["value"],
            "label": f"{lab(r['value'])} · {fmt.pct(r['share_pct'])}",
            "mom": r.get("mom_pct"),
            "mom_label": fmt.pct(r.get("mom_pct"), 1, True) if r.get("mom_pct") is not None else "",
        }
        for r in brand
    ]
    cells = [
        {"region": c["region"], "brand": c["brand"], "value": c["value"], "label": fmt._dec(c["value"] / 1e6, 1), "full": fmt.rupiah(c["value"])}
        for c in heat["cells"]
        if c["value"] > 0
    ]
    cum = [
        {
            "month": fmt.month_label(s["month"]).split()[0],
            "month_long": fmt.month_label(s["month"], long=True).split()[0],
            "values": s["values"],
            "total_label": lab(s["total"]),
        }
        for s in (cumulative or [])
    ]
    months = [r["prev_month"] for r in region[:1] if r.get("prev_month")] + [r["curr_month"] for r in region[:1] if r.get("curr_month")]
    return {
        "period": period,
        "months": [fmt.month_label(m).split()[0] for m in months],
        "region": reg,
        "brand": br,
        "heat": {"regions": heat["regions"], "brands": heat["brands"], "cells": cells},
        "region_totals": {r["key"]: lab(r["value"]) for r in region},
        "brand_totals": {r["key"]: lab(r["value"]) for r in brand},
        "focus": sankey_focus(region),
        "cumulative": cum,
    }

"""Business metrics over the clean fact table.

All functions take a fact frame that has already been restricted to the caller's scope (see
``Scope.apply``). The UI, the API, the Telegram summary and the chat tools all go through this
module, so a number shown anywhere is computed in exactly one place.

Main measure: net sales after returns = sum(net_sales_idr) over sale and return lines.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field

import pandas as pd

from dk_sales import fmt

DIMENSIONS: dict[str, str] = {
    "region": "region",
    "brand": "brand",
    "branch": "branch",
    "outlet_type": "outlet_type",
    "salesman": "salesman",
    "sku": "sku",
    "outlet": "outlet_id",
}
DIMENSION_LABELS = {
    "region": "Region",
    "brand": "Brand",
    "branch": "Cabang",
    "outlet_type": "Tipe outlet",
    "salesman": "Salesman",
    "sku": "SKU",
    "outlet": "Outlet",
}
METRICS: dict[str, str] = {
    "net_sales": "Penjualan neto setelah retur (Rp)",
    "gross_sales": "Penjualan bruto (Rp)",
    "qty_carton": "Karton",
    "invoices": "Jumlah invoice",
}


@dataclass(frozen=True)
class Scope:
    """Row-level access. None means no restriction on that axis."""

    regions: frozenset[str] | None = None
    brands: frozenset[str] | None = None
    label: str = "Semua data"

    def apply(self, fact: pd.DataFrame) -> pd.DataFrame:
        f = fact
        if self.regions is not None:
            f = f[f["region"].isin(self.regions)]
        if self.brands is not None:
            f = f[f["brand"].isin(self.brands)]
        return f

    def allows_region(self, region: str) -> bool:
        return self.regions is None or region in self.regions

    def allows_brand(self, brand: str) -> bool:
        return self.brands is None or brand in self.brands


FULL_SCOPE = Scope()


def months(fact: pd.DataFrame) -> list[str]:
    return sorted(fact["year_month"].unique().tolist())


def valid_periods(fact: pd.DataFrame) -> list[str]:
    return ["all", *months(fact)]


def filter_period(fact: pd.DataFrame, period: str) -> pd.DataFrame:
    if period == "all":
        return fact
    return fact[fact["year_month"] == period]


def _metric_series(f: pd.DataFrame, by: str | list[str], metric: str) -> pd.Series:
    g = f.groupby(by)
    if metric == "net_sales":
        return g["net_sales_idr"].sum()
    if metric == "gross_sales":
        return f[~f["is_return"]].groupby(by)["gross_sales_idr"].sum()
    if metric == "qty_carton":
        return g["qty_carton"].sum()
    if metric == "invoices":
        return f[~f["is_return"]].groupby(by)["invoice_no"].nunique()
    raise ValueError(f"unknown metric {metric}")


def totals(fact: pd.DataFrame, period: str = "all") -> dict:
    f = filter_period(fact, period)
    sale = f[~f["is_return"]]
    ret = f[f["is_return"]]
    return {
        "period": period,
        "lines": int(len(f)),
        "net_sales_idr": int(f["net_sales_idr"].sum()),
        "net_sales_before_returns_idr": int(sale["net_sales_idr"].sum()),
        "returns_idr": int(ret["net_sales_idr"].sum()),
        "return_lines": int(len(ret)),
        "gross_sales_idr": int(sale["gross_sales_idr"].sum()),
        "discount_idr": int(sale["discount_idr"].sum()),
        "qty_carton": int(f["qty_carton"].sum()),
        "invoices": int(sale["invoice_no"].nunique()),
        "active_outlets": int(sale["outlet_id"].nunique()),
    }


def trading_days(ym: str) -> int:
    """Monday-Saturday calendar days in a year-month ("2026-10"), computed from the calendar, not the data.

    Sunday is excluded because the file has no regular Sunday sales; the one Sunday row it does
    have is the invoice-sequence anomaly tracked in docs/01-dq-audit.md (INV500799-INV500823),
    not a trading day.
    """
    year, month = (int(x) for x in ym.split("-"))
    _, days_in_month = calendar.monthrange(year, month)
    return sum(1 for d in range(1, days_in_month + 1) if calendar.weekday(year, month, d) != 6)


def mom(fact: pd.DataFrame) -> dict | None:
    """Last month vs the month before it, in total and per trading day (see ``trading_days``)."""
    ms = months(fact)
    if len(ms) < 2:
        return None
    prev, curr = ms[-2], ms[-1]
    p = int(fact.loc[fact["year_month"] == prev, "net_sales_idr"].sum())
    c = int(fact.loc[fact["year_month"] == curr, "net_sales_idr"].sum())
    prev_days, curr_days = trading_days(prev), trading_days(curr)
    per_day_prev, per_day_curr = p / prev_days, c / curr_days
    return {
        "prev_month": prev,
        "curr_month": curr,
        "prev": p,
        "curr": c,
        "change": c - p,
        "pct": _pct(c, p),
        "prev_trading_days": prev_days,
        "curr_trading_days": curr_days,
        "per_day_prev": per_day_prev,
        "per_day_curr": per_day_curr,
        "per_day_pct": _pct(per_day_curr, per_day_prev),
    }


def _pct(curr: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 2)


def breakdown(fact: pd.DataFrame, dimension: str, period: str = "all", metric: str = "net_sales") -> list[dict]:
    """One row per dimension member: value in the period, share, and last-month vs previous-month change."""
    col = DIMENSIONS[dimension]
    f = filter_period(fact, period)
    val = _metric_series(f, col, metric)
    total = val.sum()
    ms = months(fact)
    prev = curr = None
    if len(ms) >= 2:
        prev = _metric_series(fact[fact["year_month"] == ms[-2]], col, metric)
        curr = _metric_series(fact[fact["year_month"] == ms[-1]], col, metric)
    keys = sorted(set(val.index) | (set(prev.index) | set(curr.index) if prev is not None and curr is not None else set()))
    rows = []
    for k in keys:
        v = int(val.get(k, 0))
        row = {"key": k, "value": v, "share_pct": round(float(v / total * 100), 2) if total else None}
        if prev is not None and curr is not None:
            p, c = int(prev.get(k, 0)), int(curr.get(k, 0))
            row.update(prev_month=ms[-2], curr_month=ms[-1], prev=p, curr=c, change=c - p, mom_pct=_pct(c, p))
        rows.append(row)
    rows.sort(key=lambda r: (-r["value"], str(r["key"])))
    return rows


# ---------------------------------------------------------------------------
# weakest outlets


@dataclass
class WeakOutlet:
    outlet_id: str
    outlet_name: str
    outlet_type: str
    branch: str
    region: str
    net_sales_idr: int
    peer_median_idr: int
    index_pct: float
    invoices: int
    peer_median_invoices: float
    month_values: dict[str, int]
    mom_pct: float | None
    sku_count: int
    reason: str
    action: str
    notes: list[str] = field(default_factory=list)
    rank: int = 0
    last_order_date: str = ""


def weakest_outlets(fact: pd.DataFrame, dim_outlet: pd.DataFrame, period: str = "all", n: int = 5) -> list[WeakOutlet]:
    """Outlets with the lowest net sales relative to the median outlet of the same type.

    Definition (kept simple so a sales manager can check it by hand):
    1. Net sales after returns per outlet in the period. Every outlet that appears anywhere in the
       data is included, so an outlet that stopped ordering shows up with 0.
    2. Peer group = outlet type (Grosir, Minimarket, Toko Kelontong, Warung), so a Warung is not
       compared with a Grosir that buys 4x more per order.
    3. Index = outlet net / median net of its peer group, in percent. Lowest index = weakest.
    4. Only outlets below their peer median are listed, and a type needs at least 2 outlets in scope.
    5. Ties: lower net first, then outlet_id.
    Trend (last month vs previous month), order count and SKU breadth explain the result and pick
    the suggested action; they do not change the rank.
    """
    outlets = dim_outlet.set_index("outlet_id")
    ids = sorted(set(fact["outlet_id"]))
    if not ids:
        return []
    f = filter_period(fact, period)
    sale = f[~f["is_return"]]
    net = f.groupby("outlet_id")["net_sales_idr"].sum().reindex(ids, fill_value=0)
    inv = sale.groupby("outlet_id")["invoice_no"].nunique().reindex(ids, fill_value=0)
    skus = sale.groupby("outlet_id")["sku"].nunique().reindex(ids, fill_value=0)
    ms = months(fact)
    per_month = {m: fact[fact["year_month"] == m].groupby("outlet_id")["net_sales_idr"].sum().reindex(ids, fill_value=0) for m in ms}

    df = pd.DataFrame({"net": net, "inv": inv, "skus": skus})
    df["type"] = [outlets.at[o, "outlet_type"] for o in ids]
    df["peer_median"] = df.groupby("type")["net"].transform("median")
    df["peer_median_inv"] = df.groupby("type")["inv"].transform("median")
    df["index"] = (df["net"] / df["peer_median"].where(df["peer_median"] != 0)).fillna(0) * 100
    # Only outlets below the median of their peers can be "weak"; a peer group of one is not a comparison.
    df["peers"] = df.groupby("type")["net"].transform("size")
    df = df[(df["index"] < 100) & (df["peers"] >= 2)]
    df = df.reset_index(names="outlet_id").sort_values(["index", "net", "outlet_id"]).head(n)

    # SKUs that sell best among peers, used for the "offer these" action.
    sale_all = fact[~fact["is_return"]].drop(columns=["outlet_type"], errors="ignore").merge(dim_outlet[["outlet_id", "outlet_type"]], on="outlet_id")
    peer_top = {t: g.groupby("sku")["net_sales_idr"].sum().sort_values(ascending=False).index.tolist() for t, g in sale_all.groupby("outlet_type")}
    bought = sale_all.groupby("outlet_id")["sku"].agg(set).to_dict()
    last_order = sale_all.groupby("outlet_id")["date"].max().dt.strftime("%Y-%m-%d").to_dict()

    out: list[WeakOutlet] = []
    for rank, r in enumerate(df.itertuples(), start=1):
        o = r.outlet_id
        mv = {m: int(per_month[m][o]) for m in ms}
        mom_pct = _pct(mv[ms[-1]], mv[ms[-2]]) if len(ms) >= 2 else None
        typ = outlets.at[o, "outlet_type"]
        reason = (
            f"Net {fmt.rupiah_short(r.net)}, {fmt.pct(r.index, 0)} dari median {typ} "
            f"({fmt.rupiah_short(r.peer_median)}); {int(r.inv)} order vs median {fmt._dec(r.peer_median_inv, 1)}"
        )
        if mom_pct is not None and period == "all":
            reason += f"; {fmt.month_label(ms[-1]).split()[0]} vs {fmt.month_label(ms[-2]).split()[0]} {fmt.pct(mom_pct, 0, signed=True)}"
        reason += "."
        out.append(
            WeakOutlet(
                outlet_id=o,
                outlet_name=outlets.at[o, "outlet_name"],
                outlet_type=typ,
                branch=outlets.at[o, "branch"],
                region=outlets.at[o, "region"],
                net_sales_idr=int(r.net),
                peer_median_idr=int(r.peer_median),
                index_pct=round(float(r.index), 1),
                invoices=int(r.inv),
                peer_median_invoices=float(r.peer_median_inv),
                month_values=mv,
                mom_pct=mom_pct,
                sku_count=int(r.skus),
                reason=reason,
                action=_action(r, mom_pct, typ, peer_top.get(typ, []), bought.get(o, set()), ms),
                notes=outlet_notes(fact, dim_outlet, o),
                rank=rank,
                last_order_date=last_order.get(o, ""),
            )
        )
    return out


def _action(r, mom_pct, typ, peer_top, bought, ms) -> str:
    missing = [s for s in peer_top if s not in bought][:2]
    offer = f" Tawarkan SKU yang laku di {typ} lain: {', '.join(missing)}." if missing else ""
    if r.inv == 0:
        return f"Belum ada order di periode ini. Pastikan outlet masih aktif dan masuk rute kunjungan.{offer}"
    if r.inv <= max(1, r.peer_median_inv * 0.5):
        return f"Order jarang ({int(r.inv)} kali, median {typ} {fmt._dec(r.peer_median_inv, 1)}). Jadwalkan kunjungan rutin dan cek apakah outlet masih aktif.{offer}"
    if mom_pct is not None and mom_pct <= -30:
        return f"Order {fmt.month_label(ms[-1]).split()[0]} turun {fmt.pct(abs(mom_pct), 0)}. Kunjungi minggu ini dan tanyakan penyebabnya (stok, harga pesaing, pembayaran).{offer}"
    return f"Nilai per order kecil.{offer or ' Tawarkan paket karton campuran.'}"


def outlet_notes(fact: pd.DataFrame, dim_outlet: pd.DataFrame, outlet_id: str) -> list[str]:
    """Data-quality context shown next to an outlet. Context only; never a reason to hide it."""
    notes: list[str] = []
    rows = fact[fact["outlet_id"] == outlet_id]
    d = dim_outlet.set_index("outlet_id")
    if rows["dq_late_numbered_invoice"].any():
        notes.append("Nomor invoice di luar urutan: cek input, kemungkinan outlet baru atau order susulan.")
    if outlet_id in d.index and bool(d.at[outlet_id, "dq_outlet_name_shared_in_branch"]):
        name, br = d.at[outlet_id, "outlet_name"], d.at[outlet_id, "branch"]
        peers = sorted(d[(d["outlet_name"] == name) & (d["branch"] == br) & (d.index != outlet_id)].index)
        notes.append(f"Nama sama dengan {', '.join(peers)} di cabang {br}: kemungkinan data master ganda, cek ke admin.")
    for r in rows[rows["is_return"] & rows["dq_return_unmatched"]].itertuples():
        bought = int(fact[(fact["outlet_id"] == outlet_id) & (fact["sku"] == r.sku) & (~fact["is_return"]) & (fact["date"] <= r.date)]["qty_carton"].sum())
        notes.append(f"Retur {abs(r.qty_carton)} karton {r.sku} ({r.invoice_no}) melebihi pembelian {bought} karton di periode ini: konfirmasi ke tim.")
    return notes


def outlet_detail(fact: pd.DataFrame, dim_outlet: pd.DataFrame, outlet_id: str) -> dict | None:
    rows = fact[fact["outlet_id"] == outlet_id]
    if rows.empty:
        return None
    d = dim_outlet.set_index("outlet_id").loc[outlet_id]
    ms = months(fact)
    sale = rows[~rows["is_return"]]
    by_month = {m: int(rows.loc[rows["year_month"] == m, "net_sales_idr"].sum()) for m in ms}
    top_sku = sale.groupby("sku")["net_sales_idr"].sum().sort_values(ascending=False).head(3)
    return {
        "outlet_id": outlet_id,
        "outlet_name": d["outlet_name"],
        "outlet_type": d["outlet_type"],
        "branch": d["branch"],
        "region": d["region"],
        "net_sales_idr": int(rows["net_sales_idr"].sum()),
        "returns_idr": int(rows.loc[rows["is_return"], "net_sales_idr"].sum()),
        "invoices": int(sale["invoice_no"].nunique()),
        "qty_carton": int(rows["qty_carton"].sum()),
        "by_month": by_month,
        "mom_pct": _pct(by_month[ms[-1]], by_month[ms[-2]]) if len(ms) >= 2 else None,
        "salesmen": sorted(s for s in rows["salesman"].unique() if s),
        "top_skus": [{"sku": k, "net_sales_idr": int(v)} for k, v in top_sku.items()],
        "first_date": str(rows["date"].min().date()),
        "last_date": str(rows["date"].max().date()),
        "notes": outlet_notes(fact, dim_outlet, outlet_id),
    }


# ---------------------------------------------------------------------------
# dashboard helpers


def apply_filters(fact: pd.DataFrame, region: str | None = None, brand: str | None = None) -> pd.DataFrame:
    if region:
        fact = fact[fact["region"] == region]
    if brand:
        fact = fact[fact["brand"] == brand]
    return fact


def kpis(fact: pd.DataFrame, period: str = "all") -> dict:
    t = totals(fact, period)
    sale_net = t["net_sales_before_returns_idr"]
    return {
        **t,
        "avg_invoice_idr": int(round(sale_net / t["invoices"])) if t["invoices"] else 0,
        "discount_pct_of_gross": round(t["discount_idr"] / t["gross_sales_idr"] * 100, 2) if t["gross_sales_idr"] else 0.0,
    }


def weekly(fact: pd.DataFrame, period: str = "all") -> list[dict]:
    """Net sales, cartons, active outlets, invoices and discount share per week (weeks start on Monday)."""
    f = filter_period(fact, period)
    if f.empty:
        return []
    f = f.assign(week=(f["date"] - pd.to_timedelta(f["date"].dt.weekday, unit="D")).dt.strftime("%Y-%m-%d"))
    sale = f[~f["is_return"]]
    out = []
    for w, g in f.groupby("week"):
        s = sale[sale["week"] == w]
        gross = int(s["gross_sales_idr"].sum())
        out.append(
            {
                "week": w,
                "net_sales_idr": int(g["net_sales_idr"].sum()),
                "qty_carton": int(g["qty_carton"].sum()),
                "active_outlets": int(s["outlet_id"].nunique()),
                "invoices": int(s["invoice_no"].nunique()),
                "avg_invoice_idr": int(round(s["net_sales_idr"].sum() / s["invoice_no"].nunique())) if len(s) else 0,
                "discount_pct": round(int(s["discount_idr"].sum()) / gross * 100, 2) if gross else 0.0,
            }
        )
    return out


def heatmap(fact: pd.DataFrame, period: str = "all") -> dict:
    """Region x brand net sales matrix, rows and columns sorted by their totals."""
    f = filter_period(fact, period)
    if f.empty:
        return {"regions": [], "brands": [], "cells": []}
    pv = f.pivot_table(index="region", columns="brand", values="net_sales_idr", aggfunc="sum", fill_value=0)
    regions = pv.sum(axis=1).sort_values(ascending=False).index.tolist()
    brands = pv.sum(axis=0).sort_values(ascending=False).index.tolist()
    cells = [{"region": r, "brand": b, "value": int(pv.at[r, b])} for r in regions for b in brands]
    return {"regions": regions, "brands": brands, "cells": cells}


def headlines(fact: pd.DataFrame, dim_outlet: pd.DataFrame, period: str, region_rows: list[dict], brand_rows: list[dict], weak: list) -> dict:
    """One plain sentence per section, built only from computed numbers."""
    ms = months(fact)
    out: dict[str, str] = {}
    t = totals(fact, period)
    plabel = fmt.period_label(period, ms)
    mm = mom(fact) if period == "all" else None
    s = f"Penjualan {plabel} {fmt.rupiah_short(t['net_sales_idr'])}"
    if mm and mm["pct"] is not None:
        arah = "naik" if mm["change"] >= 0 else "turun"
        s += f"; {fmt.month_label(mm['curr_month'], long=True).split()[0]} {arah} {fmt.pct(abs(mm['pct']))} dari {fmt.month_label(mm['prev_month'], long=True).split()[0]}"
    out["overall"] = s + "."
    movers = [r for r in region_rows if r.get("mom_pct") is not None]
    if len(movers) > 1:
        up = max(movers, key=lambda r: r["mom_pct"])
        down = min(movers, key=lambda r: r["mom_pct"])
        m1 = fmt.month_label(up["prev_month"], long=True).split()[0]
        parts = []
        if up["mom_pct"] > 0:
            parts.append(f"{up['key']} naik {fmt.pct(up['mom_pct'])} dari {m1}, tertinggi di antara region")
        if down["mom_pct"] < 0:
            parts.append(f"{down['key']} turun {fmt.pct(abs(down['mom_pct']))}, terdalam")
        out["region"] = ("; ".join(parts) or f"Semua region bergerak di bawah {fmt.pct(up['mom_pct'])}") + "."
    elif region_rows:
        out["region"] = f"{region_rows[0]['key']} {fmt.rupiah_short(region_rows[0]['value'])} pada {plabel}."
    if brand_rows:
        top = brand_rows[0]
        s = f"{top['key']} menyumbang {fmt.pct(top['share_pct'])} penjualan {plabel}"
        movers = [r for r in brand_rows if r.get("mom_pct") is not None]
        if movers and period == "all":
            down = min(movers, key=lambda r: r["mom_pct"])
            if down["mom_pct"] < 0:
                s += f"; {down['key']} turun {fmt.pct(abs(down['mom_pct']))} dari bulan sebelumnya"
        out["brand"] = s + "."
    if weak:
        worst = max(w.index_pct for w in weak)
        s = f"{len(weak)} outlet ini di bawah {fmt.pct(worst if worst >= 10 else 10, 0)} median outlet sejenis"
        flagged = [w for w in weak if any("di luar urutan" in n for n in w.notes)]
        if flagged and len(flagged) == len(weak):
            s += "; semuanya dari invoice bernomor di luar urutan, jadi cek input ke admin sebelum kunjungan"
        elif flagged:
            s += f"; {len(flagged)} dari invoice bernomor di luar urutan"
        out["weak"] = s + "."
    return out


def cumulative(fact: pd.DataFrame, last_date: pd.Timestamp | None = None) -> list[dict]:
    """Running net sales by day of month, one series per month in the data.

    Days without a sale carry the previous total, so the line never dips. Earlier months run to their
    last calendar day; the month of ``last_date`` (default: the last date in ``fact``) stops there,
    so a filter that has no sales at the end of a month does not shorten the line.
    """
    if fact.empty:
        return []
    last_date = last_date if last_date is not None else fact["date"].max()
    daily = fact.groupby(["year_month", fact["date"].dt.day])["net_sales_idr"].sum()
    out = []
    for m in months(fact):
        start = pd.Timestamp(f"{m}-01")
        n = last_date.day if (last_date.year, last_date.month) == (start.year, start.month) else start.days_in_month
        days = daily.loc[m]
        per_day = [int(days.get(d, 0)) for d in range(1, n + 1)]
        running, total = [], 0
        for v in per_day:
            total += v
            running.append(total)
        out.append({"month": m, "values": running, "total": int(days.sum()), "daily": per_day})
    return out


def cumulative_insight(series: list[dict], mom: dict | None = None) -> str:
    """One sentence on how the last month's running total compares with the month before it."""
    if len(series) < 2:
        if series:
            s = series[-1]
            return f"{fmt.month_label(s['month'], long=True).split()[0]} {fmt.rupiah_short(s['total'])} sampai tanggal {len(s['values'])}."
        return ""
    prev, curr = series[-2], series[-1]
    p_name = fmt.month_label(prev["month"], long=True).split()[0]
    c_name = fmt.month_label(curr["month"], long=True).split()[0]
    n = len(curr["values"])
    # Compare day by day; once the previous month has ended its total stays flat.
    pv = [prev["values"][min(i, len(prev["values"]) - 1)] for i in range(n)]
    ahead = [c >= p for c, p in zip(curr["values"], pv, strict=True)]
    gap = curr["total"] - prev["total"]
    end = f"menutup bulan {fmt.rupiah_short(abs(gap))} {'di atas' if gap >= 0 else 'di bawah'} {p_name}"
    if all(ahead):
        return f"{c_name} selalu di atas {p_name} sejak tanggal 1 dan {end}."
    if not ahead[-1]:
        since = n - next(i for i, a in enumerate(reversed(ahead)) if a) if any(ahead) else 0
        start = f"sejak tanggal {since + 1}" if any(ahead) else "sepanjang bulan"
        return f"{c_name} tertinggal dari {p_name} {start} dan {end}."
    overtake = n - next(i for i, a in enumerate(reversed(ahead)) if not a) + 1
    last_common = len(prev["values"])
    if overtake > last_common:
        behind = prev["values"][-1] - curr["values"][last_common - 1]
        text = (
            f"Sampai tanggal {last_common} {c_name} masih {fmt.rupiah_short(behind)} di bawah {p_name}; "
            f"tanggal {overtake}, yang tidak ada di {p_name}, membuat {c_name} {end}."
        )
        if mom and mom.get("pct") is not None and mom.get("per_day_pct") is not None:
            text += (
                f" Kenaikan {fmt.pct(mom['pct'], 1, signed=True)} {c_name} ini datang dari satu hari kerja tambahan "
                f"({mom['curr_trading_days']} vs {mom['prev_trading_days']} hari kerja), bukan dari laju harian yang "
                f"lebih tinggi: per hari kerja {fmt.pct(mom['per_day_pct'], 1, signed=True)}."
            )
        return text
    return f"{c_name} menyalip {p_name} pada tanggal {overtake} dan bertahan di atas sampai akhir data; {c_name} {end}."


def short_headline(fact: pd.DataFrame, weak: list) -> str:
    """Header line: last month vs the month before, and how many outlets need a visit."""
    parts = []
    mm = mom(fact)
    if mm and mm["pct"] is not None:
        arah = "naik" if mm["change"] >= 0 else "turun"
        s = f"{fmt.month_label(mm['curr_month'], long=True).split()[0]} {arah} {fmt.pct(abs(mm['pct']))}"
        if mm["per_day_pct"] is not None:
            s += f" (per hari kerja {fmt.pct(mm['per_day_pct'], 1, signed=True)})"
        parts.append(s)
    else:
        parts.append(f"Penjualan {fmt.rupiah_short(int(fact['net_sales_idr'].sum()))}")
    if weak:
        parts.append(f"{len(weak)} outlet perlu dikunjungi")
    return " · ".join(parts)

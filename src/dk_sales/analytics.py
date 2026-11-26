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


def compare_months(fact: pd.DataFrame, period: str = "all") -> tuple[str, str] | None:
    """(previous, current) month the dashboard compares: the last two months, or the chosen month and the one before it."""
    ms = months(fact)
    if period == "all":
        return (ms[-2], ms[-1]) if len(ms) >= 2 else None
    if period in ms and ms.index(period) > 0:
        return ms[ms.index(period) - 1], period
    return None


def _change_rows(fact: pd.DataFrame, col: str, prev: str, curr: str) -> list[dict]:
    pv = fact[fact["year_month"].isin([prev, curr])].pivot_table(index=col, columns="year_month", values="net_sales_idr", aggfunc="sum", fill_value=0)
    rows = []
    for k in pv.index:
        p = int(pv.at[k, prev]) if prev in pv.columns else 0
        c = int(pv.at[k, curr]) if curr in pv.columns else 0
        rows.append({"key": k, "prev": p, "curr": c, "change": c - p, "pct": _pct(c, p)})
    rows.sort(key=lambda r: (-r["change"], str(r["key"])))
    return rows


def top_contributor(fact: pd.DataFrame, dim_outlet: pd.DataFrame, prev: str, curr: str) -> dict | None:
    """The outlet that moved most in the direction of the total change (the biggest driver of the delta).

    None when no outlet moved in that direction. ``share_of_change_pct`` can exceed 100: an outlet can
    add more than the total when the rest of the business fell.
    """
    rows = _change_rows(fact, "outlet_id", prev, curr)
    if not rows:
        return None
    total = sum(r["change"] for r in rows)
    sign = 1 if total >= 0 else -1
    top = max(rows, key=lambda r: (r["change"] * sign, r["key"]))
    if top["change"] * sign <= 0:
        return None
    o = top["key"]
    d = dim_outlet.set_index("outlet_id")
    rows_o = fact[(fact["outlet_id"] == o) & (~fact["is_return"])]
    curr_total = int(fact.loc[fact["year_month"] == curr, "net_sales_idr"].sum())

    def per(m: str, col: str, how: str) -> int:
        g = rows_o.loc[rows_o["year_month"] == m, col]
        return int(g.nunique() if how == "nunique" else g.sum())

    return {
        **top,
        "outlet_id": o,
        "outlet_name": d.at[o, "outlet_name"],
        "outlet_type": d.at[o, "outlet_type"],
        "branch": d.at[o, "branch"],
        "region": d.at[o, "region"],
        "invoices_prev": per(prev, "invoice_no", "nunique"),
        "invoices_curr": per(curr, "invoice_no", "nunique"),
        "cartons_prev": per(prev, "qty_carton", "sum"),
        "cartons_curr": per(curr, "qty_carton", "sum"),
        "share_of_curr_pct": round(top["curr"] / curr_total * 100, 4) if curr_total else None,
        "share_of_change_pct": round(top["change"] / total * 100, 1) if total else None,
    }


def story(fact: pd.DataFrame, dim_outlet: pd.DataFrame, period: str = "all") -> dict | None:
    """Month-on-month story for the first screen, computed for whatever file, scope and filters are loaded.

    Total change, change without the top contributing outlet, regions down N of M, a bridge
    (waterfall) from the previous to the current month by region with the top outlet split out of
    its region, and the three decisions: top-outlet spike, biggest falling region, biggest falling brand.
    The bridge steps always sum exactly to the total change.
    """
    cm = compare_months(fact, period)
    if cm is None:
        return None
    prev, curr = cm
    p = int(fact.loc[fact["year_month"] == prev, "net_sales_idr"].sum())
    c = int(fact.loc[fact["year_month"] == curr, "net_sales_idr"].sum())
    pdays, cdays = trading_days(prev), trading_days(curr)
    regions = _change_rows(fact, "region", prev, curr)
    brands = sorted(_change_rows(fact, "brand", prev, curr), key=lambda r: (-r["curr"], str(r["key"])))
    top = top_contributor(fact, dim_outlet, prev, curr)

    steps = []
    for r in regions:
        if top and r["key"] == top["region"] and len(set(fact.loc[fact["region"] == r["key"], "outlet_id"])) > 1:
            steps.append({"key": top["outlet_name"], "region": r["key"], "change": top["change"], "is_top": True, "outlet_id": top["outlet_id"]})
            steps.append({"key": r["key"], "region": r["key"], "change": r["change"] - top["change"], "is_top": False, "rest": True})
        else:
            steps.append({"key": r["key"], "region": r["key"], "change": r["change"], "is_top": bool(top and r["key"] == top["region"])})
    steps.sort(key=lambda s: (-s["change"], s["key"]))
    running = p
    for s in steps:
        s["start"], running = running, running + s["change"]
        s["end"] = running

    ex_top = None
    if top:
        ep, ec = p - top["prev"], c - top["curr"]
        ex_top = {"prev": ep, "curr": ec, "change": ec - ep, "pct": _pct(ec, ep)}
    qty = {m: int(fact.loc[fact["year_month"] == m, "qty_carton"].sum()) for m in (prev, curr)}
    down_r = [r for r in regions if r["change"] < 0]
    down_b = [b for b in brands if b["change"] < 0]
    return {
        "prev_month": prev,
        "curr_month": curr,
        "prev": p,
        "curr": c,
        "change": c - p,
        "pct": _pct(c, p),
        "prev_trading_days": pdays,
        "curr_trading_days": cdays,
        "per_day_prev": p / pdays,
        "per_day_curr": c / cdays,
        "per_day_pct": _pct(c / cdays, p / pdays),
        "cartons_prev": qty[prev],
        "cartons_curr": qty[curr],
        "top": top,
        "ex_top": ex_top,
        "regions": regions,
        "regions_down": len(down_r),
        "regions_total": len(regions),
        "brands": brands,
        "bridge": steps,
        "worst_region": min(down_r, key=lambda r: (r["change"], r["key"])) if down_r else None,
        "worst_brand": min(down_b, key=lambda r: (r["change"], r["key"])) if down_b else None,
    }


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

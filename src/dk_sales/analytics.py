"""Business metrics over the clean fact table.

All functions take a fact frame that has already been restricted to the caller's scope (see
``Scope.apply``). The UI, the API, the Telegram summary and the chat tools all go through this
module, so a number shown anywhere is computed in exactly one place.

Main measure: net sales after returns = sum(net_sales_idr) over sale and return lines.
"""

from __future__ import annotations

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


def mom(fact: pd.DataFrame) -> dict | None:
    """Last month vs the month before it."""
    ms = months(fact)
    if len(ms) < 2:
        return None
    prev, curr = ms[-2], ms[-1]
    p = int(fact.loc[fact["year_month"] == prev, "net_sales_idr"].sum())
    c = int(fact.loc[fact["year_month"] == curr, "net_sales_idr"].sum())
    return {"prev_month": prev, "curr_month": curr, "prev": p, "curr": c, "change": c - p, "pct": _pct(c, p)}


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
    keys = sorted(set(val.index) | (set(prev.index) | set(curr.index) if prev is not None else set()))
    rows = []
    for k in keys:
        v = int(val.get(k, 0))
        row = {"key": k, "value": v, "share_pct": round(float(v / total * 100), 2) if total else None}
        if prev is not None:
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
    peer_top = {
        t: g.groupby("sku")["net_sales_idr"].sum().sort_values(ascending=False).index.tolist()
        for t, g in sale_all.groupby("outlet_type")
    }
    bought = sale_all.groupby("outlet_id")["sku"].agg(set).to_dict()

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
        notes.append(
            f"Retur {abs(r.qty_carton)} karton {r.sku} ({r.invoice_no}) melebihi pembelian {bought} karton di periode ini: konfirmasi ke tim."
        )
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

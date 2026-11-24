"""Reconciliation of raw totals to clean totals, per month and region.

Bridge per (month, region label):  raw + sum(rule deltas) == clean, exact to the rupiah.
Raw totals are grouped by the region text as it appears in the file, so a relabel under DQ-03
shows up as a negative delta on the variant label and a positive delta on the canonical label.
"""

from __future__ import annotations

import pandas as pd

from dk_sales.clean import CleanResult

METRICS = ["rows", "qty_carton", "gross_sales_idr", "discount_idr", "net_sales_idr"]
INT_COLS = ["qty_carton", "gross_sales_idr", "discount_idr", "net_sales_idr"]


def _agg(frame: pd.DataFrame, region_col: str) -> pd.DataFrame:
    f = frame.copy()
    for c in INT_COLS:
        f[c] = f[c].astype("int64")
    f["month"] = f["date"].astype(str).str[:7]
    f["region_label"] = f[region_col]
    out = f.groupby(["month", "region_label"]).agg(rows=("raw_row_id", "size"), **{c: (c, "sum") for c in INT_COLS})
    return out


def bridge(result: CleanResult) -> pd.DataFrame:
    raw = result.raw.copy()
    raw["date"] = raw["date"].str.strip()
    raw_t = _agg(raw, "region")

    log = result.dq_log
    deltas: list[pd.DataFrame] = []

    # DQ-03 relabel: move totals from the variant label to the canonical label.
    relabel = log[(log["rule_id"] == "DQ-03") & (log["action"].isin(["fixed", "inferred"]))]
    if len(relabel):
        moved = raw[raw["raw_row_id"].isin(relabel["raw_row_id"])].merge(
            relabel[["raw_row_id", "after"]], on="raw_row_id"
        )
        out_ = _agg(moved, "region").mul(-1)
        in_ = _agg(moved, "after")
        d = out_.add(in_, fill_value=0)
        d["rule_id"] = "DQ-03"
        deltas.append(d)

    # Quarantined rows leave the clean set (labelled with their canonical region if relabelled).
    q = result.quarantine
    if len(q):
        qr = raw[raw["raw_row_id"].isin(q["raw_row_id"])].merge(q[["raw_row_id", "rule_id"]], on="raw_row_id")
        canon = dict(zip(relabel["raw_row_id"], relabel["after"])) if len(relabel) else {}
        qr["region_c"] = [canon.get(r, reg) for r, reg in zip(qr["raw_row_id"], qr["region"])]
        for rid, g in qr.groupby("rule_id"):
            d = _agg(g, "region_c").mul(-1)
            d["rule_id"] = rid
            deltas.append(d)

    clean = result.lines.copy()
    clean["date"] = clean["date"].dt.strftime("%Y-%m-%d")
    clean_t = _agg(clean, "region")

    deltas = [d for d in deltas if len(d)]
    rule_ids = sorted({d["rule_id"].iloc[0] for d in deltas})
    keys = raw_t.index.union(clean_t.index)
    for d in deltas:
        keys = keys.union(d.index)
    rows = []
    for k in sorted(keys):
        rec = {"month": k[0], "region_label": k[1]}
        for m in METRICS:
            rec[f"raw_{m}"] = int(raw_t[m].get(k, 0))
        for rid in rule_ids:
            ds = [d for d in deltas if d["rule_id"].iloc[0] == rid]
            for m in METRICS:
                rec[f"{rid}_{m}"] = int(sum(d[m].get(k, 0) for d in ds))
        for m in METRICS:
            rec[f"clean_{m}"] = int(clean_t[m].get(k, 0))
        rows.append(rec)
    out = pd.DataFrame(rows)
    for m in METRICS:
        out[f"diff_{m}"] = out[f"raw_{m}"] + sum(out[f"{rid}_{m}"] for rid in rule_ids) - out[f"clean_{m}"]
    return out


def split_sales_returns(lines: pd.DataFrame) -> pd.DataFrame:
    f = lines.copy()
    f["month"] = f["date"].dt.strftime("%Y-%m")
    f["kind"] = f["is_return"].map({True: "retur", False: "penjualan"})
    g = f.groupby(["month", "region", "kind"]).agg(rows=("line_id" if "line_id" in f else "raw_row_id", "size"), **{c: (c, "sum") for c in INT_COLS})
    return g.reset_index()


def is_balanced(b: pd.DataFrame) -> bool:
    return bool((b[[c for c in b.columns if c.startswith("diff_")]] == 0).all().all())

"""Profiling of the raw file as it is, before any cleaning."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from dk_sales import config


def _infer_type(s: pd.Series) -> str:
    v = s[s != ""]
    if v.empty:
        return "empty"
    if v.str.fullmatch(r"-?\d+").all():
        return "integer"
    if v.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        return "date"
    return "string"


def _counts(s: pd.Series) -> dict[str, int]:
    vc = s.value_counts()
    return {str(k): int(v) for k, v in sorted(vc.items(), key=lambda kv: (-kv[1], str(kv[0])))}


def _describe(values: pd.Series) -> dict:
    d = values.describe(percentiles=[0.25, 0.5, 0.75])
    return {k: (int(v) if float(v).is_integer() else round(float(v), 2)) for k, v in d.items()}


def profile(raw: pd.DataFrame, sha256: str, source_name: str) -> dict:
    df = raw[config.RAW_COLUMNS].astype(str)
    out: dict = {
        "source": source_name,
        "sha256": sha256,
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "column_names": list(df.columns),
    }
    cols = {}
    for c in config.RAW_COLUMNS:
        s = df[c]
        info: dict[str, Any] = {
            "inferred_type": _infer_type(s),
            "blank": int((s.str.strip() == "").sum()),
            "leading_trailing_space": int((s != s.str.strip()).sum()),
            "distinct": int(s.nunique()),
            "distinct_after_trim_casefold": int(s.str.strip().str.casefold().nunique()),
        }
        if info["inferred_type"] == "integer":
            info["stats"] = _describe(s[s != ""].astype("int64"))
            info["negative"] = int((s[s != ""].astype("int64") < 0).sum())
            info["zero"] = int((s[s != ""].astype("int64") == 0).sum())
        if info["inferred_type"] == "date":
            info["min"] = s.min()
            info["max"] = s.max()
        if c not in ("invoice_no",) and info["distinct"] <= 60:
            info["values"] = _counts(s)
        cols[c] = info
    out["column_profile"] = cols

    d = pd.to_datetime(df["date"], errors="coerce")
    out["date_range"] = {"min": str(d.min().date()), "max": str(d.max().date())}
    days = pd.date_range(d.min(), d.max(), freq="D")
    present = set(d)
    out["calendar"] = {
        "days_in_range": len(days),
        "days_with_rows": len(present),
        "days_without_rows": [f"{x.date()} ({config.DAY_NAMES_ID[x.weekday()]})" for x in days if x not in present],
        "rows_per_weekday": {config.DAY_NAMES_ID[k]: int(v) for k, v in sorted(d.dt.day_of_week.value_counts().items())},
    }
    out["rows_per_day"] = {str(k.date()): int(v) for k, v in sorted(d.value_counts().items())}
    out["rows_per_month"] = {k: int(v) for k, v in sorted(df["date"].str[:7].value_counts().items())}
    for key, col in [
        ("rows_per_region_raw", "region"),
        ("rows_per_branch", "branch"),
        ("rows_per_outlet", "outlet_id"),
        ("rows_per_salesman", "salesman"),
        ("rows_per_brand", "brand"),
        ("rows_per_sku", "sku"),
        ("rows_per_outlet_type", "outlet_type"),
    ]:
        out[key] = _counts(df[col].replace("", "(kosong)"))

    num = df.copy()
    for c in config.INT_COLUMNS:
        num[c] = pd.to_numeric(num[c], errors="coerce")
    inv = num.groupby("invoice_no").agg(
        lines=("sku", "size"),
        qty=("qty_carton", "sum"),
        net=("net_sales_idr", "sum"),
        distinct_dates=("date", "nunique"),
    )
    sale_ids = df.loc[df["invoice_no"].str.fullmatch(config.SALE_PREFIX + r"\d+"), "invoice_no"]
    inv_nums = sorted(set(sale_ids.str[len(config.SALE_PREFIX) :].astype(int)))
    out["invoices"] = {
        "distinct_invoices": int(len(inv)),
        "by_prefix": _counts(df.drop_duplicates("invoice_no")["invoice_no"].str[:3]),
        "lines_per_invoice": {str(k): int(v) for k, v in sorted(inv["lines"].value_counts().items())},
        "qty_per_invoice": _describe(inv["qty"]),
        "net_per_invoice_idr": _describe(inv["net"]),
        "sale_number_min": int(min(inv_nums)) if inv_nums else None,
        "sale_number_max": int(max(inv_nums)) if inv_nums else None,
        "sale_number_gaps": [n for n in range(min(inv_nums), max(inv_nums) + 1) if n not in set(inv_nums)] if inv_nums else [],
        "invoices_with_multiple_dates": int((inv["distinct_dates"] > 1).sum()),
    }
    out["qty_by_outlet_type"] = {k: _describe(g["qty_carton"]) for k, g in num.groupby("outlet_type")}
    disc_rate = (num["discount_idr"] / num["gross_sales_idr"] * 100).round(2)
    out["discount_rate_pct"] = {str(k): int(v) for k, v in sorted(disc_rate.value_counts().items())}
    out["totals_raw"] = {c: int(num[c].sum()) for c in config.INT_COLUMNS}
    out["price_per_sku"] = {sku: sorted(int(p) for p in g["price_per_carton_idr"].unique()) for sku, g in num.groupby("sku")}
    out["brand_per_sku"] = {sku: sorted(g["brand"].unique()) for sku, g in df.groupby("sku")}
    out["exact_duplicate_rows"] = int(df.duplicated().sum())
    out["file_is_sorted_by_date"] = bool(df["date"].is_monotonic_increasing)
    return out


def _table(d: dict, k: str, v: str, limit: int | None = None) -> str:
    items = list(d.items())[:limit] if limit else list(d.items())
    lines = [f"| {k} | {v} |", "|---|---:|"]
    lines += [f"| {_md(a)} | {b} |" for a, b in items]
    return "\n".join(lines)


def _md(value: object) -> str:
    text = str(value)
    if text != text.strip():
        text = f"`{text!r}`"
    return re.sub(r"\|", r"\\|", text)


def _rp(n: int) -> str:
    return f"Rp{n:,.0f}".replace(",", ".")


def to_markdown(p: dict) -> str:
    cp = p["column_profile"]
    s: list[str] = []
    s.append("# 01 Profiling data mentah\n")
    s.append(
        "Dokumen ini dibuat otomatis oleh `make data` dari `data/raw/sales_raw.csv` sebelum cleaning. Angka mentah lengkap ada di `docs/01-profiling.json`.\n"
    )
    s.append("## Ringkasan\n")
    s.append(f"- File: `{p['source']}`, sha256 `{p['sha256']}`")
    s.append(f"- {p['rows']} baris, {p['columns']} kolom, tanggal {p['date_range']['min']} s.d. {p['date_range']['max']}")
    s.append(f"- {p['invoices']['distinct_invoices']} nomor dokumen: {', '.join(f'{k} {v}' for k, v in p['invoices']['by_prefix'].items())}")
    t = p["totals_raw"]
    s.append(f"- Total mentah: {t['qty_carton']} karton, gross {_rp(t['gross_sales_idr'])}, diskon {_rp(t['discount_idr'])}, net {_rp(t['net_sales_idr'])}")
    s.append(f"- Baris duplikat persis: {p['exact_duplicate_rows']}. File terurut menurut tanggal: {'ya' if p['file_is_sorted_by_date'] else 'tidak'}.\n")

    s.append("## Skema dan tipe\n")
    s.append("| Kolom | Tipe terbaca | Kosong | Spasi tepi | Nilai unik | Unik setelah trim+casefold | Rentang |")
    s.append("|---|---|---:|---:|---:|---:|---|")
    for c, i in cp.items():
        rng = ""
        if "stats" in i:
            rng = f"{i['stats']['min']} s.d. {i['stats']['max']}"
        elif "min" in i:
            rng = f"{i['min']} s.d. {i['max']}"
        s.append(
            f"| {c} | {i['inferred_type']} | {i['blank']} | {i['leading_trailing_space']} | {i['distinct']} | {i['distinct_after_trim_casefold']} | {rng} |"
        )
    s.append("")
    s.append("## Nilai per kolom kategori\n")
    for c in ["region", "outlet_type", "brand", "qty_carton"]:
        s.append(f"### {c}\n")
        s.append(_table(cp[c]["values"], c, "baris"))
        s.append("")
    s.append("### sku dan harga per karton\n")
    s.append("| SKU | Brand | Harga per karton | Baris |")
    s.append("|---|---|---:|---:|")
    for sku, n in p["rows_per_sku"].items():
        s.append(f"| {sku} | {', '.join(p['brand_per_sku'][sku])} | {', '.join(_rp(x) for x in p['price_per_sku'][sku])} | {n} |")
    s.append("")
    s.append("## Kalender\n")
    cal = p["calendar"]
    s.append(f"{cal['days_with_rows']} dari {cal['days_in_range']} hari punya transaksi. Hari tanpa transaksi: {', '.join(cal['days_without_rows'])}.\n")
    s.append(_table(cal["rows_per_weekday"], "Hari", "baris"))
    s.append("")
    s.append(_table(p["rows_per_month"], "Bulan", "baris"))
    s.append("")
    s.append("<details><summary>Baris per tanggal</summary>\n")
    s.append(_table(p["rows_per_day"], "Tanggal", "baris"))
    s.append("\n</details>\n")
    s.append("## Baris per region (teks mentah), cabang, tipe outlet\n")
    s.append(_table(p["rows_per_region_raw"], "region (mentah)", "baris"))
    s.append("")
    s.append(_table(p["rows_per_branch"], "Cabang", "baris"))
    s.append("")
    s.append(_table(p["rows_per_outlet_type"], "Tipe outlet", "baris"))
    s.append("")
    s.append("## Baris per salesman dan outlet\n")
    s.append(_table(p["rows_per_salesman"], "Salesman", "baris"))
    s.append("")
    s.append("<details><summary>Baris per outlet_id</summary>\n")
    s.append(_table(p["rows_per_outlet"], "outlet_id", "baris"))
    s.append("\n</details>\n")
    s.append("## Invoice\n")
    iv = p["invoices"]
    s.append(_table(iv["lines_per_invoice"], "Baris per invoice", "invoice"))
    s.append("")
    s.append(f"- Nomor INV: {iv['sale_number_min']} s.d. {iv['sale_number_max']}, celah nomor: {iv['sale_number_gaps'] or 'tidak ada'}")
    s.append(f"- Invoice dengan lebih dari satu tanggal: {iv['invoices_with_multiple_dates']}")
    q = iv["qty_per_invoice"]
    n = iv["net_per_invoice_idr"]
    s.append(f"- Karton per invoice: median {q['50%']}, rata-rata {q['mean']}, maks {q['max']}")
    s.append(f"- Net per invoice: median {_rp(n['50%'])}, rata-rata {_rp(int(n['mean']))}, maks {_rp(n['max'])}\n")
    s.append("## Qty per tipe outlet\n")
    s.append("| Tipe outlet | Baris | Min | Median | Maks | Rata-rata |")
    s.append("|---|---:|---:|---:|---:|---:|")
    for k, d in p["qty_by_outlet_type"].items():
        s.append(f"| {k} | {d['count']} | {d['min']} | {d['50%']} | {d['max']} | {d['mean']} |")
    s.append("")
    s.append("Grosir membeli 4 sampai 15 karton per baris; tipe lain 1 sampai 4 karton. Perbandingan antar outlet harus memperhitungkan tipe outlet.\n")
    s.append("## Persentase diskon per baris (diskon / gross)\n")
    s.append(_table(p["discount_rate_pct"], "Diskon %", "baris"))
    s.append("")
    s.append(
        "Nilai seperti 1,99% atau 3,01% bukan tarif tersendiri. Semua 1.891 baris cocok dengan 0, 2, 3 atau 5 persen "
        "dari gross yang dibulatkan ke Rp100 terdekat (lihat DQ-16).\n"
    )
    return "\n".join(s) + "\n"

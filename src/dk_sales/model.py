"""Star-schema model built from the cleaned lines."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

from dk_sales import config
from dk_sales.rules import FLAG_COLUMNS


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def pack_size_g(sku: str) -> int | None:
    m = re.search(r"(\d+)\s*g\b", sku, flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def load_holidays(path=None) -> dict[date, str]:
    path = path or (config.REFERENCE_DIR / "holidays_id.csv")
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, comment="#")
    return {date.fromisoformat(r.date): r.name for r in df.itertuples()}


def build_dim_date(lines: pd.DataFrame, period: tuple[str, str], holidays: dict[date, str]) -> pd.DataFrame:
    start = min(pd.Timestamp(period[0]), lines["date"].min()) if len(lines) else pd.Timestamp(period[0])
    end = max(pd.Timestamp(period[1]), lines["date"].max()) if len(lines) else pd.Timestamp(period[1])
    days = pd.date_range(start, end, freq="D")
    sales_days = set(lines.loc[~lines["is_return"], "date"])
    rows = []
    for d in days:
        iso = d.isocalendar()
        hol = holidays.get(d.date(), "")
        rows.append(
            {
                "date_key": int(d.strftime("%Y%m%d")),
                "date": d,
                "day_of_week": d.weekday() + 1,
                "day_name_id": config.DAY_NAMES_ID[d.weekday()],
                "iso_year": int(iso.year),
                "iso_week": int(iso.week),
                "week_start": (d - pd.Timedelta(days=d.weekday())),
                "month": d.month,
                "month_name_id": config.MONTH_NAMES_ID[d.month - 1],
                "year_month": d.strftime("%Y-%m"),
                "is_sunday": d.weekday() == 6,
                "is_holiday": bool(hol),
                "holiday_name": hol,
                "is_trading_day": d.weekday() < 6 and not hol,
                "has_sales": d in sales_days,
            }
        )
    return pd.DataFrame(rows)


def build_dims(lines: pd.DataFrame, period: tuple[str, str], holidays: dict[date, str]) -> dict[str, pd.DataFrame]:
    geo = (
        lines.groupby(["region", "branch"])
        .agg(n_outlets=("outlet_id", "nunique"), n_salesmen=("salesman", lambda s: s[s != ""].nunique()))
        .reset_index()
        .sort_values(["region", "branch"])
    )
    geo.insert(0, "geo_key", geo["branch"].map(slug))

    product = (
        lines.groupby(["brand", "sku"])
        .agg(list_price_per_carton_idr=("price_per_carton_idr", lambda s: int(s.mode().min())))
        .reset_index()
        .sort_values(["brand", "sku"])
    )
    product.insert(0, "sku_code", product["sku"].map(slug))
    product["pack_size_g"] = product["sku"].map(pack_size_g).astype("Int64")
    product = product[["sku_code", "brand", "sku", "pack_size_g", "list_price_per_carton_idr"]]

    named = lines[lines["salesman"] != ""]
    salesman = (
        named.groupby("salesman")
        .agg(
            branch=("branch", lambda s: s.mode().min()),
            region=("region", lambda s: s.mode().min()),
            n_outlets=("outlet_id", "nunique"),
            n_invoices=("invoice_no", "nunique"),
        )
        .reset_index()
        .sort_values("salesman")
    )
    salesman.insert(0, "salesman_code", salesman["salesman"].map(slug))

    def first_mode(s: pd.Series):
        return s.mode().min()

    outlet = (
        lines.groupby("outlet_id")
        .agg(
            outlet_name=("outlet_name", first_mode),
            outlet_type=("outlet_type", first_mode),
            branch=("branch", first_mode),
            region=("region", first_mode),
            first_date=("date", "min"),
            last_date=("date", "max"),
            n_invoices=("invoice_no", "nunique"),
            n_salesmen=("salesman", lambda s: s[s != ""].nunique()),
            dq_suspect_outlet=("dq_suspect_outlet", "any"),
            dq_outlet_name_shared_in_branch=("dq_outlet_name_shared_in_branch", "any"),
        )
        .reset_index()
        .sort_values("outlet_id")
    )
    outlet["name_shared_count"] = outlet.groupby("outlet_name")["outlet_id"].transform("count").astype("int64")

    return {
        "dim_date": build_dim_date(lines, period, holidays),
        "dim_geo": geo.reset_index(drop=True),
        "dim_product": product.reset_index(drop=True),
        "dim_salesman": salesman.reset_index(drop=True),
        "dim_outlet": outlet.reset_index(drop=True),
    }


FACT_COLUMNS = [
    "line_id",
    "date_key",
    "date",
    "year_month",
    "invoice_no",
    "document_type",
    "is_return",
    "outlet_id",
    "geo_key",
    "region",
    "branch",
    "salesman_code",
    "salesman",
    "sku_code",
    "brand",
    "sku",
    "qty_carton",
    "price_per_carton_idr",
    "gross_sales_idr",
    "discount_idr",
    "net_sales_idr",
    "discount_rate_pct",
    *FLAG_COLUMNS,
    "dq_flags",
]


def build_fact(lines: pd.DataFrame) -> pd.DataFrame:
    f = lines.copy()
    f["line_id"] = f["raw_row_id"].astype("int64")
    f["date_key"] = f["date"].dt.strftime("%Y%m%d").astype("int64")
    f["year_month"] = f["date"].dt.strftime("%Y-%m")
    f["document_type"] = f["is_return"].map({True: "return", False: "sale"})
    f["geo_key"] = f["branch"].map(slug)
    f["salesman_code"] = f["salesman"].map(lambda s: slug(s) if s else "")
    f["sku_code"] = f["sku"].map(slug)
    gross = f["gross_sales_idr"].where(f["gross_sales_idr"] != 0)
    f["discount_rate_pct"] = (f["discount_idr"] / gross * 100).round(2).fillna(0.0)
    return f[FACT_COLUMNS].sort_values("line_id").reset_index(drop=True)

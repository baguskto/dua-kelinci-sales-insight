"""Data contracts (pandera) for the raw input and the modelled outputs."""

from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

from dk_sales import config
from dk_sales.rules import FLAG_COLUMNS

CONTRACT_VERSION = "1.0.0"

_text = Column(str, nullable=False)

# Fact columns that carry the 15 raw fields; two fact rows equal on all of them are an exact duplicate.
_FACT_BUSINESS_COLUMNS = [
    "date",
    "invoice_no",
    "region",
    "branch",
    "outlet_id",
    "salesman",
    "brand",
    "sku",
    "qty_carton",
    "price_per_carton_idr",
    "gross_sales_idr",
    "discount_idr",
    "net_sales_idr",
]

# Raw input: every column is text; the contract only checks presence, order-free names and that the
# fields needed to parse are non-empty. Value-level problems are handled by DQ rules, not by rejection.
RAW_SCHEMA = DataFrameSchema(
    {c: Column(str, nullable=False, required=True) for c in config.RAW_COLUMNS},
    strict=False,
    coerce=False,
    name="sales_raw",
)

FACT_SCHEMA = DataFrameSchema(
    {
        "line_id": Column(int, Check.ge(1), unique=True),
        "date_key": Column(int, Check.in_range(19000101, 29991231)),
        "date": Column("datetime64[ns]"),
        "year_month": Column(str, Check.str_matches(r"^\d{4}-\d{2}$")),
        "invoice_no": Column(str, Check.str_matches(config.INVOICE_PATTERN)),
        "document_type": Column(str, Check.isin(["sale", "return"])),
        "is_return": Column(bool),
        "outlet_id": _text,
        "geo_key": _text,
        "region": Column(str, Check.isin(config.CANONICAL_REGIONS)),
        "branch": _text,
        "salesman_code": Column(str),
        "salesman": Column(str),
        "sku_code": _text,
        "brand": _text,
        "sku": _text,
        "qty_carton": Column(int, Check.ne(0)),
        "price_per_carton_idr": Column(int, Check.gt(0)),
        "gross_sales_idr": Column(int),
        "discount_idr": Column(int, Check.ge(0)),
        "net_sales_idr": Column(int),
        "discount_rate_pct": Column(float, Check.in_range(0, 100)),
        **{c: Column(bool) for c in FLAG_COLUMNS},
        "dq_flags": Column(str),
    },
    checks=[
        Check(lambda df: (df["gross_sales_idr"] == df["qty_carton"] * df["price_per_carton_idr"]).all(), name="gross_eq_qty_x_price"),
        Check(lambda df: (df["net_sales_idr"] == df["gross_sales_idr"] - df["discount_idr"]).all(), name="net_eq_gross_minus_discount"),
        Check(lambda df: (df["is_return"] == (df["qty_carton"] < 0)).all(), name="return_iff_negative_qty"),
        Check(lambda df: (df["is_return"] == (df["document_type"] == "return")).all(), name="document_type_matches_flag"),
        Check(lambda df: ~df.duplicated(subset=_FACT_BUSINESS_COLUMNS).any(), name="no_exact_duplicates"),
    ],
    strict=True,
    name="fact_sales_line",
)

DIM_SCHEMAS: dict[str, DataFrameSchema] = {
    "dim_outlet": DataFrameSchema(
        {
            "outlet_id": Column(str, unique=True),
            "outlet_name": _text,
            "outlet_type": Column(str, Check.isin(config.OUTLET_TYPES)),
            "branch": _text,
            "region": Column(str, Check.isin(config.CANONICAL_REGIONS)),
        },
        strict=False,
        name="dim_outlet",
    ),
    "dim_product": DataFrameSchema(
        {
            "sku_code": Column(str, unique=True),
            "sku": Column(str, unique=True),
            "brand": _text,
            "pack_size_g": Column("Int64", Check.gt(0), nullable=True),
            "list_price_per_carton_idr": Column(int, Check.gt(0)),
        },
        strict=True,
        name="dim_product",
    ),
    "dim_salesman": DataFrameSchema(
        {"salesman_code": Column(str, unique=True), "salesman": Column(str, unique=True), "branch": _text},
        strict=False,
        name="dim_salesman",
    ),
    "dim_geo": DataFrameSchema(
        {"geo_key": Column(str, unique=True), "branch": Column(str, unique=True), "region": Column(str, Check.isin(config.CANONICAL_REGIONS))},
        strict=False,
        name="dim_geo",
    ),
    "dim_date": DataFrameSchema(
        {"date_key": Column(int, unique=True), "day_name_id": Column(str, Check.isin(config.DAY_NAMES_ID))},
        strict=False,
        name="dim_date",
    ),
}


def validate_outputs(tables: dict) -> None:
    """Raise pandera.errors.SchemaError(s) when an output table breaks its contract."""
    FACT_SCHEMA.validate(tables["fact_sales_line"], lazy=True)
    for name, schema in DIM_SCHEMAS.items():
        schema.validate(tables[name], lazy=True)
    fact = tables["fact_sales_line"]
    # Referential integrity: every fact key exists in its dimension.
    for col, dim, key in [
        ("outlet_id", "dim_outlet", "outlet_id"),
        ("sku_code", "dim_product", "sku_code"),
        ("geo_key", "dim_geo", "geo_key"),
        ("date_key", "dim_date", "date_key"),
    ]:
        missing = set(fact[col]) - set(tables[dim][key])
        if missing:
            raise pa.errors.SchemaError(FACT_SCHEMA, fact, f"{col} not in {dim}: {sorted(missing)[:5]}")
    named = set(fact.loc[fact["salesman_code"] != "", "salesman_code"])
    if named - set(tables["dim_salesman"]["salesman_code"]):
        raise pa.errors.SchemaError(FACT_SCHEMA, fact, "salesman_code not in dim_salesman")


def contract_document(raw_sha256: str) -> dict:
    """Machine-readable contract, written to contracts/sales_data_contract.json."""
    from dk_sales.rules import RULES

    return {
        "contract_version": CONTRACT_VERSION,
        "dataset": "dua_kelinci_sales_lines",
        "owner": "Bagus Kurnianto Labamu",
        "input": {
            "path": "data/raw/sales_raw.csv",
            "sha256": raw_sha256,
            "immutable": True,
            "format": "CSV, UTF-8 (BOM, UTF-16 dan cp1252 juga dibaca), pemisah koma/titik koma/tab terdeteksi otomatis; .xlsx sheet pertama",
            "grain": "satu baris produk (SKU) pada satu dokumen penjualan atau retur",
            "columns": [
                {"name": c, "type": "integer" if c in config.INT_COLUMNS else ("date" if c == "date" else "string"), "required": True, "blank_allowed": c == "salesman"}
                for c in config.RAW_COLUMNS
            ],
            "invoice_pattern": config.INVOICE_PATTERN,
            "canonical_regions": config.CANONICAL_REGIONS,
            "region_aliases": config.REGION_ALIASES,
            "outlet_types": config.OUTLET_TYPES,
            "discount_rates_pct": config.DISCOUNT_RATES_PCT,
            "discount_rounding_idr": config.DISCOUNT_ROUNDING_IDR,
            "expected_period": [config.PERIOD_START, config.PERIOD_END],
        },
        "outputs": {
            "fact_sales_line": {"primary_key": "line_id", "columns": list(FACT_SCHEMA.columns)},
            **{name: {"columns": list(s.columns)} for name, s in DIM_SCHEMAS.items()},
        },
        "guarantees": [
            "rows_in == rows_clean + rows_quarantined",
            "gross_sales_idr == qty_carton * price_per_carton_idr pada setiap baris fact",
            "net_sales_idr == gross_sales_idr - discount_idr pada setiap baris fact",
            "is_return == (qty_carton < 0)",
            "region hanya berisi 6 nama baku",
            "rekonsiliasi mentah ke bersih per bulan dan region selisih 0 rupiah",
            "dua kali menjalankan pipeline menghasilkan file yang sama (hash sama)",
        ],
        "rules": [
            {"id": r.rule_id, "title": r.title, "severity": r.severity, "level": r.level, "action": r.action, "flag_column": r.flag_column}
            for r in RULES
        ],
    }

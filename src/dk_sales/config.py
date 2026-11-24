"""Static configuration: column specs, canonical values, paths."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "data" / "raw" / "sales_raw.csv"
REFERENCE_DIR = ROOT / "data" / "reference"
PROCESSED_DIR = ROOT / "data" / "processed"
DOCS_DIR = ROOT / "docs"
CONTRACTS_DIR = ROOT / "contracts"

# sha256 of the immutable raw input committed in a3439dc.
RAW_SHA256 = "48b9f90ddaa91e0033ada4feb3cb47a8aaf490774165d266223be1da34e6741f"

RAW_COLUMNS: list[str] = [
    "date",
    "invoice_no",
    "region",
    "branch",
    "outlet_id",
    "outlet_name",
    "outlet_type",
    "salesman",
    "brand",
    "sku",
    "qty_carton",
    "price_per_carton_idr",
    "gross_sales_idr",
    "discount_idr",
    "net_sales_idr",
]
TEXT_COLUMNS: list[str] = [
    "invoice_no",
    "region",
    "branch",
    "outlet_id",
    "outlet_name",
    "outlet_type",
    "salesman",
    "brand",
    "sku",
]
INT_COLUMNS: list[str] = [
    "qty_carton",
    "price_per_carton_idr",
    "gross_sales_idr",
    "discount_idr",
    "net_sales_idr",
]
# Fields that describe the invoice header and must be identical on every line of one invoice.
INVOICE_HEADER_COLUMNS: list[str] = [
    "date",
    "region",
    "branch",
    "outlet_id",
    "outlet_name",
    "outlet_type",
    "salesman",
]
REQUIRED_NON_BLANK: list[str] = [c for c in RAW_COLUMNS if c != "salesman"]

CANONICAL_REGIONS: list[str] = [
    "Jabodetabek",
    "Jawa Barat",
    "Jawa Tengah",
    "Jawa Timur",
    "Sumatera",
    "Kalimantan",
]
# Common abbreviations seen in field exports, keyed by upper-case form.
REGION_ALIASES: dict[str, str] = {
    "JABAR": "Jawa Barat",
    "JATENG": "Jawa Tengah",
    "JATIM": "Jawa Timur",
    "SUMATRA": "Sumatera",
}
OUTLET_TYPES: list[str] = ["Grosir", "Minimarket", "Toko Kelontong", "Warung"]

# Allowed discount rates in percent; discount_idr = round(gross * rate / 100, nearest 100).
DISCOUNT_RATES_PCT: list[int] = [0, 2, 3, 5]
DISCOUNT_ROUNDING_IDR = 100

INVOICE_PATTERN = r"^(INV|RTR)\d{6}$"
SALE_PREFIX = "INV"
RETURN_PREFIX = "RTR"

PERIOD_START = "2026-09-01"
PERIOD_END = "2026-10-31"

DAY_NAMES_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTH_NAMES_ID = [
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
]

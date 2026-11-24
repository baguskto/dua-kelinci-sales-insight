"""Helpers to build small raw frames for rule tests."""

from __future__ import annotations

import pandas as pd

from dk_sales import config

BASE_ROW = {
    "date": "2026-09-01",
    "invoice_no": "INV500001",
    "region": "Jabodetabek",
    "branch": "Jakarta Barat",
    "outlet_id": "OUT1",
    "outlet_name": "Toko A",
    "outlet_type": "Warung",
    "salesman": "Andi",
    "brand": "Sukro",
    "sku": "Sukro Pedas 100g",
    "qty_carton": "2",
    "price_per_carton_idr": "186000",
    "gross_sales_idr": "372000",
    "discount_idr": "0",
    "net_sales_idr": "372000",
}


def rows(*overrides: dict) -> pd.DataFrame:
    """Build an all-string raw frame from BASE_ROW plus per-row overrides."""
    out = []
    for o in overrides:
        r = dict(BASE_ROW)
        r.update({k: str(v) for k, v in o.items()})
        out.append(r)
    return pd.DataFrame(out, columns=config.RAW_COLUMNS)

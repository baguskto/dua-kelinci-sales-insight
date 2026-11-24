from __future__ import annotations

import io

import pandas as pd
import pytest

from dk_sales import config
from dk_sales.clean import clean
from dk_sales.io import InputError, read_csv_bytes, read_upload

RAW = config.RAW_PATH.read_bytes()


def test_semicolon_and_bom():
    text = RAW.decode().replace(",", ";")
    df, meta = read_csv_bytes(b"\xef\xbb\xbf" + text.encode())
    assert meta["delimiter"] == ";" and meta["encoding"] == "utf-8-sig"
    assert len(df) == 1891 and list(df.columns) == config.RAW_COLUMNS


def test_cp1252_and_utf16():
    sample = "\n".join(RAW.decode().splitlines()[:5]).replace("Grosir", "Grösir")
    df, meta = read_csv_bytes(sample.encode("cp1252"))
    assert meta["encoding"] == "cp1252" and "Grösir" in " ".join(df["outlet_name"])
    df2, meta2 = read_csv_bytes(sample.encode("utf-16"))
    assert meta2["encoding"] == "utf-16" and len(df2) == 4


def test_empty_and_binary_rejected():
    with pytest.raises(InputError):
        read_csv_bytes(b"   ")
    with pytest.raises(InputError):
        read_csv_bytes(b"\x00\x01\x02\xff\xfe\x00" * 50)


def test_xlsx_roundtrip_gives_same_clean_result():
    df = pd.read_csv(config.RAW_PATH, dtype=str, keep_default_na=False)
    typed = df.copy()
    typed["date"] = pd.to_datetime(typed["date"])
    for c in config.INT_COLUMNS:
        typed[c] = typed[c].astype(int)
    buf = io.BytesIO()
    typed.to_excel(buf, index=False)
    x, meta = read_upload("sales.xlsx", buf.getvalue())
    assert meta["format"] == "xlsx"
    a = clean(x).lines
    b = clean(df).lines
    assert a["net_sales_idr"].sum() == b["net_sales_idr"].sum()
    assert len(a) == len(b)


def test_xls_rejected():
    with pytest.raises(InputError):
        read_upload("old.xls", b"whatever")

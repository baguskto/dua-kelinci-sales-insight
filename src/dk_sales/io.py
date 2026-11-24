"""Reading raw input files into an all-string DataFrame.

Everything is read as text so the DQ log can show the original value byte-for-byte. Parsing to
typed columns happens in the cleaning step under rule DQ-02.
"""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

import pandas as pd


class InputError(ValueError):
    """Raised when a file cannot be read as a table at all."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_bytes(data: bytes) -> tuple[str, str]:
    """Decode CSV bytes. Returns (text, encoding). Tries UTF-8 (with BOM), UTF-16, then cp1252."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16"), "utf-16"
        except UnicodeDecodeError as exc:
            raise InputError("File berawalan penanda UTF-16 tetapi isinya tidak bisa dibaca.") from exc
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    # Excel on Windows saves "CSV" as cp1252. Every byte decodes, so check for binary content first.
    if b"\x00" in data[:4096]:
        raise InputError("File tidak terbaca sebagai teks CSV (berisi data biner).")
    return data.decode("cp1252", errors="replace"), "cp1252"


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        first = text.splitlines()[0] if text else ""
        counts = {d: first.count(d) for d in [",", ";", "\t", "|"]}
        best = max(counts, key=lambda d: counts[d])
        return best if counts[best] > 0 else ","


def read_csv_bytes(data: bytes) -> tuple[pd.DataFrame, dict]:
    """Read CSV bytes into an all-string frame. Returns (frame, meta)."""
    if not data.strip():
        raise InputError("File kosong.")
    text, encoding = decode_bytes(data)
    delimiter = sniff_delimiter(text)
    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=True,
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InputError(f"File tidak bisa dibaca sebagai tabel CSV: {exc}") from exc
    return df, {"encoding": encoding, "delimiter": delimiter, "format": "csv"}


def read_xlsx_bytes(data: bytes) -> tuple[pd.DataFrame, dict]:
    """Read the first sheet of an .xlsx file. Dates and numbers are converted back to plain text."""
    try:
        raw = pd.read_excel(io.BytesIO(data), sheet_name=0, dtype=object, engine="openpyxl")
    except Exception as exc:  # openpyxl raises many types for broken files
        raise InputError(f"File Excel tidak bisa dibaca: {type(exc).__name__}") from exc

    def to_text(v: object) -> str:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%d") if v == v.normalize() else v.isoformat()
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")  # type: ignore[union-attr]
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    df = raw.map(to_text).astype(str)
    df.columns = [str(c) for c in df.columns]
    return df, {"encoding": "xlsx", "delimiter": None, "format": "xlsx"}


def read_upload(filename: str, data: bytes) -> tuple[pd.DataFrame, dict]:
    name = filename.lower()
    if name.endswith(".xlsx"):
        return read_xlsx_bytes(data)
    if name.endswith(".xls"):
        raise InputError("Format .xls lama tidak didukung. Simpan ulang sebagai .xlsx atau .csv.")
    return read_csv_bytes(data)


def read_raw(path: Path) -> pd.DataFrame:
    df, _ = read_csv_bytes(Path(path).read_bytes())
    return df

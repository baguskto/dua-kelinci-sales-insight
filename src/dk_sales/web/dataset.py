"""The active dataset: loaded from sales.csv at startup, replaceable by an admin upload.

Uploads go through the same contract and cleaning as the startup file. Rejected files never
replace the active dataset. Accepted uploads are stored under DATA_DIR/uploads/<sha256> so the
active dataset survives a restart.
"""

from __future__ import annotations

import io
import json
import threading
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from dk_sales import config, model
from dk_sales.clean import CleanResult, ContractError, clean
from dk_sales.io import InputError, read_upload, sha256_bytes

ALLOWED_EXTENSIONS = (".csv", ".txt", ".xlsx")
XLSX_MAX_UNCOMPRESSED = 60 * 1024 * 1024
XLSX_MAX_RATIO = 100
XLSX_MAX_ENTRIES = 500


@dataclass
class Dataset:
    fact: pd.DataFrame
    dims: dict[str, pd.DataFrame]
    result: CleanResult
    source: dict = field(default_factory=dict)

    @property
    def dim_outlet(self) -> pd.DataFrame:
        return self.dims["dim_outlet"]


def check_upload(filename: str, data: bytes, max_bytes: int) -> None:
    """Extension allowlist, size limit and content sniffing. Raises InputError."""
    name = (filename or "").lower().strip()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise InputError("Jenis file tidak didukung. Unggah .csv atau .xlsx.")
    if len(data) == 0:
        raise InputError("File kosong.")
    if len(data) > max_bytes:
        raise InputError(f"File lebih besar dari batas {max_bytes // (1024 * 1024)} MB.")
    if name.endswith(".xlsx"):
        if not data.startswith(b"PK\x03\x04"):
            raise InputError("File .xlsx tidak valid (bukan arsip Office Open XML).")
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise InputError("File .xlsx rusak.") from exc
        infos = zf.infolist()
        names = {i.filename for i in infos}
        if "xl/workbook.xml" not in names:
            raise InputError("File .xlsx tidak berisi workbook Excel.")
        if any(n.lower().endswith("vbaproject.bin") for n in names):
            raise InputError("File berisi macro. Simpan ulang sebagai .xlsx tanpa macro.")
        if len(infos) > XLSX_MAX_ENTRIES:
            raise InputError("File .xlsx berisi terlalu banyak bagian.")
        total = sum(i.file_size for i in infos)
        packed = max(1, sum(i.compress_size for i in infos))
        if total > XLSX_MAX_UNCOMPRESSED or total / packed > XLSX_MAX_RATIO:
            raise InputError("Isi .xlsx terlalu besar setelah dibuka (kemungkinan zip bomb).")
    else:
        head = data[:4096]
        if head.startswith(b"PK\x03\x04") or head.startswith(b"\xd0\xcf\x11\xe0"):
            raise InputError("Isi file adalah Excel, bukan CSV. Gunakan ekstensi .xlsx.")
        if b"\x00" in head and not head.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise InputError("File tidak terbaca sebagai teks CSV (berisi data biner).")


def build_dataset(raw: pd.DataFrame, source: dict) -> Dataset:
    holidays = model.load_holidays()
    period = (config.PERIOD_START, config.PERIOD_END)
    result = clean(raw, period=period, holidays=set(holidays))
    if result.lines.empty:
        raise ContractError("Semua baris gagal validasi; tidak ada data bersih.", {"rows_quarantined": len(result.quarantine)})
    fact = model.build_fact(result.lines)
    dims = model.build_dims(result.lines, period, holidays)
    fact = fact.merge(dims["dim_outlet"][["outlet_id", "outlet_name", "outlet_type"]], on="outlet_id", how="left")
    return Dataset(fact=fact, dims=dims, result=result, source=source)


def load_bytes(filename: str, data: bytes, max_bytes: int, max_rows: int) -> Dataset:
    check_upload(filename, data, max_bytes)
    raw, meta = read_upload(filename, data)
    if len(raw) > max_rows:
        raise InputError(f"File berisi {len(raw)} baris, melebihi batas {max_rows} baris.")
    from datetime import datetime

    source = {"filename": Path(filename).name[:120], "sha256": sha256_bytes(data), "bytes": len(data), **meta,
              "loaded_at": datetime.now().strftime("%d %b %Y %H:%M")}
    return build_dataset(raw, source)


class DatasetStore:
    def __init__(self, default_file: Path, data_dir: Path, max_bytes: int, max_rows: int):
        self.default_file = default_file
        self.data_dir = data_dir
        self.max_bytes = max_bytes
        self.max_rows = max_rows
        self._lock = threading.Lock()
        self._active: Dataset | None = None
        self.load_error: str | None = None

    @property
    def active(self) -> Dataset | None:
        return self._active

    def _pointer(self) -> Path:
        return self.data_dir / "active.json"

    def load_startup(self) -> None:
        pointer = self._pointer()
        try:
            if pointer.exists():
                info = json.loads(pointer.read_text())
                path = self.data_dir / "uploads" / info["stored_as"]
                if path.exists():
                    self._active = load_bytes(info["filename"], path.read_bytes(), self.max_bytes, self.max_rows)
                    self._active.source["origin"] = "upload"
                    return
            data = self.default_file.read_bytes()
            self._active = load_bytes(self.default_file.name, data, max(self.max_bytes, len(data)), max(self.max_rows, 10_000_000))
            self._active.source["origin"] = "default"
        except FileNotFoundError:
            self.load_error = f"File data {self.default_file.name} tidak ditemukan. Unggah file CSV atau .xlsx."
        except (InputError, ContractError) as exc:
            self.load_error = f"File data {self.default_file.name} tidak valid: {exc}"

    def replace_from_upload(self, filename: str, data: bytes) -> Dataset:
        ds = load_bytes(filename, data, self.max_bytes, self.max_rows)
        ds.source["origin"] = "upload"
        stored_as = ds.source["sha256"] + (".xlsx" if filename.lower().endswith(".xlsx") else ".csv")
        try:
            (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
            (self.data_dir / "uploads" / stored_as).write_bytes(data)
            self._pointer().write_text(json.dumps({"filename": ds.source["filename"], "stored_as": stored_as, "sha256": ds.source["sha256"]}))
        except OSError:
            ds.source["persisted"] = False
        with self._lock:
            self._active = ds
            self.load_error = None
        return ds

    def reset_to_default(self) -> None:
        try:
            self._pointer().unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        self._active = None
        self.load_startup()

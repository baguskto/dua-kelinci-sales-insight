"""Cleaning pipeline: applies DQ rules to an all-string raw frame.

Contract:
- The input frame is never mutated.
- Every changed cell, every inferred value, every flag and every quarantined row produces one DQ
  log entry (raw_row_id, rule_id, column, before, after, action, reason).
- No row disappears without a quarantine record. rows_in == rows_clean + rows_quarantined.
- The output depends only on the input, so running it twice gives identical results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from dk_sales import config
from dk_sales.rules import FLAG_COLUMNS, RULES_BY_ID

LOG_COLUMNS = ["raw_row_id", "source_line", "rule_id", "column", "before", "after", "action", "reason"]


class ContractError(ValueError):
    """The input violates a file-level rule (DQ-01) and cannot be processed."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


@dataclass
class DQLog:
    entries: list[dict] = field(default_factory=list)

    def add(self, raw_row_id: int, rule_id: str, column: str, before, after, action: str, reason: str) -> None:
        self.entries.append(
            {
                "raw_row_id": int(raw_row_id),
                "source_line": int(raw_row_id) + 1,
                "rule_id": rule_id,
                "column": column,
                "before": "" if before is None or (isinstance(before, float) and pd.isna(before)) else str(before),
                "after": "" if after is None or (isinstance(after, float) and pd.isna(after)) else str(after),
                "action": action,
                "reason": reason,
            }
        )

    def frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.entries, columns=LOG_COLUMNS)
        if df.empty:
            return df.astype({"raw_row_id": "int64", "source_line": "int64"})
        return df.sort_values(["raw_row_id", "rule_id", "column"], kind="mergesort").reset_index(drop=True)


@dataclass
class CleanResult:
    raw: pd.DataFrame
    lines: pd.DataFrame
    quarantine: pd.DataFrame
    dq_log: pd.DataFrame
    rule_stats: dict[str, dict]
    meta: dict


# ---------------------------------------------------------------------------
# helpers


def _norm_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


# Control and bidi-override characters can hide or reorder text in reports and are a prompt-injection vector.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", _CONTROL.sub("", value)).strip()


def canonical_region(value: str) -> str | None:
    key = _norm_text(value).upper()
    for region in config.CANONICAL_REGIONS:
        if region.upper() == key:
            return region
    return config.REGION_ALIASES.get(key)


def _parse_int(value: str) -> int | None:
    v = value.strip()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    # Excel exports sometimes write integers as 12.0
    if re.fullmatch(r"-?\d+\.0+", v):
        return int(v.split(".")[0])
    return None


def _parse_date(value: str) -> date | None:
    v = value.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[ T]00:00(?::00)?)?", v)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)  # dd/mm/yyyy, the Indonesian locale default
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _mode(series: pd.Series):
    counts = series.value_counts(dropna=True)
    if counts.empty:
        return None
    top = counts.max()
    return sorted(v for v, c in counts.items() if c == top)[0]


def round_half_up(value: float, step: int) -> int:
    return int((value / step) + 0.5) * step if value >= 0 else -int((-value / step) + 0.5) * step


def longest_increasing_subsequence(values: list[int]) -> set[int]:
    """Indices of one longest strictly increasing subsequence (deterministic, O(n log n))."""
    import bisect

    tails: list[int] = []
    tails_idx: list[int] = []
    prev = [-1] * len(values)
    for i, v in enumerate(values):
        pos = bisect.bisect_left(tails, v)
        if pos == len(tails):
            tails.append(v)
            tails_idx.append(i)
        else:
            tails[pos] = v
            tails_idx[pos] = i
        prev[i] = tails_idx[pos - 1] if pos > 0 else -1
    out: set[int] = set()
    k = tails_idx[-1] if tails_idx else -1
    while k >= 0:
        out.add(k)
        k = prev[k]
    return out


# ---------------------------------------------------------------------------
# pipeline


def check_structure(raw: pd.DataFrame, log_meta: dict) -> pd.DataFrame:
    """DQ-01: normalise headers, require all 15 columns, drop unknown ones."""
    rename = {c: _norm_header(c) for c in raw.columns}
    df = raw.rename(columns=rename)
    if len(set(df.columns)) != len(df.columns):
        raise ContractError("Ada nama kolom ganda.", {"columns": list(raw.columns)})
    missing = [c for c in config.RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ContractError(
            "Kolom wajib tidak ditemukan: " + ", ".join(missing),
            {"missing": missing, "found": [str(c) for c in raw.columns]},
        )
    extra = [c for c in df.columns if c not in config.RAW_COLUMNS]
    log_meta["renamed_columns"] = {str(k): v for k, v in rename.items() if str(k) != v}
    log_meta["ignored_columns"] = extra
    return df[config.RAW_COLUMNS].copy()


def clean(raw_in: pd.DataFrame, period: tuple[str, str] | None = None, holidays: set[date] | None = None) -> CleanResult:
    period = period or (config.PERIOD_START, config.PERIOD_END)
    holidays = holidays or set()
    meta: dict = {"rows_in": int(len(raw_in)), "period_start": period[0], "period_end": period[1]}
    log = DQLog()
    stats: dict[str, dict] = {rid: {"rows": 0, "entities": 0, "remaining": 0, "note": ""} for rid in RULES_BY_ID}

    if len(raw_in) == 0:
        raise ContractError("File tidak berisi baris data.")
    df = check_structure(raw_in, meta)
    df = df.astype(str)
    df.insert(0, "raw_row_id", range(1, len(df) + 1))
    raw = df.copy()

    quarantine: list[dict] = []

    def quarantine_rows(idx: pd.Index, rule_id: str, reasons: dict[int, str]) -> None:
        nonlocal df
        for i in idx:
            row = df.loc[i]
            reason = reasons[i]
            quarantine.append({**{c: row[c] for c in ["raw_row_id", *config.RAW_COLUMNS]}, "rule_id": rule_id, "reason": reason})
            log.add(row["raw_row_id"], rule_id, "*", "", "", "quarantined", reason)
        df = df.drop(index=idx)

    # DQ-04 whitespace (applied first so later comparisons see clean text)
    ws_rows = set()
    for col in config.RAW_COLUMNS:
        new = df[col].map(_norm_text)
        changed = new != df[col]
        for i in df.index[changed]:
            log.add(
                df.at[i, "raw_row_id"],
                "DQ-04",
                col,
                repr(df.at[i, col]),
                repr(new[i]),
                "fixed",
                "Spasi di awal/akhir, spasi ganda atau karakter kontrol dihapus.",
            )
            ws_rows.add(i)
        df[col] = new
    stats["DQ-04"]["rows"] = len(ws_rows)

    # DQ-02 value formats
    bad: dict[int, str] = {}
    parsed_dates: dict[int, date] = {}
    parsed_ints: dict[str, dict[int, int]] = {c: {} for c in config.INT_COLUMNS}
    inv_re = re.compile(config.INVOICE_PATTERN)
    for i, row in df.iterrows():
        problems = []
        for col in config.REQUIRED_NON_BLANK:
            if row[col] == "":
                problems.append(f"{col} kosong")
        d = _parse_date(row["date"])
        if d is None and row["date"] != "":
            problems.append(f"tanggal tidak terbaca ({row['date'][:20]!r})")
        else:
            parsed_dates[i] = d  # type: ignore[assignment]
        for col in config.INT_COLUMNS:
            v = _parse_int(row[col])
            if v is None and row[col] != "":
                problems.append(f"{col} bukan bilangan bulat ({row[col][:20]!r})")
            elif v is not None:
                parsed_ints[col][i] = v
        if row["invoice_no"] and not inv_re.match(row["invoice_no"]):
            problems.append(f"format invoice_no tidak dikenal ({row['invoice_no'][:20]!r})")
        if problems:
            bad[i] = "; ".join(problems)
    stats["DQ-02"]["rows"] = len(bad)
    if bad:
        quarantine_rows(pd.Index(list(bad)), "DQ-02", bad)
    df["date"] = pd.to_datetime(pd.Series({i: parsed_dates[i] for i in df.index}, dtype=object))
    for col in config.INT_COLUMNS:
        df[col] = pd.Series({i: parsed_ints[col][i] for i in df.index}, dtype="int64")

    # DQ-03 region spelling
    region_rows = 0
    unresolved_region = []
    for i in df.index:
        val = df.at[i, "region"]
        canon = canonical_region(val)
        if canon is None:
            unresolved_region.append(i)
            continue
        if canon != val:
            log.add(df.at[i, "raw_row_id"], "DQ-03", "region", val, canon, "fixed", f"Region '{val}' dipetakan ke nama baku '{canon}'.")
            df.at[i, "region"] = canon
            region_rows += 1
    # Regions that are not canonical and have no alias: take the branch's canonical region if known.
    if unresolved_region:
        branch_region = df.loc[~df.index.isin(unresolved_region)].groupby("branch")["region"].agg(_mode).to_dict()
        for i in unresolved_region:
            val = df.at[i, "region"]
            br = df.at[i, "branch"]
            if br in branch_region:
                log.add(
                    df.at[i, "raw_row_id"],
                    "DQ-03",
                    "region",
                    val,
                    branch_region[br],
                    "inferred",
                    f"Region '{val}' tidak dikenal; diambil dari region cabang {br}.",
                )
                df.at[i, "region"] = branch_region[br]
                region_rows += 1
            else:
                log.add(
                    df.at[i, "raw_row_id"], "DQ-03", "region", val, val, "flagged", f"Region '{val}' tidak dikenal dan cabang {br} tidak punya region baku."
                )
                stats["DQ-03"]["remaining"] += 1
    stats["DQ-03"]["rows"] = region_rows

    # Snapshot used for the "before" counts of consistency rules (after trimming, before inference/fixes
    # that depend on other rows). Built from raw text so DQ-19/20/22 show what the raw file looked like.
    raw_view = raw.loc[raw["raw_row_id"].isin(df["raw_row_id"])].copy()

    # DQ-24 qty sign vs document type
    sign_bad: dict[int, str] = {}
    for i in df.index:
        prefix = df.at[i, "invoice_no"][:3]
        q = df.at[i, "qty_carton"]
        amounts = [df.at[i, c] for c in ["gross_sales_idr", "net_sales_idr"]]
        if q == 0:
            sign_bad[i] = "qty_carton nol"
        elif prefix == config.SALE_PREFIX and (q < 0 or any(a < 0 for a in amounts)):
            sign_bad[i] = "invoice penjualan (INV) dengan qty atau nilai negatif"
        elif prefix == config.RETURN_PREFIX and (q > 0 or any(a > 0 for a in amounts)):
            sign_bad[i] = "dokumen retur (RTR) dengan qty atau nilai positif"
        elif df.at[i, "price_per_carton_idr"] <= 0:
            sign_bad[i] = "harga per karton nol atau negatif"
    stats["DQ-24"]["rows"] = len(sign_bad)
    if sign_bad:
        quarantine_rows(pd.Index(list(sign_bad)), "DQ-24", sign_bad)

    # DQ-14 / DQ-15 arithmetic
    for rule_id, label, expected in [
        ("DQ-14", "gross_sales_idr", lambda f: f["qty_carton"] * f["price_per_carton_idr"]),
        ("DQ-15", "net_sales_idr", lambda f: f["gross_sales_idr"] - f["discount_idr"]),
    ]:
        exp = expected(df)
        mism = df.index[df[label] != exp]
        reasons = {i: f"{label} {df.at[i, label]} tidak sama dengan hitungan {int(exp[i])}" for i in mism}
        stats[rule_id]["rows"] = len(mism)
        if len(mism):
            quarantine_rows(mism, rule_id, reasons)

    # DQ-06 exact duplicates (compared after DQ-03/DQ-04 so spelling variants cannot hide a duplicate)
    key_cols = config.RAW_COLUMNS
    dup_mask = df.duplicated(subset=key_cols, keep="first")
    first_of: dict[tuple, int] = {}
    for i in df.index:
        k = tuple(df.loc[i, key_cols])
        first_of.setdefault(k, df.at[i, "raw_row_id"])
    dup_reasons = {
        i: f"Duplikat persis dari raw_row_id {first_of[tuple(df.loc[i, key_cols])]} (invoice {df.at[i, 'invoice_no']}, SKU {df.at[i, 'sku']})."
        for i in df.index[dup_mask]
    }
    stats["DQ-06"]["rows"] = len(dup_reasons)
    stats["DQ-06"]["entities"] = df.loc[dup_mask, "invoice_no"].nunique()
    if dup_reasons:
        quarantine_rows(pd.Index(list(dup_reasons)), "DQ-06", dup_reasons)

    for col in FLAG_COLUMNS:
        df[col] = False
    if df.empty:
        return _finish(df, raw, quarantine, log, stats, meta, empty=True)
    df["is_return"] = df["invoice_no"].str.startswith(config.RETURN_PREFIX)

    # DQ-05 blank salesman
    blank = df.index[df["salesman"] == ""]
    inv_sales = df.loc[df["salesman"] != ""].groupby("invoice_no")["salesman"].agg(lambda s: sorted(set(s)))
    outlet_sales = df.loc[df["salesman"] != ""].groupby("outlet_id")["salesman"].agg(lambda s: sorted(set(s)))
    unresolved = 0
    for i in blank:
        inv = df.at[i, "invoice_no"]
        out = df.at[i, "outlet_id"]
        cand = inv_sales.get(inv, [])
        if len(cand) == 1:
            df.at[i, "salesman"] = cand[0]
            df.at[i, "dq_salesman_inferred"] = True
            log.add(df.at[i, "raw_row_id"], "DQ-05", "salesman", "", cand[0], "inferred", f"Baris lain di invoice {inv} dicatat atas nama {cand[0]}.")
            continue
        ocand = outlet_sales.get(out, [])
        if len(ocand) == 1:
            df.at[i, "salesman"] = ocand[0]
            df.at[i, "dq_salesman_inferred"] = True
            log.add(df.at[i, "raw_row_id"], "DQ-05", "salesman", "", ocand[0], "inferred", f"Outlet {out} hanya pernah dilayani {ocand[0]}.")
            continue
        unresolved += 1
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-05",
            "salesman",
            "",
            "",
            "flagged",
            f"Tidak ada bukti salesman: invoice {inv} tidak punya salesman lain, outlet {out} dilayani {len(ocand)} salesman.",
        )
    stats["DQ-05"]["rows"] = len(blank)
    stats["DQ-05"]["remaining"] = unresolved

    # DQ-07 returns
    ret = df.index[df["is_return"]]
    for i in ret:
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-07",
            "invoice_no",
            df.at[i, "invoice_no"],
            df.at[i, "invoice_no"],
            "flagged",
            f"Dokumen retur, qty {df.at[i, 'qty_carton']}, net {df.at[i, 'net_sales_idr']}. Disimpan sebagai retur.",
        )
    stats["DQ-07"]["rows"] = len(ret)

    # DQ-08 returns without enough prior purchases in the data
    sales = df.loc[~df["is_return"]]
    unmatched = 0
    for i in ret:
        o, s, d = df.at[i, "outlet_id"], df.at[i, "sku"], df.at[i, "date"]
        bought = sales[(sales["outlet_id"] == o) & (sales["sku"] == s) & (sales["date"] <= d)]
        qty = int(bought["qty_carton"].sum())
        if qty < abs(int(df.at[i, "qty_carton"])):
            unmatched += 1
            df.at[i, "dq_return_unmatched"] = True
            invs = ", ".join(sorted(bought["invoice_no"].unique())) or "tidak ada"
            log.add(
                df.at[i, "raw_row_id"],
                "DQ-08",
                "qty_carton",
                df.at[i, "qty_carton"],
                df.at[i, "qty_carton"],
                "flagged",
                f"Retur {abs(int(df.at[i, 'qty_carton']))} karton {s}, sedangkan pembelian outlet {o} untuk SKU ini sampai tanggal retur hanya {qty} karton (invoice: {invs}).",
            )
    stats["DQ-08"]["rows"] = unmatched

    # DQ-09 late-numbered invoices
    inv = df.loc[df["invoice_no"].str.startswith(config.SALE_PREFIX)].groupby("invoice_no").agg(date=("date", "min")).reset_index()
    inv["num"] = inv["invoice_no"].str[3:].astype(int)
    inv = inv.sort_values(["date", "num"], kind="mergesort").reset_index(drop=True)
    in_seq = longest_increasing_subsequence(inv["num"].tolist())
    inv["in_seq"] = inv.index.isin(in_seq)
    off_nums = set(inv.loc[~inv["in_seq"], "num"])
    # An in-sequence invoice whose number jumps over numbers used by back-dated invoices belongs to the
    # same late-issued block (e.g. INV500801 after INV500798 when 799 and 800 are back-dated).
    late = set(inv.loc[~inv["in_seq"], "invoice_no"])
    seq = inv.loc[inv["in_seq"]].sort_values("num")
    prev_num = None
    for _, r in seq.iterrows():
        if prev_num is not None and any(prev_num < n < r["num"] for n in off_nums):
            late.add(r["invoice_no"])
        prev_num = r["num"]
    regular = inv.loc[~inv["invoice_no"].isin(late)]
    late_rows = df.index[df["invoice_no"].isin(late)]
    for i in late_rows:
        d = df.at[i, "date"]
        n = int(df.at[i, "invoice_no"][3:])
        later_lower = regular[(regular["date"] > d) & (regular["num"] < n)]
        if len(later_lower):
            ex = later_lower.sort_values("num").iloc[-1]
            why = f"Nomor {df.at[i, 'invoice_no']} bertanggal {d.date()} lebih besar dari {len(later_lower)} invoice reguler bertanggal lebih akhir, terakhir {ex['invoice_no']} ({ex['date'].date()})."
        else:
            why = f"Nomor {df.at[i, 'invoice_no']} melompati nomor yang dipakai invoice bertanggal lebih awal; bagian dari blok yang sama."
        df.at[i, "dq_late_numbered_invoice"] = True
        log.add(df.at[i, "raw_row_id"], "DQ-09", "invoice_no", df.at[i, "invoice_no"], df.at[i, "invoice_no"], "flagged", why)
    stats["DQ-09"]["rows"] = len(late_rows)
    stats["DQ-09"]["entities"] = len(late)
    if late:
        stats["DQ-09"]["note"] = f"{min(late)} s.d. {max(late)}"

    # DQ-10 outlets seen only in late-numbered invoices
    sale_lines = df.loc[~df["is_return"]]
    by_outlet = sale_lines.groupby("outlet_id")["dq_late_numbered_invoice"].all()
    suspect = sorted(by_outlet.index[by_outlet])
    for i in df.index[df["outlet_id"].isin(suspect)]:
        df.at[i, "dq_suspect_outlet"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-10",
            "outlet_id",
            df.at[i, "outlet_id"],
            df.at[i, "outlet_id"],
            "flagged",
            f"Outlet {df.at[i, 'outlet_id']} hanya muncul di invoice di luar urutan.",
        )
    stats["DQ-10"]["rows"] = int(df["dq_suspect_outlet"].sum())
    stats["DQ-10"]["entities"] = len(suspect)
    stats["DQ-10"]["note"] = ", ".join(suspect)

    # DQ-11 non-trading day
    for i in df.index:
        d = df.at[i, "date"]
        if d.weekday() == 6 or d.date() in holidays:
            kind = "hari Minggu" if d.weekday() == 6 else "libur nasional"
            df.at[i, "dq_non_trading_day"] = True
            log.add(df.at[i, "raw_row_id"], "DQ-11", "date", d.date(), d.date(), "flagged", f"Transaksi pada {kind} {d.date()}.")
    stats["DQ-11"]["rows"] = int(df["dq_non_trading_day"].sum())

    # DQ-12 / DQ-13 shared outlet names
    outlets = df.groupby("outlet_id").agg(name=("outlet_name", _mode), branch=("branch", _mode)).reset_index()
    shared_same_branch: list[str] = []
    shared_any: list[str] = []
    for _, grp in outlets.groupby("name"):
        if len(grp) < 2:
            continue
        shared_any.extend(grp["outlet_id"])
        for _, g2 in grp.groupby("branch"):
            if len(g2) > 1:
                shared_same_branch.extend(g2["outlet_id"])
    for i in df.index[df["outlet_id"].isin(shared_same_branch)]:
        o = df.at[i, "outlet_id"]
        peers = sorted(set(outlets.loc[(outlets["name"] == df.at[i, "outlet_name"]) & (outlets["branch"] == df.at[i, "branch"]), "outlet_id"]) - {o})
        df.at[i, "dq_outlet_name_shared_in_branch"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-12",
            "outlet_id",
            o,
            o,
            "flagged",
            f"Nama '{df.at[i, 'outlet_name']}' juga dipakai {', '.join(peers)} di cabang {df.at[i, 'branch']}.",
        )
    stats["DQ-12"]["rows"] = int(df["dq_outlet_name_shared_in_branch"].sum())
    stats["DQ-12"]["entities"] = len(shared_same_branch)
    stats["DQ-12"]["note"] = ", ".join(sorted(shared_same_branch))
    stats["DQ-13"]["rows"] = int(df["outlet_id"].isin(shared_any).sum())
    stats["DQ-13"]["entities"] = len(shared_any)
    stats["DQ-13"]["note"] = f"{outlets[outlets['outlet_id'].isin(shared_any)]['name'].nunique()} nama dipakai {len(shared_any)} outlet_id"

    # DQ-16 discount pattern
    off = 0
    for i in df.index:
        g, disc = df.at[i, "gross_sales_idr"], df.at[i, "discount_idr"]
        ok = False
        for rate in config.DISCOUNT_RATES_PCT:
            if disc == round_half_up(g * rate / 100, config.DISCOUNT_ROUNDING_IDR):
                ok = True
                break
        if not ok:
            off += 1
            df.at[i, "dq_discount_off_pattern"] = True
            log.add(
                df.at[i, "raw_row_id"],
                "DQ-16",
                "discount_idr",
                disc,
                disc,
                "flagged",
                f"Diskon {disc} dari gross {g} tidak cocok dengan 0/2/3/5% dibulatkan ke Rp100.",
            )
    stats["DQ-16"]["rows"] = off

    # DQ-17 price per SKU, DQ-18 brand per SKU
    for rule_id, col, flag in [("DQ-17", "price_per_carton_idr", "dq_price_off_list"), ("DQ-18", "brand", "dq_brand_mismatch")]:
        ref = df.groupby("sku")[col].agg(_mode)
        mism = df.index[df[col] != df["sku"].map(ref)]
        for i in mism:
            df.at[i, flag] = True
            log.add(df.at[i, "raw_row_id"], rule_id, col, df.at[i, col], df.at[i, col], "flagged", f"SKU {df.at[i, 'sku']} biasanya {ref[df.at[i, 'sku']]}.")
        stats[rule_id]["rows"] = len(mism)
        stats[rule_id]["entities"] = int(df.loc[mism, "sku"].nunique())

    # Consistency rules: count violations in the raw text view and again after cleaning.
    def outlet_conflicts(frame: pd.DataFrame) -> tuple[pd.Index, list[str]]:
        idx: set = set()
        ids: set = set()
        for col in ["outlet_name", "outlet_type", "branch", "region"]:
            ref = frame.groupby("outlet_id")[col].agg(_mode)
            m = frame.index[frame[col] != frame["outlet_id"].map(ref)]
            idx |= set(m)
            ids |= set(frame.loc[m, "outlet_id"])
        return pd.Index(sorted(idx)), sorted(ids)

    def branch_region_conflicts(frame: pd.DataFrame) -> pd.Index:
        ref = frame.groupby("branch")["region"].agg(_mode)
        return frame.index[frame["region"] != frame["branch"].map(ref)]

    def salesman_branch_conflicts(frame: pd.DataFrame) -> pd.Index:
        f = frame[frame["salesman"] != ""]
        ref = f.groupby("salesman")["branch"].agg(_mode)
        return f.index[f["branch"] != f["salesman"].map(ref)]

    def header_conflicts(frame: pd.DataFrame) -> tuple[pd.Index, list[str]]:
        idx: set = set()
        invs: set = set()
        for col in config.INVOICE_HEADER_COLUMNS:
            ref = frame.groupby("invoice_no")[col].agg(_mode)
            m = frame.index[frame[col] != frame["invoice_no"].map(ref)]
            idx |= set(m)
            invs |= set(frame.loc[m, "invoice_no"])
        return pd.Index(sorted(idx)), sorted(invs)

    raw_out_idx, raw_out_ids = outlet_conflicts(raw_view)
    raw_hdr_idx, raw_hdr_invs = header_conflicts(raw_view)
    stats["DQ-19"].update(rows=len(raw_out_idx), entities=len(raw_out_ids), note="mentah: " + ", ".join(raw_out_ids))
    stats["DQ-20"].update(rows=len(branch_region_conflicts(raw_view)))
    stats["DQ-21"].update(rows=len(salesman_branch_conflicts(raw_view)))
    stats["DQ-22"].update(rows=len(raw_hdr_idx), entities=len(raw_hdr_invs))

    ci, cids = outlet_conflicts(df)
    for i in ci:
        df.at[i, "dq_outlet_attr_conflict"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-19",
            "outlet_id",
            df.at[i, "outlet_id"],
            df.at[i, "outlet_id"],
            "flagged",
            "Atribut outlet berbeda dari nilai terbanyak untuk outlet_id ini.",
        )
    stats["DQ-19"]["remaining"] = len(ci)
    br = branch_region_conflicts(df)
    for i in br:
        df.at[i, "dq_branch_region_conflict"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-20",
            "region",
            df.at[i, "region"],
            df.at[i, "region"],
            "flagged",
            f"Cabang {df.at[i, 'branch']} biasanya di region lain.",
        )
    stats["DQ-20"]["remaining"] = len(br)
    sb = salesman_branch_conflicts(df)
    for i in sb:
        df.at[i, "dq_salesman_branch_conflict"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-21",
            "salesman",
            df.at[i, "salesman"],
            df.at[i, "salesman"],
            "flagged",
            f"Salesman {df.at[i, 'salesman']} biasanya di cabang lain.",
        )
    stats["DQ-21"]["remaining"] = len(sb)
    hi, hinv = header_conflicts(df)
    for i in hi:
        df.at[i, "dq_invoice_header_conflict"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-22",
            "invoice_no",
            df.at[i, "invoice_no"],
            df.at[i, "invoice_no"],
            "flagged",
            "Header baris ini berbeda dari baris lain di invoice yang sama.",
        )
    stats["DQ-22"]["remaining"] = len(hi)

    # DQ-23 SKU repeated inside an invoice after exact duplicates are gone
    rep = df.index[df.duplicated(subset=["invoice_no", "sku"], keep=False)]
    for i in rep:
        df.at[i, "dq_repeated_sku_in_invoice"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-23",
            "sku",
            df.at[i, "sku"],
            df.at[i, "sku"],
            "flagged",
            f"SKU muncul lebih dari sekali di invoice {df.at[i, 'invoice_no']} dengan angka berbeda.",
        )
    stats["DQ-23"]["rows"] = len(rep)
    raw_rep = raw_view.duplicated(subset=["invoice_no", "sku"], keep=False).sum()
    stats["DQ-23"]["note"] = f"mentah: {int(raw_rep)} baris (semuanya duplikat persis DQ-06)"

    # DQ-25 more than one sales invoice per outlet per day
    s = df.loc[~df["is_return"]]
    cnt = s.groupby(["outlet_id", "date"])["invoice_no"].nunique()
    multi = cnt[cnt > 1]
    for o, d in multi.index:
        for i in s.index[(s["outlet_id"] == o) & (s["date"] == d)]:
            df.at[i, "dq_multi_invoice_day"] = True
            log.add(
                df.at[i, "raw_row_id"],
                "DQ-25",
                "invoice_no",
                df.at[i, "invoice_no"],
                df.at[i, "invoice_no"],
                "flagged",
                f"Outlet {o} punya {int(multi[(o, d)])} invoice penjualan pada {d.date()}.",
            )
    stats["DQ-25"]["rows"] = int(df["dq_multi_invoice_day"].sum())
    stats["DQ-25"]["entities"] = len(multi)
    same_day_return = df.loc[df["is_return"]].merge(s, on=["outlet_id", "date"])
    stats["DQ-25"]["note"] = (
        f"{same_day_return['invoice_no_x'].nunique()} retur di hari yang sama dengan invoice penjualan outlet yang sama (bukan pelanggaran)"
    )

    # DQ-26 trading days without sales
    start, end = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    days = pd.date_range(start, end, freq="D")
    present = set(df["date"])
    empty_trading = [d for d in days if d.weekday() < 6 and d.date() not in holidays and d not in present]
    stats["DQ-26"]["entities"] = len(empty_trading)
    stats["DQ-26"]["note"] = ", ".join(str(d.date()) for d in empty_trading) or "tidak ada"

    # DQ-27 out of period
    oop = df.index[(df["date"] < start) | (df["date"] > end)]
    for i in oop:
        df.at[i, "dq_out_of_period"] = True
        log.add(
            df.at[i, "raw_row_id"],
            "DQ-27",
            "date",
            df.at[i, "date"].date(),
            df.at[i, "date"].date(),
            "flagged",
            f"Tanggal di luar periode {period[0]} s.d. {period[1]}.",
        )
    stats["DQ-27"]["rows"] = len(oop)

    return _finish(df, raw, quarantine, log, stats, meta)


def _finish(df, raw, quarantine, log, stats, meta, empty: bool = False) -> CleanResult:
    q = pd.DataFrame(quarantine, columns=["raw_row_id", *config.RAW_COLUMNS, "rule_id", "reason"])
    q = q.sort_values("raw_row_id").reset_index(drop=True)
    df = df.sort_values("raw_row_id").reset_index(drop=True)
    if empty:
        df["is_return"] = pd.Series(dtype=bool)
        df["dq_flags"] = pd.Series(dtype=str)
    else:
        df["dq_flags"] = df.apply(lambda r: ";".join(c for c in FLAG_COLUMNS if r[c]), axis=1)
    meta.update(rows_clean=int(len(df)), rows_quarantined=int(len(q)))
    if meta["rows_in"] != meta["rows_clean"] + meta["rows_quarantined"]:
        raise RuntimeError("row conservation violated: a row was dropped without a quarantine record")
    return CleanResult(raw=raw, lines=df, quarantine=q, dq_log=log.frame(), rule_stats=stats, meta=meta)

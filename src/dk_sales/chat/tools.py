"""Typed, read-only tools for the "Tanya data" chat.

The model (or the offline intent parser) can only call these functions. Every argument is
validated against an allowlist; the caller's scope is applied before any number is computed,
so a Head of Region cannot reach another region's numbers through any argument. No tool has a
side effect: none can send a message, change data or read raw rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from dk_sales import analytics as an
from dk_sales import config, fmt, guard
from dk_sales.analytics import Scope

MAX_N = 20
FILTER_KEYS = ("region", "brand", "outlet_type", "salesman", "branch")
FILTER_LABELS = {"region": "region", "brand": "brand", "outlet_type": "tipe", "salesman": "salesman", "branch": "cabang"}


def _filt(used: dict) -> str:
    return ", ".join(f"{FILTER_LABELS[k]} {v}" for k, v in used.items())
OUTLET_ID_RE = re.compile(r"^OUT\d{1,8}$")


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ToolResult:
    tool: str
    args: dict
    data: dict
    text: str
    table: list[dict] = field(default_factory=list)
    facts: list[float] = field(default_factory=list)
    pct_facts: list[float] = field(default_factory=list)

    @property
    def source_label(self) -> str:
        shown = {k: v for k, v in self.args.items() if v not in (None, "", "all")}
        if self.args.get("period") == "all":
            shown["period"] = "semua bulan"
        return self.tool + (" (" + ", ".join(f"{k}={v}" for k, v in shown.items()) + ")" if shown else "")


_DIM_ENUM = list(an.DIMENSIONS)
_METRIC_ENUM = list(an.METRICS)

TOOL_SPECS: list[dict] = [
    {
        "name": "sales_by",
        "description": "Nilai penjualan per anggota dimensi (atau total bila dimension='total'), untuk satu periode, dengan filter opsional. Juga mengembalikan perubahan bulan terakhir vs bulan sebelumnya.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "enum": ["total", *_DIM_ENUM]},
                "period": {"type": "string", "description": "'all' atau bulan 'YYYY-MM' yang ada di data"},
                "metric": {"type": "string", "enum": _METRIC_ENUM},
                "region": {"type": "string"},
                "brand": {"type": "string"},
                "outlet_type": {"type": "string"},
                "salesman": {"type": "string"},
                "branch": {"type": "string"},
            },
            "required": ["dimension"],
            "additionalProperties": False,
        },
    },
    {
        "name": "top_bottom",
        "description": "N anggota dimensi dengan nilai tertinggi (order='top') atau terendah (order='bottom').",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "enum": _DIM_ENUM},
                "n": {"type": "integer", "minimum": 1, "maximum": MAX_N},
                "order": {"type": "string", "enum": ["top", "bottom"]},
                "metric": {"type": "string", "enum": _METRIC_ENUM},
                "period": {"type": "string"},
                "region": {"type": "string"},
                "brand": {"type": "string"},
            },
            "required": ["dimension"],
            "additionalProperties": False,
        },
    },
    {
        "name": "compare_periods",
        "description": "Bandingkan bulan terakhir dengan bulan sebelumnya, total atau per anggota dimensi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "enum": ["total", *_DIM_ENUM]},
                "metric": {"type": "string", "enum": _METRIC_ENUM},
                "region": {"type": "string"},
                "brand": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "weakest_outlets",
        "description": "Outlet terlemah: penjualan neto paling rendah dibanding median outlet bertipe sama, dengan alasan dan saran tindakan.",
        "input_schema": {
            "type": "object",
            "properties": {"period": {"type": "string"}, "n": {"type": "integer", "minimum": 1, "maximum": MAX_N}},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "outlet_detail",
        "description": "Detail satu outlet berdasarkan outlet_id (format OUT1234).",
        "input_schema": {
            "type": "object",
            "properties": {"outlet_id": {"type": "string"}},
            "required": ["outlet_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "find_outlet",
        "description": "Cari outlet_id dari nama outlet. Bisa mengembalikan lebih dari satu bila namanya dipakai beberapa outlet.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "maxLength": 80}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "data_quality_summary",
        "description": "Ringkasan kualitas data: jumlah baris per aturan DQ, duplikat yang dikarantina, retur, salesman yang diisi.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
]
TOOL_NAMES = {t["name"] for t in TOOL_SPECS}


class ToolRunner:
    def __init__(self, dataset, scope: Scope):
        self.ds = dataset
        self.scope = scope
        self.fact = scope.apply(dataset.fact)
        self.months = an.months(self.fact) or an.months(dataset.fact)
        self.dim_outlet = dataset.dim_outlet
        full = dataset.fact
        self.known = {
            "region": sorted(full["region"].unique()),
            "brand": sorted(full["brand"].unique()),
            "outlet_type": sorted(full["outlet_type"].unique()),
            "salesman": sorted(s for s in full["salesman"].unique() if s),
            "branch": sorted(full["branch"].unique()),
        }

    # -- validation ---------------------------------------------------------

    def _period(self, v) -> str:
        if v in (None, "", "all"):
            return "all"
        if not isinstance(v, str) or v not in self.months:
            raise ToolError("bad_period", f"Periode harus 'all' atau salah satu bulan di data: {', '.join(self.months)}.")
        return v

    def _choice(self, v, allowed, name, default=None):
        if v in (None, ""):
            return default
        if v not in allowed:
            raise ToolError("bad_arg", f"Nilai {name} tidak dikenal. Pilihan: {', '.join(map(str, allowed))}.")
        return v

    def _n(self, v, default=5) -> int:
        if v in (None, ""):
            return default
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= MAX_N:
            raise ToolError("bad_arg", f"n harus bilangan bulat 1 sampai {MAX_N}.")
        return v

    def _filters(self, args: dict) -> tuple[pd.DataFrame, dict]:
        f = self.fact
        used = {}
        for k in FILTER_KEYS:
            v = args.get(k)
            if v in (None, ""):
                continue
            if not isinstance(v, str) or v not in self.known[k]:
                raise ToolError("bad_arg", f"{k} '{str(v)[:40]}' tidak ada di data.")
            if k == "region" and not self.scope.allows_region(v):
                raise ToolError("forbidden", f"Anda tidak punya akses ke data region {v}.")
            if k == "brand" and not self.scope.allows_brand(v):
                raise ToolError("forbidden", f"Anda tidak punya akses ke data brand {v}.")
            col = k
            f = f[f[col] == v]
            used[k] = v
        return f, used

    def run(self, name: str, args: dict | None) -> ToolResult:
        args = dict(args or {})
        if name not in TOOL_NAMES:
            raise ToolError("unknown_tool", f"Tool {name} tidak ada.")
        spec = next(t for t in TOOL_SPECS if t["name"] == name)
        extra = set(args) - set(spec["input_schema"]["properties"])
        if extra:
            raise ToolError("bad_arg", f"Argumen tidak dikenal: {', '.join(sorted(extra))}.")
        return getattr(self, "_" + name)(args)

    # -- tools ----------------------------------------------------------------

    def _sales_by(self, a: dict) -> ToolResult:
        dim = self._choice(a.get("dimension"), ["total", *_DIM_ENUM], "dimension", "total")
        period = self._period(a.get("period"))
        metric = self._choice(a.get("metric"), _METRIC_ENUM, "metric", "net_sales")
        f, used = self._filters(a)
        args = {"dimension": dim, "period": period, "metric": metric, **used}
        plabel = fmt.period_label(period, self.months)
        filt = _filt(used)
        what = an.METRICS[metric].split(" (")[0].lower()
        if f.empty:
            return ToolResult("sales_by", args, {"rows": []}, f"Tidak ada transaksi untuk {filt or 'filter ini'} di {plabel}.")
        if dim == "total":
            t = an.totals(f, period)
            val = _metric_total(t, metric)
            mm = an.mom(f) if period == "all" else None
            facts = [val, *[int(m[:4]) for m in self.months]]
            pcts: list[float] = []
            text = f"{_cap(what)}{' ' + filt if filt else ''} {plabel}: {_fmt_metric(val, metric)}."
            table = [{"label": f"{_cap(what)} {plabel}", "value": _fmt_metric(val, metric)}]
            if mm and metric == "net_sales":
                facts += [mm["prev"], mm["curr"]]
                if mm["pct"] is not None:
                    pcts.append(mm["pct"])
                    text += f" {fmt.month_label(mm['curr_month']).split()[0]} {fmt.rupiah_short(mm['curr'])} vs {fmt.month_label(mm['prev_month']).split()[0]} {fmt.rupiah_short(mm['prev'])} ({fmt.pct(mm['pct'], signed=True)})."
                table += [
                    {"label": fmt.month_label(mm["prev_month"]), "value": fmt.rupiah(mm["prev"])},
                    {"label": fmt.month_label(mm["curr_month"]), "value": fmt.rupiah(mm["curr"])},
                ]
            if metric == "net_sales" and t["return_lines"]:
                facts += [t["returns_idr"], t["return_lines"]]
                text += f" Sudah termasuk retur {fmt.rupiah_short(t['returns_idr'])}."
            return ToolResult("sales_by", args, {"total": t, "mom": mm}, text, table, facts, pcts)
        rows = an.breakdown(f, dim, period, metric)
        return self._render_rows("sales_by", args, rows, dim, metric, plabel, filt, limit=MAX_N)

    def _top_bottom(self, a: dict) -> ToolResult:
        dim = self._choice(a.get("dimension"), _DIM_ENUM, "dimension", "region")
        n = self._n(a.get("n"))
        order = self._choice(a.get("order"), ["top", "bottom"], "order", "top")
        period = self._period(a.get("period"))
        metric = self._choice(a.get("metric"), _METRIC_ENUM, "metric", "net_sales")
        f, used = self._filters(a)
        args = {"dimension": dim, "n": n, "order": order, "metric": metric, "period": period, **used}
        rows = an.breakdown(f, dim, period, metric)
        if order == "bottom":
            rows = list(reversed(rows))
        rows = rows[:n]
        res = self._render_rows("top_bottom", args, rows, dim, metric, fmt.period_label(period, self.months), _filt(used), limit=n, heading=f"{'' if n == 1 else str(n) + ' '}{an.DIMENSION_LABELS[dim].lower()} {'tertinggi' if order == 'top' else 'terendah'}")
        res.facts.append(n)
        return res

    def _compare_periods(self, a: dict) -> ToolResult:
        dim = self._choice(a.get("dimension"), ["total", *_DIM_ENUM], "dimension", "total")
        metric = self._choice(a.get("metric"), _METRIC_ENUM, "metric", "net_sales")
        f, used = self._filters(a)
        args = {"dimension": dim, "metric": metric, **used}
        ms = an.months(f)
        if len(ms) < 2:
            return ToolResult("compare_periods", args, {}, "Data hanya punya satu bulan, jadi belum bisa dibandingkan.")
        prev, curr = ms[-2], ms[-1]
        pl, cl = fmt.month_label(prev).split()[0], fmt.month_label(curr).split()[0]
        filt = _filt(used)
        if dim == "total":
            p = _metric_total(an.totals(f, prev), metric)
            c = _metric_total(an.totals(f, curr), metric)
            pct = an._pct(c, p)
            arah = "naik" if c >= p else "turun"
            text = f"{_cap(an.METRICS[metric].split(' (')[0].lower())}{' ' + filt if filt else ''}: {cl} {_fmt_metric(c, metric)}, {arah} {fmt.pct(abs(pct)) if pct is not None else '-'} dari {pl} ({_fmt_metric(p, metric)})."
            table = [{"label": fmt.month_label(prev), "value": _fmt_metric(p, metric, full=True)}, {"label": fmt.month_label(curr), "value": _fmt_metric(c, metric, full=True)}, {"label": "Perubahan", "value": fmt.pct(pct, signed=True)}]
            return ToolResult("compare_periods", args, {"prev": p, "curr": c, "pct": pct}, text, table, [p, c, c - p, int(curr[:4])], [pct] if pct is not None else [])
        rows = [r for r in an.breakdown(f, dim, "all", metric) if r.get("mom_pct") is not None or r.get("curr")]
        rows.sort(key=lambda r: (r.get("mom_pct") is None, -(r.get("mom_pct") or 0)))
        facts: list[float] = [int(curr[:4])]
        pcts: list[float] = []
        table = []
        lines = []
        for r in rows[:MAX_N]:
            facts += [r["prev"], r["curr"], r["change"]]
            if r["mom_pct"] is not None:
                pcts.append(r["mom_pct"])
            name = self._label(dim, r["key"])
            lines.append(f"{name} {fmt.pct(r['mom_pct'], signed=True)}")
            table.append({"label": name, "value": f"{_fmt_metric(r['prev'], metric)} -> {_fmt_metric(r['curr'], metric)} ({fmt.pct(r['mom_pct'], signed=True)})"})
        text = f"Perubahan {cl} vs {pl} per {an.DIMENSION_LABELS[dim].lower()}{' (' + filt + ')' if filt else ''}, dari naik terbesar: " + "; ".join(lines) + "."
        return ToolResult("compare_periods", args, {"rows": rows[:MAX_N]}, text, table, facts, pcts)

    def _weakest_outlets(self, a: dict) -> ToolResult:
        period = self._period(a.get("period"))
        n = self._n(a.get("n"))
        args = {"period": period, "n": n}
        weak = an.weakest_outlets(self.fact, self.dim_outlet, period, n)
        if not weak:
            return ToolResult("weakest_outlets", args, {"rows": []}, "Tidak ada outlet di bawah median outlet sejenis dalam akses Anda.")
        facts: list[float] = [n, len(weak), *range(1, len(weak) + 1), *[int(m[:4]) for m in self.months]]
        pcts: list[float] = []
        lines, table = [], []
        for w in weak:
            facts += [w.net_sales_idr, w.peer_median_idr, w.invoices, w.peer_median_invoices, w.index_pct, *w.month_values.values()]
            pcts += [w.index_pct] + ([w.mom_pct] if w.mom_pct is not None else [])
            lines.append(f"{w.rank}) {w.outlet_name} ({w.outlet_id}, {w.branch}): {w.reason}")
            table.append({"label": f"{w.outlet_name} ({w.outlet_id})", "value": f"{fmt.rupiah(w.net_sales_idr)}, {fmt.pct(w.index_pct, 0)} dari median {w.outlet_type}"})
        text = f"{len(weak)} outlet terlemah {fmt.period_label(period, self.months)} dibanding median outlet bertipe sama: " + " ".join(lines)
        notes = sorted({n for w in weak for n in w.notes if "di luar urutan" in n})
        if notes:
            text += " Catatan data: " + notes[0]
        return ToolResult("weakest_outlets", args, {"rows": [w.__dict__ for w in weak]}, text, table, facts, pcts)

    def _outlet_detail(self, a: dict) -> ToolResult:
        oid = str(a.get("outlet_id", "")).strip().upper()
        if not OUTLET_ID_RE.match(oid):
            raise ToolError("bad_arg", "outlet_id harus berformat OUT diikuti angka, misalnya OUT1003.")
        d = an.outlet_detail(self.fact, self.dim_outlet, oid)
        if d is None:
            raise ToolError("not_found", f"Outlet {oid} tidak ditemukan dalam data yang bisa Anda akses.")
        args = {"outlet_id": oid}
        months = list(d["by_month"].items())
        facts: list[float] = [d["net_sales_idr"], d["invoices"], d["qty_carton"], d["returns_idr"], *[v for _, v in months], *[s["net_sales_idr"] for s in d["top_skus"]], *[int(m[:4]) for m, _ in months]]
        pcts = [d["mom_pct"]] if d["mom_pct"] is not None else []
        # Notes are generated from the data (e.g. returned vs bought cartons); their numbers are facts too.
        facts += [n.value for note in d["notes"] for n in guard.find_numbers(note)]
        bulan = ", ".join(f"{fmt.month_label(m).split()[0]} {fmt.rupiah_short(v)}" for m, v in months)
        text = (
            f"{d['outlet_name']} ({oid}), {d['outlet_type']} di {d['branch']}, {d['region']}: net {fmt.rupiah_short(d['net_sales_idr'])} "
            f"dari {d['invoices']} invoice ({bulan}). Salesman: {', '.join(d['salesmen']) or '-'}."
        )
        if d["top_skus"]:
            text += " SKU terbesar: " + ", ".join(s["sku"] for s in d["top_skus"]) + "."
        if d["notes"]:
            text += " Catatan: " + " ".join(d["notes"])
        table = [{"label": "Net setelah retur", "value": fmt.rupiah(d["net_sales_idr"])}, {"label": "Invoice", "value": str(d["invoices"])}] + [{"label": fmt.month_label(m), "value": fmt.rupiah(v)} for m, v in months]
        return ToolResult("outlet_detail", args, d, text, table, facts, pcts)

    def _find_outlet(self, a: dict) -> ToolResult:
        name = str(a.get("name", ""))[:80].strip().lower()
        if len(name) < 3:
            raise ToolError("bad_arg", "Nama outlet terlalu pendek.")
        allowed = set(self.fact["outlet_id"])
        d = self.dim_outlet[self.dim_outlet["outlet_id"].isin(allowed)]
        m = d[d["outlet_name"].str.lower().str.contains(re.escape(name))]
        rows = [{"outlet_id": r.outlet_id, "outlet_name": r.outlet_name, "branch": r.branch, "outlet_type": r.outlet_type} for r in m.itertuples()]
        args = {"name": name}
        if not rows:
            return ToolResult("find_outlet", args, {"rows": []}, f"Tidak ada outlet bernama '{name}' dalam akses Anda.")
        text = "Outlet yang cocok: " + "; ".join(f"{r['outlet_name']} {r['outlet_id']} ({r['outlet_type']}, {r['branch']})" for r in rows) + "."
        return ToolResult("find_outlet", args, {"rows": rows}, text, [{"label": r["outlet_id"], "value": f"{r['outlet_name']}, {r['branch']}"} for r in rows], [len(rows)])

    def _data_quality_summary(self, a: dict) -> ToolResult:
        from dk_sales.rules import ACTION_ID, RULES

        st = self.ds.result.rule_stats
        m = self.ds.result.meta
        rows = [{"rule_id": r.rule_id, "title": r.title, "rows": st[r.rule_id]["rows"], "action": ACTION_ID[r.action]} for r in RULES if st[r.rule_id]["rows"]]
        facts: list[float] = [m["rows_in"], m["rows_clean"], m["rows_quarantined"], len(rows), *[r["rows"] for r in rows]]
        text = (
            f"Dari {m['rows_in']} baris, {m['rows_clean']} bersih dan {m['rows_quarantined']} dikarantina. "
            f"{len(rows)} aturan menemukan masalah: "
            + "; ".join(f"{r['rule_id']} {r['title'].split(' (')[0].lower()} {r['rows']} baris ({r['action']})" for r in rows)
            + "."
        )
        table = [{"label": f"{r['rule_id']} {r['title']}", "value": f"{r['rows']} baris, {r['action']}"} for r in rows]
        return ToolResult("data_quality_summary", {}, {"meta": m, "rows": rows}, text, table, facts)

    # -- helpers --------------------------------------------------------------

    def _label(self, dim: str, key) -> str:
        if dim == "outlet":
            d = self.dim_outlet.set_index("outlet_id")
            return f"{d.at[key, 'outlet_name']} ({key})" if key in d.index else str(key)
        return str(key)

    def _render_rows(self, tool, args, rows, dim, metric, plabel, filt, limit, heading=None) -> ToolResult:
        rows = rows[:limit]
        facts: list[float] = [int(m[:4]) for m in self.months]
        pcts: list[float] = []
        parts, table = [], []
        for r in rows:
            facts += [r["value"]] + [r[k] for k in ("prev", "curr", "change") if k in r]
            if r.get("share_pct") is not None:
                pcts.append(r["share_pct"])
            if r.get("mom_pct") is not None:
                pcts.append(r["mom_pct"])
            name = self._label(dim, r["key"])
            s = f"{name} {_fmt_metric(r['value'], metric)}"
            if r.get("share_pct") is not None and metric != "invoices":
                s += f" ({fmt.pct(r['share_pct'])})"
            parts.append(s)
            table.append({"label": name, "value": _fmt_metric(r["value"], metric, full=True)})
        head = heading or f"{an.METRICS[metric].split(' (')[0]} per {an.DIMENSION_LABELS[dim].lower()}"
        text = f"{_cap(head)} {plabel}{' (' + filt + ')' if filt else ''}: " + "; ".join(parts) + "." if parts else f"Tidak ada data untuk {head} {plabel}."
        return ToolResult(tool, args, {"rows": rows}, text, table, facts, pcts)


def _metric_total(t: dict, metric: str) -> int:
    return {"net_sales": t["net_sales_idr"], "gross_sales": t["gross_sales_idr"], "qty_carton": t["qty_carton"], "invoices": t["invoices"]}[metric]


def _fmt_metric(v, metric: str, full: bool = False) -> str:
    if metric in ("net_sales", "gross_sales"):
        return fmt.rupiah(v) if full else fmt.rupiah_short(v)
    unit = "karton" if metric == "qty_carton" else "invoice"
    return f"{int(v):,}".replace(",", ".") + f" {unit}"


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def known_values(dataset) -> dict:
    """Values the intent parser may recognise (from the full dataset; access is checked in the tools)."""
    f = dataset.fact
    return {
        "region": sorted(f["region"].unique()),
        "brand": sorted(f["brand"].unique()),
        "branch": sorted(f["branch"].unique()),
        "salesman": sorted(s for s in f["salesman"].unique() if s),
        "outlet_type": sorted(f["outlet_type"].unique()),
        "months": an.months(f),
        "canonical_regions": config.CANONICAL_REGIONS,
    }

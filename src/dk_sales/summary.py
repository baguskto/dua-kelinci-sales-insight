"""One-paragraph Telegram summary for a sales manager, built only from computed numbers."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from dk_sales import analytics as an
from dk_sales import fmt

TELEGRAM_MAX_CHARS = 1000


@dataclass
class Summary:
    text: str
    facts: list[float] = field(default_factory=list)
    pct_facts: list[float] = field(default_factory=list)
    source: str = "template"
    fallback_reason: str | None = None


def build(fact: pd.DataFrame, dim_outlet: pd.DataFrame, scope_label: str = "", period: str = "all") -> Summary:
    facts: list[float] = []
    pcts: list[float] = []
    ms = an.months(fact)
    if fact.empty:
        return Summary(text="Belum ada data penjualan untuk diringkas.")
    label = fmt.period_label(period, ms)
    facts += [int(m[:4]) for m in ms]
    t = an.totals(fact, period)
    facts.append(t["net_sales_idr"])
    head = f"Ringkasan penjualan Dua Kelinci{(' ' + scope_label) if scope_label else ''}, {label} (net setelah retur): total {fmt.rupiah_short(t['net_sales_idr'])}"
    parts = [head]

    mm = an.mom(fact) if period == "all" else None
    if mm and mm["pct"] is not None:
        facts += [mm["curr"], mm["prev"]]
        pcts.append(mm["pct"])
        arah = "naik" if mm["change"] >= 0 else "turun"
        parts[-1] += (
            f", {fmt.month_label(mm['curr_month'], long=True).split()[0]} {fmt.rupiah_short(mm['curr'])}, "
            f"{arah} {fmt.pct(abs(mm['pct']))} dari {fmt.month_label(mm['prev_month'], long=True).split()[0]}"
        )
        if mm["per_day_pct"] is not None:
            facts += [mm["curr_trading_days"], mm["prev_trading_days"]]
            pcts.append(mm["per_day_pct"])
            parts[-1] += (
                f", tapi per hari kerja {fmt.pct(mm['per_day_pct'], 1, signed=True)} karena "
                f"{fmt.month_label(mm['curr_month'], long=True).split()[0]} punya {mm['curr_trading_days']} hari kerja "
                f"vs {mm['prev_trading_days']}"
            )
        parts[-1] += "."
    else:
        parts[-1] += "."

    reg = an.breakdown(fact, "region", period)
    if len(reg) > 1:
        top, low = reg[0], reg[-1]
        facts += [top["value"], low["value"]]
        s = f"Region terbesar {top['key']} {fmt.rupiah_short(top['value'])}, terkecil {low['key']} {fmt.rupiah_short(low['value'])}"
        movers = [r for r in reg if r.get("mom_pct") is not None]
        if period == "all" and len(movers) > 1:
            up = max(movers, key=lambda r: r["mom_pct"])
            down = min(movers, key=lambda r: r["mom_pct"])
            pcts += [up["mom_pct"], down["mom_pct"]]
            if up["mom_pct"] > 0:
                s += f"; {up['key']} tumbuh paling cepat ({fmt.pct(up['mom_pct'], signed=True)})"
            if down["mom_pct"] < 0:
                s += f", {down['key']} turun paling dalam ({fmt.pct(down['mom_pct'], signed=True)})"
        parts.append(s + ".")
    else:
        # A single region in scope: break it down by branch instead.
        brs = an.breakdown(fact, "branch", period)
        if len(brs) > 1:
            facts += [brs[0]["value"], brs[-1]["value"]]
            parts.append(
                f"Cabang terbesar {brs[0]['key']} {fmt.rupiah_short(brs[0]['value'])}, terkecil {brs[-1]['key']} {fmt.rupiah_short(brs[-1]['value'])}."
            )

    br = an.breakdown(fact, "brand", period)
    if len(br) > 1:
        facts += [br[0]["value"], br[-1]["value"]]
        parts.append(f"Brand terbesar {br[0]['key']} {fmt.rupiah_short(br[0]['value'])}, terkecil {br[-1]['key']} {fmt.rupiah_short(br[-1]['value'])}.")

    weak = an.weakest_outlets(fact, dim_outlet, period, n=5)
    if weak:
        facts.append(len(weak))
        names = ", ".join(f"{w.outlet_name} ({w.outlet_id}, {w.branch})" for w in weak)
        parts.append(f"{len(weak)} outlet terlemah dibanding outlet sejenis: {names}.")
        flagged = [w for w in weak if any("di luar urutan" in n for n in w.notes)]
        if flagged:
            facts.append(len(flagged))
            if len(flagged) == len(weak):
                parts.append("Semuanya tercatat dengan nomor invoice di luar urutan, jadi cek dulu inputnya ke admin, lalu jadwalkan kunjungan.")
            else:
                parts.append(f"{len(flagged)} di antaranya tercatat dengan nomor invoice di luar urutan; cek inputnya ke admin.")
        else:
            w = weak[0]
            facts.append(w.index_pct)
            parts.append(f"Aksi utama: kunjungi {w.outlet_name} ({w.outlet_id}), penjualannya {fmt.pct(w.index_pct, 0)} dari median {w.outlet_type}.")
            pcts.append(w.index_pct)
    if t["return_lines"]:
        facts += [t["returns_idr"], t["return_lines"]]
        parts.append(f"Retur {t['return_lines']} baris senilai {fmt.rupiah_short(abs(t['returns_idr']))} sudah dikurangkan.")
    text = " ".join(parts)
    return Summary(text=text, facts=facts, pct_facts=pcts)

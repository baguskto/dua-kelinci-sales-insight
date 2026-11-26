"""One-paragraph Telegram summary for a sales manager, built only from computed numbers.

Written in English like the dashboard. Every number in the text is listed in ``facts`` or
``pct_facts`` so guard.check(..., lang="en") can verify it, including after an LLM rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from dk_sales import analytics as an
from dk_sales import fmt

TELEGRAM_MAX_CHARS = 1000
TARGET_CHARS = 450
LANG = "en"


@dataclass
class Summary:
    text: str
    facts: list[float] = field(default_factory=list)
    pct_facts: list[float] = field(default_factory=list)
    source: str = "template"
    fallback_reason: str | None = None
    lang: str = LANG


def build(fact: pd.DataFrame, dim_outlet: pd.DataFrame, scope_label: str = "", period: str = "all") -> Summary:
    """Insight first: the month-on-month change and whether one outlet explains it, falling regions and
    brands, then the outlets to visit. One plain paragraph."""
    if fact.empty:
        return Summary(text="No sales data to summarise yet.")
    facts: list[float] = []
    pcts: list[float] = []
    who = f"Dua Kelinci{(' ' + scope_label) if scope_label else ''}"
    st = an.story(fact, dim_outlet, period)
    parts: list[str] = []
    if st:
        cm, pm = fmt.mon(st["curr_month"]), fmt.mon(st["prev_month"])
        facts += [st["curr"], st["prev_trading_days"], st["curr_trading_days"]]
        pcts += [st["pct"], st["per_day_pct"]]
        s = f"{who}, {cm} vs {pm}: net sales {fmt.rpm(st['curr'])} ({fmt.spct(st['pct'])})"
        top, ex = st["top"], st["ex_top"]
        if top and ex and ex["pct"] is not None and (ex["change"] >= 0) != (st["change"] >= 0):
            facts.append(top["change"])
            pcts.append(ex["pct"])
            s += f", but without {top['outlet_name']} ({fmt.rpm(top['change'], True)}) {'down' if ex['change'] < 0 else 'up'} {fmt.epct(abs(ex['pct']))}"
        s += f"; per trading day {fmt.spct(st['per_day_pct'])}."
        parts.append(s)
        if st["regions_total"] > 1 and st["worst_region"]:
            w = st["worst_region"]
            facts += [st["regions_down"], st["regions_total"], w["change"]]
            parts.append(f"{st['regions_down']} of {st['regions_total']} regions fell, most in {fmt.region(w['key'])} {fmt.rpm(w['change'], True)}")
            if st["worst_brand"] and st["worst_brand"]["pct"] is not None:
                b = st["worst_brand"]
                pcts.append(b["pct"])
                parts[-1] += f"; brand {b['key']} {fmt.spct(b['pct'])}"
            parts[-1] += "."
    else:
        t = an.totals(fact, period)
        facts.append(t["net_sales_idr"])
        parts.append(f"{who}, {fmt.period_en(period, an.months(fact))}: net sales {fmt.rpm(t['net_sales_idr'])}.")

    weak = an.weakest_outlets(fact, dim_outlet, period, n=5)
    if weak:
        facts.append(len(weak))
        names = ", ".join(f"{w.outlet_name} ({w.outlet_id})" for w in weak)
        s = f"{len(weak)} outlets to visit: {names}"
        flagged = [w for w in weak if any("di luar urutan" in n for n in w.notes)]
        if flagged and len(flagged) == len(weak):
            s += "; all come from out-of-sequence invoices, check the data first"
        elif flagged:
            facts.append(len(flagged))
            s += f"; {len(flagged)} come from out-of-sequence invoices, check the data first"
        parts.append(s + ".")
    facts += [int(m[:4]) for m in an.months(fact)]
    return Summary(text=" ".join(parts), facts=facts, pct_facts=pcts)

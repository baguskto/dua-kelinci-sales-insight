from __future__ import annotations

import pytest

from dk_sales import analytics as an
from dk_sales import config, fmt, guard, summary
from dk_sales.web.dataset import load_bytes


@pytest.fixture(scope="module")
def ds():
    return load_bytes("sales.csv", (config.ROOT / "sales.csv").read_bytes(), 10**8, 10**7)


def test_totals_and_mom(ds):
    t = an.totals(ds.fact)
    assert t["net_sales_idr"] == 1_725_966_000
    assert t["returns_idr"] == -528_000
    assert t["net_sales_before_returns_idr"] == 1_726_494_000
    m = an.mom(ds.fact)
    assert (m["prev"], m["curr"], m["pct"]) == (847_517_400, 878_448_600, 3.65)


def test_breakdown_region_sorted_and_shares_sum(ds):
    rows = an.breakdown(ds.fact, "region")
    assert [r["key"] for r in rows][:2] == ["Jabodetabek", "Sumatera"]
    assert sum(r["value"] for r in rows) == 1_725_966_000
    assert abs(sum(r["share_pct"] for r in rows) - 100) < 0.05
    jt = next(r for r in rows if r["key"] == "Jawa Timur")
    assert jt["mom_pct"] == 92.36


def test_period_filter(ds):
    assert an.totals(ds.fact, "2026-10")["net_sales_idr"] == 878_448_600
    assert an.valid_periods(ds.fact) == ["all", "2026-09", "2026-10"]


def test_weakest_outlets_are_the_late_block_outlets(ds):
    weak = an.weakest_outlets(ds.fact, ds.dim_outlet, "all", 5)
    assert [w.outlet_id for w in weak] == ["OUT1003", "OUT1026", "OUT1045", "OUT1042", "OUT1035"]
    assert all(w.index_pct < 10 for w in weak)
    assert all(any("di luar urutan" in n for n in w.notes) for w in weak)
    assert any("data master ganda" in n for n in weak[0].notes)


def test_weakest_compares_within_outlet_type(ds):
    weak = an.weakest_outlets(ds.fact, ds.dim_outlet, "all", 20)
    by_type = {w.outlet_type for w in weak}
    assert "Warung" in by_type
    for w in weak:
        assert w.index_pct < 100
        assert w.peer_median_idr > 0


def test_weakest_handles_outlet_without_orders_in_period(ds):
    sep = an.weakest_outlets(ds.fact, ds.dim_outlet, "2026-09", 5)
    assert sep[0].outlet_id == "OUT1047" and sep[0].net_sales_idr == 0
    assert sep[0].action.startswith("Belum ada order")


def test_scope_limits_rows(ds):
    s = an.Scope(regions=frozenset({"Jawa Barat"}))
    f = s.apply(ds.fact)
    assert set(f["region"]) == {"Jawa Barat"}
    weak = an.weakest_outlets(f, ds.dim_outlet, "all", 5)
    assert all(w.region == "Jawa Barat" for w in weak)


def test_outlet_detail_return_note(ds):
    d = an.outlet_detail(ds.fact, ds.dim_outlet, "OUT1049")
    assert d["returns_idr"] == -528_000
    assert "melebihi pembelian 1 karton" in d["notes"][0]
    assert an.outlet_detail(ds.fact, ds.dim_outlet, "OUT9999") is None


def test_fmt():
    assert fmt.rupiah(1725966000) == "Rp1.725.966.000"
    assert fmt.rupiah(-528000) == "-Rp528.000"
    assert fmt.rupiah_short(1725966000) == "Rp1,73 miliar"
    assert fmt.rupiah_short(878448600) == "Rp878,4 juta"
    assert fmt.rupiah_short(98_000_000) == "Rp98 juta"
    assert fmt.rupiah_short(528000) == "Rp528 ribu"
    assert fmt.pct(3.65, 1, True) == "+3,6%" or fmt.pct(3.65, 1, True) == "+3,7%"
    assert fmt.period_label("all", ["2026-09", "2026-10"]) == "Sep-Okt 2026"


def test_summary_is_short_grounded_plain_text(ds):
    s = summary.build(ds.fact, ds.dim_outlet)
    assert len(s.text) <= summary.TELEGRAM_MAX_CHARS
    assert "\n" not in s.text and "*" not in s.text and "|" not in s.text
    for must in ["Rp1,73 miliar", "Jabodetabek", "Kalimantan", "Kacang Dua Kelinci", "Roni", "OUT1003", "naik 3,6%"]:
        assert must in s.text
    assert guard.check(s.text, s.facts, s.pct_facts).ok


def test_summary_scoped(ds):
    s = summary.build(an.Scope(regions=frozenset({"Jawa Barat"})).apply(ds.fact), ds.dim_outlet, "Region Jawa Barat")
    assert "Jabodetabek" not in s.text and "Cabang terbesar" in s.text
    assert guard.check(s.text, s.facts, s.pct_facts).ok


@pytest.mark.parametrize(
    "text,ok",
    [
        ("Total Rp1,73 miliar.", True),
        ("Total Rp1,8 miliar.", False),
        ("Okt naik 3,6%.", True),
        ("Okt naik 4%.", True),
        ("Okt naik 5%.", False),
        ("Total Rp1.725.966.000", True),
        ("Total Rp1.725.966.001", False),
        ("OUT1003 dan INV500813 dan DQ-06 bukan angka", True),
        ("Kacang Kulit 250g tidak dihitung", True),
        ("Ada 7 outlet", False),
        ("Rp 1,73 M", True),
    ],
)
def test_guard_cases(text, ok):
    assert guard.check(text, [1_725_966_000], [3.65]).ok is ok


def test_guard_parse_numbers():
    assert guard.parse_number("1.234.567") == (1234567.0, 0)
    assert guard.parse_number("878,4") == (878.4, 1)
    assert guard.parse_number("3.6") == (3.6, 1)
    assert guard.parse_number("1,234,567") == (1234567.0, 0)
    assert guard.parse_number("-13,9") == (-13.9, 1)


def test_cumulative_runs_by_day_and_ends_at_month_totals(ds):
    s = an.cumulative(ds.fact)
    assert [c["month"] for c in s] == ["2026-09", "2026-10"]
    sep, okt = s
    assert (len(sep["values"]), len(okt["values"])) == (30, 31)
    assert (sep["values"][-1], okt["values"][-1]) == (847_517_400, 878_448_600)
    assert sum(okt["daily"]) == okt["total"] == okt["values"][-1]
    # A day without sales carries the previous total (4 Oktober is a Sunday without orders).
    assert okt["daily"][3] == 0 and okt["values"][3] == okt["values"][2]


def test_cumulative_keeps_calendar_length_when_a_filter_has_no_sales_at_month_end(ds):
    roni = an.cumulative(ds.fact[ds.fact["brand"] == "Roni"], ds.fact["date"].max())
    assert len(roni[0]["values"]) == 30  # September has 30 days even if Roni has no sale on the 29th and 30th


def test_cumulative_insight_sentences(ds):
    assert an.cumulative_insight(an.cumulative(ds.fact)) == (
        "Sampai tanggal 30 Oktober masih Rp6,9 juta di bawah September; tanggal 31, yang tidak ada di September, "
        "membuat Oktober menutup bulan Rp30,9 juta di atas September."
    )
    end = ds.fact["date"].max()
    jatim = an.cumulative_insight(an.cumulative(ds.fact[ds.fact["region"] == "Jawa Timur"], end))
    assert jatim.startswith("Oktober selalu di atas September sejak tanggal 1")
    jabar = an.cumulative_insight(an.cumulative(ds.fact[ds.fact["region"] == "Jawa Barat"], end))
    assert jabar == "Oktober tertinggal dari September sepanjang bulan dan menutup bulan Rp23,2 juta di bawah September."
    jabo = an.cumulative_insight(an.cumulative(ds.fact[ds.fact["region"] == "Jabodetabek"], end))
    assert jabo.startswith("Oktober menyalip September pada tanggal 13")
    assert an.cumulative_insight([]) == ""


def test_short_headline(ds):
    weak = an.weakest_outlets(ds.fact, ds.dim_outlet, "all", 5)
    assert an.short_headline(ds.fact, weak) == "Oktober naik 3,6% · 5 outlet perlu dikunjungi"
    jabar = ds.fact[ds.fact["region"] == "Jawa Barat"]
    assert an.short_headline(jabar, []).startswith("Oktober turun 13,9%")

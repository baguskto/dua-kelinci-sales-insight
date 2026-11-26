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
    assert (m["prev_trading_days"], m["curr_trading_days"]) == (26, 27)
    assert m["per_day_pct"] == -0.19
    assert an.trading_days("2026-09") == 26 and an.trading_days("2026-10") == 27


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


def test_summary_leads_with_the_insight_and_stays_short(ds):
    s = summary.build(ds.fact, ds.dim_outlet)
    assert len(s.text) <= summary.TARGET_CHARS
    assert "\n" not in s.text and "*" not in s.text and "|" not in s.text
    assert s.text.startswith("Dua Kelinci, Okt vs Sep: net Rp 878,4 jt (+3,6%), tapi tanpa Grosir Lancar Jaya (+Rp 47,7 jt) turun 2,0%")
    for must in ["per hari kerja \u22120,2%", "4 dari 6 region turun", "Jawa Barat \u2212Rp 23,2 jt", "Pilus \u221212,2%", "OUT1003", "OUT1035", "di luar urutan"]:
        assert must in s.text
    assert guard.check(s.text, s.facts, s.pct_facts).ok


def test_summary_scoped(ds):
    s = summary.build(an.Scope(regions=frozenset({"Jawa Barat"})).apply(ds.fact), ds.dim_outlet, "Region Jawa Barat")
    assert "Jabodetabek" not in s.text and s.text.startswith("Dua Kelinci Region Jawa Barat, Okt vs Sep: net Rp 143,9 jt (\u221213,9%)")
    assert guard.check(s.text, s.facts, s.pct_facts).ok
    sep = summary.build(ds.fact, ds.dim_outlet, "", "2026-09")
    assert sep.text.startswith("Dua Kelinci, September 2026: net Rp 847,5 jt.") and guard.check(sep.text, sep.facts, sep.pct_facts).ok


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


def test_story_matches_the_month_on_month_numbers(ds):
    st = an.story(ds.fact, ds.dim_outlet)
    assert (st["prev_month"], st["curr_month"]) == ("2026-09", "2026-10")
    assert (st["prev"], st["curr"], st["change"], st["pct"]) == (847_517_400, 878_448_600, 30_931_200, 3.65)
    assert (st["prev_trading_days"], st["curr_trading_days"], st["per_day_pct"]) == (26, 27, -0.19)
    assert (st["regions_down"], st["regions_total"]) == (4, 6)
    assert st["worst_region"]["key"] == "Jawa Barat" and st["worst_region"]["change"] == -23_181_700
    assert st["worst_brand"]["key"] == "Pilus" and st["worst_brand"]["change"] == -4_659_900
    assert (st["cartons_prev"], st["cartons_curr"]) == (4_318, 4_427)


def test_top_contributor_and_growth_without_it(ds):
    st = an.story(ds.fact, ds.dim_outlet)
    top = st["top"]
    assert (top["outlet_id"], top["outlet_name"], top["region"]) == ("OUT1036", "Grosir Lancar Jaya", "Jawa Timur")
    assert (top["prev"], top["curr"], top["change"]) == (28_296_400, 75_962_600, 47_666_200)
    assert (top["invoices_prev"], top["invoices_curr"], top["cartons_prev"], top["cartons_curr"]) == (9, 18, 143, 415)
    assert fmt.pct(top["share_of_curr_pct"]) == "8,6%"
    assert top["share_of_change_pct"] > 100  # one outlet adds more than the whole business
    assert st["ex_top"] == {"prev": 819_221_000, "curr": 802_486_000, "change": -16_735_000, "pct": -2.04}


def test_top_contributor_follows_the_direction_of_the_total(ds):
    # Jawa Barat fell, so its top contributor is the outlet that fell most, and without it the region grew.
    st = an.story(ds.fact[ds.fact["region"] == "Jawa Barat"], ds.dim_outlet)
    assert st["change"] < 0 and st["top"]["change"] < 0
    assert st["ex_top"]["change"] > 0


def test_bridge_steps_sum_exactly_to_the_total_change(ds):
    end = ds.fact["date"].max()
    for f in (ds.fact, ds.fact[ds.fact["region"] == "Jawa Timur"], ds.fact[ds.fact["brand"] == "Sukro"], ds.fact[ds.fact["region"] == "Jawa Barat"]):
        st = an.story(f, ds.dim_outlet)
        steps = st["bridge"]
        assert sum(s["change"] for s in steps) == st["change"]
        assert steps[0]["start"] == st["prev"] and steps[-1]["end"] == st["curr"]
        assert all(a["end"] == b["start"] for a, b in zip(steps, steps[1:], strict=False))
    assert end is not None


def test_bridge_splits_the_top_outlet_out_of_its_region(ds):
    st = an.story(ds.fact, ds.dim_outlet)
    by_key = {s["key"]: s["change"] for s in st["bridge"]}
    assert by_key["Grosir Lancar Jaya"] == 47_666_200
    assert by_key["Jawa Timur"] == 66_775_700 - 47_666_200
    assert [s["key"] for s in st["bridge"]][:3] == ["Grosir Lancar Jaya", "Jawa Timur", "Jabodetabek"]


def test_story_needs_a_previous_month(ds):
    assert an.story(ds.fact, ds.dim_outlet, "2026-09") is None
    assert an.compare_months(ds.fact, "2026-10") == ("2026-09", "2026-10")
    assert an.story(ds.fact[ds.fact["year_month"] == "2026-10"], ds.dim_outlet) is None


def test_dashboard_number_format():
    assert fmt.jt(878_448_600) == "Rp 878,4 jt"
    assert fmt.jt(-23_181_700, signed=True) == "\u2212Rp 23,2 jt"
    assert fmt.jt(47_666_200, signed=True) == "+Rp 47,7 jt"
    assert fmt.jt(1_725_966_000) == "Rp 1.726,0 jt"
    assert fmt.spct(-0.19) == "\u22120,2%" and fmt.spct(3.65) == "+3,6%" and fmt.spct(0.01) == "0,0%"

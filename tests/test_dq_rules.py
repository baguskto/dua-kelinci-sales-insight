"""One test per DQ rule: the count on the real file plus the behaviour on a small synthetic frame."""

from __future__ import annotations

import pandas as pd
import pytest

from dk_sales.clean import ContractError, clean
from dk_sales.rules import RULES
from tests.helpers import rows


def log_for(result, rule_id):
    return result.dq_log[result.dq_log["rule_id"] == rule_id]


def test_every_rule_has_a_test_below():
    import tests.test_dq_rules as me

    names = {n for n in dir(me) if n.startswith("test_dq")}
    for r in RULES:
        assert f"test_dq{r.rule_id[3:]}" in {n[:9] for n in names}, f"missing test for {r.rule_id}"


def test_dq01_missing_column_rejected():
    df = rows({}).drop(columns=["net_sales_idr"])
    with pytest.raises(ContractError) as e:
        clean(df)
    assert "net_sales_idr" in e.value.details["missing"]


def test_dq01_headers_normalised_and_extra_ignored(build):
    df = rows({})
    df.columns = [c.upper() + " " for c in df.columns]
    df["Catatan"] = "x"
    r = clean(df)
    assert len(r.lines) == 1
    assert r.meta["ignored_columns"] == ["catatan"]
    assert build.result.rule_stats["DQ-01"]["rows"] == 0


def test_dq02_bad_values_quarantined(build):
    df = rows({}, {"date": "31-31-2026", "invoice_no": "INV500002"}, {"qty_carton": "dua", "invoice_no": "INV500003"}, {"invoice_no": "X-1"})
    r = clean(df)
    assert len(r.lines) == 1
    assert set(r.quarantine["rule_id"]) == {"DQ-02"}
    assert len(r.quarantine) == 3
    assert build.result.rule_stats["DQ-02"]["rows"] == 0


def test_dq02_accepts_dd_mm_yyyy_and_excel_float():
    r = clean(rows({"date": "01/09/2026", "qty_carton": "2.0"}))
    assert r.lines.loc[0, "date"] == pd.Timestamp("2026-09-01")
    assert r.lines.loc[0, "qty_carton"] == 2


def test_dq03_region_variants(build):
    assert build.result.rule_stats["DQ-03"]["rows"] == 10
    lg = log_for(build.result, "DQ-03")
    assert dict(lg["before"].value_counts()) == {"Jabar": 4, "JAWA BARAT": 4, "JABODETABEK": 1, "JAWA TIMUR": 1}
    assert set(build.tables["fact_sales_line"]["region"]) == {"Jabodetabek", "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Sumatera", "Kalimantan"}
    r = clean(rows({"region": "jateng", "branch": "Solo"}))
    assert r.lines.loc[0, "region"] == "Jawa Tengah"


def test_dq03_unknown_region_taken_from_branch():
    r = clean(rows({}, {"region": "Jkt Raya", "invoice_no": "INV500002"}))
    assert r.lines.loc[1, "region"] == "Jabodetabek"
    assert log_for(r, "DQ-03")["action"].tolist() == ["inferred"]


def test_dq04_trailing_spaces(build):
    lg = log_for(build.result, "DQ-04")
    assert len(lg) == 4
    assert set(lg["column"]) == {"outlet_name"}
    assert set(lg["before"]) == {"'Grosir Berkah '", "'Toko Murah Meriah '", "'Toko Sumber Rejeki '"}
    assert not build.tables["dim_outlet"]["outlet_name"].str.endswith(" ").any()


def test_dq05_salesman_inferred_from_invoice(build, fact):
    assert build.result.rule_stats["DQ-05"]["rows"] == 5
    assert build.result.rule_stats["DQ-05"]["remaining"] == 0
    assert (fact["salesman"] != "").all()
    assert fact["dq_salesman_inferred"].sum() == 5
    assert set(log_for(build.result, "DQ-05")["action"]) == {"inferred"}


def test_dq05_without_evidence_stays_blank_and_flagged():
    df = rows(
        {"invoice_no": "INV500001", "salesman": "", "outlet_id": "OUT9"},
        {"invoice_no": "INV500002", "salesman": "Andi", "outlet_id": "OUT9", "sku": "X 1g"},
        {"invoice_no": "INV500003", "salesman": "Budi", "outlet_id": "OUT9", "sku": "Y 1g"},
    )
    r = clean(df)
    assert r.lines.loc[0, "salesman"] == ""
    assert log_for(r, "DQ-05")["action"].tolist() == ["flagged"]
    # Outlet with a single salesman is enough evidence.
    r2 = clean(rows({"invoice_no": "INV500001", "salesman": ""}, {"invoice_no": "INV500002", "sku": "X 1g"}))
    assert r2.lines.loc[0, "salesman"] == "Andi"


def test_dq06_exact_duplicates_quarantined(build):
    q = build.result.quarantine
    assert len(q) == 3
    assert set(q["rule_id"]) == {"DQ-06"}
    assert sorted(q["invoice_no"]) == ["INV500201", "INV500386", "INV500791"]
    assert sorted(q["raw_row_id"]) == [495, 913, 1873]


def test_dq07_return_kept_as_return(fact):
    r = fact[fact["is_return"]]
    assert len(r) == 1
    row = r.iloc[0]
    assert row["invoice_no"] == "RTR900001"
    assert row["qty_carton"] == -2 and row["net_sales_idr"] == -528000
    assert row["document_type"] == "return"


def test_dq08_return_unmatched(build, fact):
    assert build.result.rule_stats["DQ-08"]["rows"] == 1
    assert fact.loc[fact["is_return"], "dq_return_unmatched"].all()


def test_dq09_late_numbered_invoices(build, fact):
    late = sorted(fact.loc[fact["dq_late_numbered_invoice"], "invoice_no"].unique())
    assert late == [f"INV{n}" for n in range(500799, 500824)]
    assert build.result.rule_stats["DQ-09"]["rows"] == 25


def test_dq09_synthetic_backdated_number():
    df = rows(
        {"invoice_no": "INV000001", "date": "2026-09-01"},
        {"invoice_no": "INV000002", "date": "2026-09-02"},
        {"invoice_no": "INV000009", "date": "2026-09-02"},
        {"invoice_no": "INV000003", "date": "2026-09-03"},
    )
    r = clean(df)
    assert r.lines.loc[r.lines["dq_late_numbered_invoice"], "invoice_no"].tolist() == ["INV000009"]


def test_dq10_suspect_outlets(build, fact):
    assert build.result.rule_stats["DQ-10"]["note"] == "OUT1003, OUT1026, OUT1035, OUT1042, OUT1045"
    s = fact[fact["dq_suspect_outlet"]]
    assert len(s) == 25 and (s["qty_carton"] == 1).all() and (s["discount_idr"] == 0).all()


def test_dq11_sunday(build, fact):
    nt = fact[fact["dq_non_trading_day"]]
    assert nt["invoice_no"].tolist() == ["INV500813"]
    assert str(nt["date"].iloc[0].date()) == "2026-09-27"
    r = clean(rows({"date": "2026-09-02"}), holidays={pd.Timestamp("2026-09-02").date()})
    assert r.lines["dq_non_trading_day"].all()


def test_dq12_same_name_same_branch(build):
    assert build.result.rule_stats["DQ-12"]["note"] == "OUT1001, OUT1003"


def test_dq13_same_name_other_branch(build):
    st = build.result.rule_stats["DQ-13"]
    assert st["entities"] == 18
    dim = build.tables["dim_outlet"]
    assert dim.loc[dim["outlet_name"] == "Toko Anugerah", "name_shared_count"].tolist() == [3, 3, 3]


def test_dq14_gross_mismatch_quarantined(build):
    r = clean(rows({"gross_sales_idr": "999"}))
    assert r.quarantine["rule_id"].tolist() == ["DQ-14"]
    assert build.result.rule_stats["DQ-14"]["rows"] == 0


def test_dq15_net_mismatch_quarantined(build):
    r = clean(rows({"net_sales_idr": "1"}))
    assert r.quarantine["rule_id"].tolist() == ["DQ-15"]
    assert build.result.rule_stats["DQ-15"]["rows"] == 0


def test_dq16_discount_pattern(build, fact):
    assert build.result.rule_stats["DQ-16"]["rows"] == 0
    # 3% of 792000 = 23760, rounded to nearest 100 = 23800: valid.
    ok = clean(rows({"qty_carton": "4", "price_per_carton_idr": "198000", "gross_sales_idr": "792000", "discount_idr": "23800", "net_sales_idr": "768200"}))
    assert not ok.lines["dq_discount_off_pattern"].any()
    bad = clean(rows({"discount_idr": "1000", "net_sales_idr": "371000"}))
    assert bad.lines["dq_discount_off_pattern"].all()
    assert set(fact["discount_rate_pct"].round().astype(int)) <= {0, 2, 3, 5}


def test_dq17_one_price_per_sku(build):
    assert build.result.rule_stats["DQ-17"]["rows"] == 0
    r = clean(rows({}, {}, {"invoice_no": "INV500002", "price_per_carton_idr": "100000", "gross_sales_idr": "200000", "net_sales_idr": "200000"}))
    assert r.lines["dq_price_off_list"].sum() == 1


def test_dq18_one_brand_per_sku(build):
    assert build.result.rule_stats["DQ-18"]["rows"] == 0
    r = clean(rows({}, {"invoice_no": "INV500002"}, {"invoice_no": "INV500003", "brand": "Tos Tos"}))
    assert r.lines["dq_brand_mismatch"].sum() == 1


def test_dq19_outlet_attributes_stable(build):
    st = build.result.rule_stats["DQ-19"]
    assert st["entities"] == 10 and st["remaining"] == 0
    r = clean(rows({}, {"invoice_no": "INV500002"}, {"invoice_no": "INV500003", "outlet_type": "Grosir"}))
    assert r.lines["dq_outlet_attr_conflict"].sum() == 1


def test_dq20_branch_region_stable(build):
    assert build.result.rule_stats["DQ-20"]["rows"] == 10
    assert build.result.rule_stats["DQ-20"]["remaining"] == 0
    r = clean(rows({}, {"invoice_no": "INV500002", "outlet_id": "O2"}, {"invoice_no": "INV500003", "outlet_id": "O3", "region": "Sumatera"}))
    assert r.lines["dq_branch_region_conflict"].sum() == 1


def test_dq21_salesman_single_branch(build):
    assert build.result.rule_stats["DQ-21"]["rows"] == 0
    r = clean(rows({}, {"invoice_no": "INV500002", "outlet_id": "O2"}, {"invoice_no": "INV500003", "outlet_id": "O3", "branch": "Medan", "region": "Sumatera"}))
    assert r.lines["dq_salesman_branch_conflict"].sum() == 1


def test_dq22_invoice_header_identical(build):
    st = build.result.rule_stats["DQ-22"]
    assert st["entities"] == 19 and st["remaining"] == 0
    r = clean(rows({}, {"sku": "X 1g"}, {"sku": "Y 1g", "salesman": "Budi"}))
    assert r.lines["dq_invoice_header_conflict"].sum() == 1


def test_dq23_repeated_sku_in_invoice(build):
    assert build.result.rule_stats["DQ-23"]["rows"] == 0
    r = clean(rows({}, {"qty_carton": "1", "gross_sales_idr": "186000", "net_sales_idr": "186000"}))
    assert r.lines["dq_repeated_sku_in_invoice"].sum() == 2


def test_dq24_qty_sign(build):
    assert build.result.rule_stats["DQ-24"]["rows"] == 0
    r = clean(rows({"qty_carton": "0", "gross_sales_idr": "0", "net_sales_idr": "0"}, {"invoice_no": "RTR000001"}))
    assert r.quarantine["rule_id"].tolist() == ["DQ-24", "DQ-24"]


def test_dq25_multi_invoice_day(build):
    assert build.result.rule_stats["DQ-25"]["rows"] == 0
    r = clean(rows({}, {"invoice_no": "INV500002", "sku": "X 1g"}))
    assert r.lines["dq_multi_invoice_day"].sum() == 2


def test_dq26_trading_days_without_sales(build):
    assert build.result.rule_stats["DQ-26"]["entities"] == 0
    r = clean(rows({"date": "2026-09-01"}), period=("2026-09-01", "2026-09-03"))
    assert r.rule_stats["DQ-26"]["entities"] == 2


def test_dq27_out_of_period(build):
    assert build.result.rule_stats["DQ-27"]["rows"] == 0
    r = clean(rows({"date": "2026-11-02"}))
    assert r.lines["dq_out_of_period"].all()


def test_row_conservation(build):
    m = build.result.meta
    assert m["rows_in"] == 1891
    assert m["rows_in"] == m["rows_clean"] + m["rows_quarantined"]


def test_empty_file_rejected():
    with pytest.raises(ContractError):
        clean(rows({}).iloc[0:0])


def test_all_rows_quarantined_gives_empty_clean_set():
    r = clean(rows({"gross_sales_idr": "1"}, {"date": "bukan tanggal"}))
    assert len(r.lines) == 0 and len(r.quarantine) == 2

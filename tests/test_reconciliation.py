from __future__ import annotations

from dk_sales import reconcile


def test_bridge_balances_to_the_rupiah(build):
    b = build.bridge
    diff_cols = [c for c in b.columns if c.startswith("diff_")]
    assert len(diff_cols) == 5
    assert (b[diff_cols] == 0).all().all()
    assert reconcile.is_balanced(b)


def test_totals(build):
    b = build.bridge
    assert b["raw_rows"].sum() == 1891
    assert b["clean_rows"].sum() == 1888
    assert b["raw_net_sales_idr"].sum() - b["clean_net_sales_idr"].sum() == 1024300 + 744000 + 302600
    assert b["DQ-06_net_sales_idr"].sum() == -(1024300 + 744000 + 302600)
    # Relabelling moves money between labels but never changes the total.
    assert b["DQ-03_net_sales_idr"].sum() == 0
    assert b["DQ-03_rows"].sum() == 0


def test_clean_labels_are_canonical(build):
    b = build.bridge
    variants = b[b["region_label"].isin(["Jabar", "JAWA BARAT", "JABODETABEK", "JAWA TIMUR"])]
    assert (variants["clean_rows"] == 0).all()
    assert (variants["raw_rows"] + variants["DQ-03_rows"] == 0).all()


def test_sales_and_returns_split(fact):
    split = reconcile.split_sales_returns(fact)
    ret = split[split["kind"] == "retur"]
    assert ret["net_sales_idr"].sum() == -528000
    assert split["net_sales_idr"].sum() == fact["net_sales_idr"].sum()

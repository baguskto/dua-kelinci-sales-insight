from __future__ import annotations

import json

import pandera.errors
import pytest

from dk_sales import config, contract


def test_outputs_pass_contract(build):
    contract.validate_outputs(build.tables)


def test_fact_contract_rejects_broken_arithmetic(build):
    fact = build.tables["fact_sales_line"].copy()
    fact.loc[0, "net_sales_idr"] += 1
    with pytest.raises(pandera.errors.SchemaErrors):
        contract.FACT_SCHEMA.validate(fact, lazy=True)


def test_fact_contract_rejects_non_canonical_region(build):
    fact = build.tables["fact_sales_line"].copy()
    fact.loc[0, "region"] = "JAWA BARAT"
    with pytest.raises(pandera.errors.SchemaErrors):
        contract.FACT_SCHEMA.validate(fact, lazy=True)


def test_referential_integrity_checked(build):
    tables = dict(build.tables)
    tables["dim_outlet"] = tables["dim_outlet"].iloc[1:]
    with pytest.raises(pandera.errors.SchemaError):
        contract.validate_outputs(tables)


def test_contract_file_records_raw_hash():
    doc = json.loads((config.CONTRACTS_DIR / "sales_data_contract.json").read_text())
    assert doc["input"]["sha256"] == config.RAW_SHA256
    assert [c["name"] for c in doc["input"]["columns"]] == config.RAW_COLUMNS
    assert len(doc["rules"]) == 27


def test_dimension_sizes(build):
    t = build.tables
    assert len(t["dim_outlet"]) == 52
    assert len(t["dim_product"]) == 13
    assert len(t["dim_salesman"]) == 26
    assert len(t["dim_geo"]) == 13
    assert len(t["dim_date"]) == 61
    assert t["dim_product"].set_index("sku").loc["Kacang Kulit 250g", "pack_size_g"] == 250
    assert t["dim_date"].set_index("date_key").loc[20260927, "day_name_id"] == "Minggu"

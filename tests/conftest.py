from __future__ import annotations

import pytest

from dk_sales import config, pipeline


@pytest.fixture(scope="session")
def build():
    return pipeline.run(config.RAW_PATH)


@pytest.fixture(scope="session")
def fact(build):
    return build.tables["fact_sales_line"]



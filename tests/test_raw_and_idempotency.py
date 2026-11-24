from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from dk_sales import config, pipeline
from dk_sales.io import sha256_file


def test_raw_file_unchanged():
    assert sha256_file(config.RAW_PATH) == config.RAW_SHA256


def test_raw_file_not_modified_in_git():
    out = subprocess.run(["git", "status", "--porcelain", "--", "data/raw"], cwd=config.ROOT, capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip() == ""


def _hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob("*")) if p.is_file()}


def test_pipeline_is_idempotent(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        build = pipeline.run(config.RAW_PATH)
        pipeline.write(build, processed_dir=d / "processed", docs_dir=d / "docs", contracts_dir=d / "contracts")
    ha, hb = _hashes(a), _hashes(b)
    assert len(ha) == 23
    assert ha == hb


def test_committed_outputs_match_a_fresh_build(tmp_path):
    build = pipeline.run(config.RAW_PATH)
    pipeline.write(build, processed_dir=tmp_path / "processed", docs_dir=tmp_path / "docs", contracts_dir=tmp_path / "contracts")
    for name in ["01-dq-audit.md", "02-reconciliation.md", "02-data-dictionary.md", "01-profiling.md"]:
        assert (tmp_path / "docs" / name).read_text() == (config.DOCS_DIR / name).read_text(), f"{name} is stale, run make data"

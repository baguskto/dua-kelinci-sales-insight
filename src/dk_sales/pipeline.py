"""End-to-end build: raw CSV -> profile, cleaning, model, reconciliation, docs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dk_sales import config, contract, docs, model, profile, reconcile
from dk_sales.clean import CleanResult, clean
from dk_sales.io import read_raw, sha256_file


@dataclass
class BuildOutput:
    result: CleanResult
    tables: dict[str, pd.DataFrame]
    bridge: pd.DataFrame
    profile: dict
    raw_sha256: str


def run(raw_path: Path = config.RAW_PATH) -> BuildOutput:
    raw_sha = sha256_file(raw_path)
    raw = read_raw(raw_path)
    prof = profile.profile(raw, raw_sha, str(Path(raw_path).relative_to(config.ROOT)) if Path(raw_path).is_relative_to(config.ROOT) else Path(raw_path).name)
    holidays = model.load_holidays()
    period = (config.PERIOD_START, config.PERIOD_END)
    result = clean(raw, period=period, holidays=set(holidays))
    fact = model.build_fact(result.lines)
    tables = {"fact_sales_line": fact, **model.build_dims(result.lines, period, holidays)}
    contract.validate_outputs(tables)
    br = reconcile.bridge(result)
    if not reconcile.is_balanced(br):
        raise AssertionError("reconciliation does not balance")
    return BuildOutput(result=result, tables=tables, bridge=br, profile=prof, raw_sha256=raw_sha)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, lineterminator="\n")


def write(
    build: BuildOutput, processed_dir: Path = config.PROCESSED_DIR, docs_dir: Path | None = config.DOCS_DIR, contracts_dir: Path | None = config.CONTRACTS_DIR
) -> list[Path]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, df in build.tables.items():
        df.to_parquet(processed_dir / f"{name}.parquet", index=False, engine="pyarrow")
        _write_csv(df, processed_dir / f"{name}.csv")
        written += [processed_dir / f"{name}.parquet", processed_dir / f"{name}.csv"]
    for name, df in [
        ("dq_log", build.result.dq_log),
        ("quarantine_lines", build.result.quarantine),
        ("reconciliation_bridge", build.bridge),
        ("sales_vs_returns", reconcile.split_sales_returns(build.tables["fact_sales_line"])),
    ]:
        _write_csv(df, processed_dir / f"{name}.csv")
        written.append(processed_dir / f"{name}.csv")
    stats = {
        "meta": build.result.meta,
        "raw_sha256": build.raw_sha256,
        "rules": build.result.rule_stats,
    }
    (processed_dir / "dq_summary.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    written.append(processed_dir / "dq_summary.json")

    if contracts_dir is not None:
        contracts_dir.mkdir(parents=True, exist_ok=True)
        p = contracts_dir / "sales_data_contract.json"
        p.write_text(json.dumps(contract.contract_document(build.raw_sha256), indent=2, ensure_ascii=False) + "\n")
        written.append(p)
    if docs_dir is not None:
        docs_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "01-profiling.json": json.dumps(build.profile, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            "01-profiling.md": profile.to_markdown(build.profile),
            "01-dq-audit.md": docs.audit_markdown(build),
            "02-data-dictionary.md": docs.dictionary_markdown(build),
            "02-reconciliation.md": docs.reconciliation_markdown(build),
        }
        for name, text in files.items():
            (docs_dir / name).write_text(text)
            written.append(docs_dir / name)
    return written


def main() -> None:
    build = run()
    paths = write(build)
    m = build.result.meta
    print(f"rows_in={m['rows_in']} rows_clean={m['rows_clean']} rows_quarantined={m['rows_quarantined']}")
    print(f"reconciliation balanced={reconcile.is_balanced(build.bridge)}")
    print(f"wrote {len(paths)} files")


if __name__ == "__main__":
    main()

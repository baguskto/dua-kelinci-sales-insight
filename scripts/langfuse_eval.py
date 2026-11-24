"""Push the golden and red-team chat sets to the self-hosted Langfuse as datasets and record one
experiment run (offline engine, or Claude when ANTHROPIC_API_KEY is set).

Reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY from the environment or from the ops .env file and
talks only to LANGFUSE_HOST (default http://localhost:3001). Never prints keys.

    uv run --extra observability python scripts/langfuse_eval.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_ops_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    load_ops_env()
    os.environ.setdefault("LANGFUSE_HOST", "http://localhost:3001")
    from langfuse import Langfuse

    from dk_sales import config
    from dk_sales.chat import evalset
    from dk_sales.chat.engine import ChatEngine
    from dk_sales.web.dataset import load_bytes
    from dk_sales.web.settings import Settings

    lf = Langfuse(host=os.environ["LANGFUSE_HOST"], public_key=os.environ["LANGFUSE_PUBLIC_KEY"], secret_key=os.environ["LANGFUSE_SECRET_KEY"])
    if not lf.auth_check():
        print("Langfuse auth gagal; cek LANGFUSE_HOST dan kunci.")
        return 1
    ds = load_bytes("sales.csv", (config.ROOT / "sales.csv").read_bytes(), 10**8, 10**7)
    llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    engine = ChatEngine(Settings(app_env="test", anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "")))
    run_name = f"{'claude' if llm else 'offline'}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    totals = {}
    for kind in ("golden", "redteam"):
        name = f"dk-chat-{kind}"
        lf.create_dataset(name=name, description=f"Set {kind} untuk Tanya data (lihat tests/eval/{kind}.json)")
        items = evalset.load(kind)
        for item in items:
            lf.create_dataset_item(
                dataset_name=name,
                id=f"{name}-{item['id']}",
                input={"question": item["q"], "as": item.get("as", "default")},
                expected_output={k: item[k] for k in ("expect", "tool", "refusal", "expect_text") if k in item},
            )
        dataset = lf.get_dataset(name)
        by_id = {r.id: r for r in evalset.run(engine, ds, (kind,))}
        passed = 0
        for it in dataset.items:
            item_id = it.id.removeprefix(f"{name}-")
            res = by_id[item_id]
            with it.run(run_name=run_name, run_metadata={"mode": res.mode}) as span:
                span.update(input={"question": res.question}, output={"passed": res.passed, "detail": res.detail, "mode": res.mode})
                span.score_trace(name="eval_pass", value=1.0 if res.passed else 0.0, comment=res.detail[:200] or None)
            passed += res.passed
        totals[kind] = (passed, len(dataset.items))
    lf.flush()
    for kind, (ok, n) in totals.items():
        print(f"{kind}: {ok}/{n} lulus, run {run_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

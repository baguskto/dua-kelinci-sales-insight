"""Run the golden and red-team chat sets.

Offline (default): rule engine, no network.
Live: `ANTHROPIC_API_KEY=... uv run --extra llm python scripts/live_eval.py --live` runs the same sets
against the real Claude API (model from LLM_MODEL, default claude-haiku-4-5-20251001). Results are
written to var/eval-<mode>.json. The live run sends only the questions and aggregate tool results,
never raw rows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dk_sales import config  # noqa: E402
from dk_sales.chat import evalset  # noqa: E402
from dk_sales.chat.engine import ChatEngine  # noqa: E402
from dk_sales.web.dataset import load_bytes  # noqa: E402
from dk_sales.web.settings import from_env  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use the real API (needs ANTHROPIC_API_KEY)")
    args = ap.parse_args()
    settings = from_env()
    if args.live and not settings.llm_enabled:
        print("ANTHROPIC_API_KEY belum diisi; live eval dilewati.")
        return 0
    if not args.live:
        settings.anthropic_api_key = ""
    settings.chat_rate_per_minute = 10_000
    ds = load_bytes("sales.csv", (config.ROOT / "sales.csv").read_bytes(), 10**8, 10**7)
    engine = ChatEngine(settings)
    results = evalset.run(engine, ds)
    print(evalset.report(results))
    out = config.ROOT / "var" / f"eval-{'live' if args.live else 'offline'}.json"
    out.parent.mkdir(exist_ok=True)
    evalset.write_json(results, out)
    print(f"hasil: {out}")
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

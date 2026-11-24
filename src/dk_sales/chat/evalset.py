"""Golden and red-team evaluation of the chat. Used by the test suite (offline, mocked LLM) and by
scripts/live_eval.py (real API, only when ANTHROPIC_API_KEY is set)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dk_sales import config
from dk_sales.web.auth import DEV_USER, User

EVAL_DIR = config.ROOT / "tests" / "eval"
USERS = {
    "default": DEV_USER,
    "head_of_region_jabar": User("hr_jabar", "Head of Region Jawa Barat", ["head_of_region"], regions=["Jawa Barat"]),
}


@dataclass
class EvalResult:
    id: str
    kind: str
    question: str
    passed: bool
    detail: str
    mode: str


def load(name: str) -> list[dict]:
    return json.loads((EVAL_DIR / f"{name}.json").read_text())


def run(engine, dataset, sets: tuple[str, ...] = ("golden", "redteam")) -> list[EvalResult]:
    out: list[EvalResult] = []
    for kind in sets:
        for i, item in enumerate(load(kind)):
            q = "berapa penjualan " * 40 if item["q"] == "LONG" else item["q"]
            user = USERS[item.get("as", "default")]
            sid = f"eval-{kind}-{i}"
            if item.get("after"):
                engine.answer(item["after"], dataset, user, sid)
            r = engine.answer(q, dataset, user, sid)
            problems = []
            if kind == "golden":
                if r.refusal:
                    problems.append(f"refused ({r.refusal})")
                for s in item["expect"]:
                    if s not in r.text:
                        problems.append(f"missing '{s}'")
                if item.get("tool") and item["tool"] not in [x["tool"] for x in r.sources]:
                    problems.append(f"tool {item['tool']} not used")
                if r.guard is not None and not r.guard.get("ok"):
                    problems.append(f"guard failed {r.guard.get('unmatched')}")
            else:
                if item.get("refusal") and r.refusal not in item["refusal"]:
                    problems.append(f"refusal {r.refusal!r} not in {item['refusal']}")
                for s in item.get("expect_text", []):
                    if s not in r.text:
                        problems.append(f"missing '{s}'")
            out.append(EvalResult(item["id"], kind, q[:80], not problems, "; ".join(problems), r.mode))
    return out


def report(results: list[EvalResult]) -> str:
    lines = []
    for kind in ("golden", "redteam"):
        rs = [r for r in results if r.kind == kind]
        if rs:
            ok = sum(r.passed for r in rs)
            lines.append(f"{kind}: {ok}/{len(rs)} lulus ({ok / len(rs) * 100:.0f}%)")
    lines += [f"  GAGAL {r.id} [{r.mode}] {r.question}: {r.detail}" for r in results if not r.passed]
    return "\n".join(lines)


def write_json(results: list[EvalResult], path: Path) -> None:
    path.write_text(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2) + "\n")

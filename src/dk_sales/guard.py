"""Number guardrail: every number in a generated text must match a computed fact.

Used for the Telegram summary (LLM polish) and for chat replies (LLM mode). The check is
deliberately strict: a number that cannot be traced back to a fact fails the whole text, and
the caller falls back to the deterministic template.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_UNITS = {
    "miliar": 1e9,
    "milyar": 1e9,
    "m": 1e9,
    "juta": 1e6,
    "jt": 1e6,
    "ribu": 1e3,
    "rb": 1e3,
    "k": 1e3,
}
NUMBER_RE = re.compile(
    r"(?:(?<=Rp)|(?<=Rp\s)|(?<![\w.,]))"  # a number glued to letters (OUT1003, INV500813) is an id, not a number
    r"(?P<num>[-+−]?\d+(?:[.,]\d+)*)"
    r"(?P<unit>\s*(?:%|persen\b|miliar\b|milyar\b|juta\b|jt\b|ribu\b|rb\b|[mMkK]\b))?"
    r"(?![\w])"
)


@dataclass(frozen=True)
class FoundNumber:
    text: str
    value: float
    tolerance: float
    is_pct: bool


def parse_number(num: str) -> tuple[float, int]:
    """Parse Indonesian (1.234,5) or plain (1234.5) notation. Returns (value, decimals)."""
    s = num.replace("−", "-").lstrip("+")
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "," in s and "." in s:
        whole, dec = s.rsplit(",", 1) if s.rfind(",") > s.rfind(".") else s.rsplit(".", 1)
        whole = whole.replace(".", "").replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            whole, dec = parts
        elif all(len(p) == 3 for p in parts[1:]):
            whole, dec = "".join(parts), ""
        else:
            whole, dec = parts[0], "".join(parts[1:])
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            whole, dec = "".join(parts), ""
        else:
            whole, dec = parts
    else:
        whole, dec = s, ""
    value = float(f"{whole}.{dec}" if dec else whole)
    return (-value if neg else value), len(dec)


# Identifiers such as DQ-06, OUT1003, INV500813 or RTR900001 are names, not numbers.
ID_RE = re.compile(r"\b(?![Rr][Pp]\d)[A-Za-z]{2,5}-?\d+\b")


def find_numbers(text: str) -> list[FoundNumber]:
    text = ID_RE.sub(" ", text)
    out = []
    for m in NUMBER_RE.finditer(text):
        raw_unit = (m.group("unit") or "").strip()
        unit = raw_unit.lower()
        value, decimals = parse_number(m.group("num"))
        is_pct = unit in ("%", "persen")
        mult = 1.0 if is_pct or not unit else _UNITS.get(unit, 1.0)
        # Single letter units only count after "Rp" context; "5 M" without Rp is ambiguous, keep as plain.
        if unit in ("m", "k") and "Rp" not in text[max(0, m.start() - 3) : m.start()]:
            mult = 1.0
        precision = (10**-decimals) * mult
        out.append(FoundNumber(m.group(0).strip(), value * mult, precision / 2 + 1e-9, is_pct))
    return out


@dataclass
class GuardResult:
    ok: bool
    checked: int
    unmatched: list[str]


def check(text: str, facts: list[float], pct_facts: list[float] | None = None) -> GuardResult:
    """Every number in text must be within display rounding of some fact (sign ignored)."""
    vals = [abs(float(f)) for f in facts]
    pcts = [abs(float(f)) for f in (pct_facts or [])]
    unmatched = []
    found = find_numbers(text)
    for n in found:
        pool = pcts if n.is_pct else vals
        if not any(abs(abs(n.value) - f) <= n.tolerance for f in pool):
            unmatched.append(n.text)
    return GuardResult(ok=not unmatched, checked=len(found), unmatched=unmatched)

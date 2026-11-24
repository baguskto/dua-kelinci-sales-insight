"""Indonesian number formatting shared by the UI, the Telegram summary and the chat."""

from __future__ import annotations

MONTH_SHORT = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun", 7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"}
MONTH_LONG = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def rupiah(n: float | int) -> str:
    """Full rupiah with dot thousands separator: Rp1.234.500."""
    n = int(round(n))
    sign = "-" if n < 0 else ""
    return f"{sign}Rp{abs(n):,}".replace(",", ".")


def rupiah_short(n: float | int) -> str:
    """Compact rupiah for phone screens: Rp1,73 miliar, Rp878,4 juta, Rp528 ribu."""
    v = float(n)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        return f"{sign}Rp{_dec(a / 1e9, 2)} miliar"
    if a >= 1e6:
        return f"{sign}Rp{_dec(a / 1e6, 1)} juta"
    if a >= 1e3:
        return f"{sign}Rp{_dec(a / 1e3, 0)} ribu"
    return f"{sign}Rp{int(a)}"


def _dec(v: float, digits: int) -> str:
    s = f"{v:.{digits}f}"
    if digits:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def pct(v: float | None, digits: int = 1, signed: bool = False) -> str:
    if v is None:
        return "-"
    s = f"{v:+.{digits}f}" if signed else f"{v:.{digits}f}"
    return s.replace(".", ",") + "%"


def month_label(ym: str, long: bool = False) -> str:
    y, m = ym.split("-")
    names = MONTH_LONG if long else MONTH_SHORT
    return f"{names[int(m)]} {y}"


def period_label(period: str, months: list[str]) -> str:
    if period == "all":
        if not months:
            return "-"
        if len(months) == 1:
            return month_label(months[0], long=True)
        a, b = months[0], months[-1]
        if a[:4] == b[:4]:
            return f"{MONTH_SHORT[int(a[5:])]}-{MONTH_SHORT[int(b[5:])]} {a[:4]}"
        return f"{month_label(a)} - {month_label(b)}"
    return month_label(period, long=True)

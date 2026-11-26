"""Indonesian number formatting shared by the UI, the Telegram summary and the chat."""

from __future__ import annotations

MONTH_SHORT = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun", 7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"}
MONTH_LONG = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
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


def rupiah_short_parts(n: float | int) -> tuple[str, str]:
    """rupiah_short split into number and unit, so a KPI can set the unit smaller: ("Rp1,73", "miliar")."""
    s = rupiah_short(n)
    num, _, unit = s.partition(" ")
    return num, unit


MINUS = "−"

# -- English dashboard format (the UI is in English; the chat and the data files stay Indonesian) ----------
MONTH_EN = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
MONTH_EN_LONG = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}
# Standard English names where one exists; the data keeps the Indonesian value (filters use it).
REGION_EN = {"Jawa Barat": "West Java", "Jawa Tengah": "Central Java", "Jawa Timur": "East Java", "Sumatera": "Sumatra"}
REGION_EN_SHORT = {"Jabodetabek": "Jabo", "Jawa Barat": "W. Java", "Jawa Tengah": "C. Java", "Jawa Timur": "E. Java"}


def rpm(n: float | int, signed: bool = False) -> str:
    """Dashboard money format, always in millions with one decimal: Rp 878.4M, −Rp 23.2M, +Rp 47.7M."""
    sign, num, unit = rpm_parts(n, signed)
    return f"{sign}Rp {num}{unit}"


def rpm_parts(n: float | int, signed: bool = False) -> tuple[str, str, str]:
    """rpm() split into sign, number and unit, so the big number and its unit can be set at different sizes."""
    v = round(float(n) / 1e6, 1)
    sign = MINUS if v < 0 else ("+" if signed and v > 0 else "")
    return sign, f"{abs(v):,.1f}", "M"


def spct(v: float | None, digits: int = 1) -> str:
    """Signed percent with a real minus sign: +3.6%, −0.2%."""
    if v is None:
        return "-"
    r = round(v, digits)
    sign = MINUS if r < 0 else ("+" if r > 0 else "")
    return f"{sign}{abs(r):.{digits}f}%"


def epct(v: float | None, digits: int = 1) -> str:
    """Unsigned percent, English decimal point: 8.6%."""
    return "-" if v is None else f"{v:.{digits}f}%"


def num(n: float | int) -> str:
    """Whole number with a thousands comma: 4,427 (a real minus sign when negative)."""
    n = int(round(n))
    return f"{MINUS if n < 0 else ''}{abs(n):,}"


def mon(ym: str) -> str:
    return MONTH_EN[int(ym[5:7])]


def mon_long(ym: str) -> str:
    return f"{MONTH_EN_LONG[int(ym[5:7])]} {ym[:4]}"


def period_en(period: str, months: list[str]) -> str:
    if period != "all":
        return mon_long(period)
    if not months:
        return "-"
    if len(months) == 1:
        return mon_long(months[0])
    a, b = months[0], months[-1]
    return f"{mon(a)}-{mon(b)} {b[:4]}" if a[:4] == b[:4] else f"{mon(a)} {a[:4]} - {mon(b)} {b[:4]}"


def region(name: str) -> str:
    return REGION_EN.get(name, name)


def region_short(name: str) -> str:
    return REGION_EN_SHORT.get(name, region(name))


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

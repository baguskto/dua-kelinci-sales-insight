"""Offline intent parser for Indonesian sales questions.

Rules and keyword/fuzzy matching map a question to calls of the same tools the LLM uses. It also
holds the deterministic guardrails that run before any mode answers: prompt injection, requests
for actions, SQL-like input, data that does not exist in the file, and unsupported languages.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

AVAILABLE = (
    "Yang tersedia: penjualan neto, bruto, karton dan jumlah invoice per region, cabang, brand, SKU, "
    "salesman, tipe outlet dan outlet untuk September dan Oktober 2026, perbandingan Oktober vs September, "
    "outlet terlemah, dan ringkasan kualitas data."
)
EXAMPLES = "Contoh: 'penjualan per region bulan Oktober', '5 outlet terlemah', 'brand mana yang turun paling dalam?'"

REFUSALS = {
    "empty": "Tulis pertanyaan tentang data penjualan. " + EXAMPLES,
    "too_long": "Pertanyaan terlalu panjang. Persingkat menjadi satu pertanyaan.",
    "injection": "Saya hanya menjawab pertanyaan tentang data penjualan di file ini dan tidak mengubah aturan kerja saya. " + EXAMPLES,
    "action": "Chat ini hanya membaca data. Saya tidak bisa mengirim pesan, mengubah, menghapus atau mengunggah data. Untuk mengirim ringkasan ke Telegram, tekan tombol Kirim di panel Ringkasan.",
    "sql": "Saya tidak menjalankan query atau kode. Tanyakan dengan kalimat biasa. " + EXAMPLES,
    "missing_data": "Data itu tidak ada di file ini. " + AVAILABLE,
    "personal_data": "File ini tidak berisi data pribadi (nomor telepon, alamat, email atau KTP) dan saya tidak memberikannya. " + AVAILABLE,
    "language": "Saya menjawab dalam Bahasa Indonesia untuk pertanyaan tentang data penjualan ini. " + EXAMPLES,
    "off_topic": "Maaf, saya hanya bisa menjawab pertanyaan tentang data penjualan Dua Kelinci di file ini. " + EXAMPLES,
    "unknown": "Saya belum menangkap maksud pertanyaannya. " + EXAMPLES,
}

INJECTION = [
    r"abaikan (semua )?(instruksi|perintah|aturan)",
    r"lupakan (semua )?(instruksi|perintah|aturan)",
    r"ignore (all |the )?(previous|prior|above)",
    r"disregard (all |the )?(previous|prior|above)",
    r"system prompt",
    r"prompt sistem",
    r"developer mode",
    r"jailbreak",
    r"\bdan mode\b",
    r"kamu sekarang (adalah|jadi|menjadi)",
    r"tanpa (aturan|batasan|filter)",
    r"mulai sekarang kamu",
    r"you are now",
    r"act as",
    r"berpura[- ]pura",
    r"tampilkan (instruksi|prompt|aturan)",
    r"bocorkan",
    r"<\s*/?\s*(system|script|instruction)",
    r"\[\s*(system|inst)\s*\]",
    r"api[_ ]?key",
    r"secret[_ ]?key",
    r"token bot",
]
ACTION = [
    r"\bkirim(kan)?\b",
    r"\bsend\b",
    r"\bbroadcast\b",
    r"\bforward\b",
    r"\bemail(kan)?\b",
    r"\bhapus\b",
    r"\bdelete\b",
    r"\bubah\b",
    r"\bedit\b",
    r"\bganti (data|angka)",
    r"\bupdate\b",
    r"\bupload\b",
    r"\bunggah\b",
    r"\bpost(ing)? ke\b",
    r"\bbagikan ke\b",
    r"\bshare\b",
]
SQL = [
    r"\bselect\b.+\bfrom\b",
    r"\bdrop\s+table\b",
    r"\binsert\s+into\b",
    r"\bdelete\s+from\b",
    r"\bunion\s+select\b",
    r";\s*--",
    r"\bor\s+1\s*=\s*1\b",
    r"\bexec(ute)?\s*\(",
    r"__import__",
    r"\bos\.system\b",
]
MISSING = [
    r"\bstok\b",
    r"\bstock\b",
    r"\binventor",
    r"\bgudang\b",
    r"\bbudget\b",
    r"\banggaran\b",
    r"\btarget\b",
    r"\bkuota\b",
    r"\bprofit\b",
    r"\blaba\b",
    r"\bmargin\b",
    r"\bhpp\b",
    r"\bcogs\b",
    r"\bbiaya\b",
    r"\bgaji\b",
    r"\bkomisi\b",
    r"\bprediksi\b",
    r"\bforecast\b",
    r"\bramalan\b",
    r"\bkompetitor\b",
    r"\bpesaing\b",
    r"\bmarket share\b",
    r"\bpangsa pasar\b",
    r"\bharga pesaing\b",
]
PERSONAL = [
    r"\bnomor (hp|telepon|telp|wa|whatsapp)\b",
    r"\bno\.? ?(hp|telp)\b",
    r"\balamat\b",
    r"\bemail\b",
    r"\bktp\b",
    r"\bnik\b",
    r"\brekening\b",
    r"\bphone number\b",
    r"\baddress\b",
]
OTHER_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "november": 11,
    "desember": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "june": 6,
    "july": 7,
    "august": 8,
    "december": 12,
}
MONTHS = {"september": 9, "sept": 9, "sep": 9, "oktober": 10, "october": 10, "okt": 10, "oct": 10}

DATA_WORDS = [
    "penjualan",
    "jualan",
    "omzet",
    "omset",
    "sales",
    "revenue",
    "pendapatan",
    "net",
    "neto",
    "bruto",
    "gross",
    "karton",
    "invoice",
    "faktur",
    "order",
    "region",
    "wilayah",
    "cabang",
    "brand",
    "merek",
    "merk",
    "sku",
    "produk",
    "outlet",
    "toko",
    "warung",
    "grosir",
    "minimarket",
    "salesman",
    "retur",
    "diskon",
    "data",
    "terlemah",
    "terbesar",
    "tertinggi",
    "terendah",
    "terkecil",
    "naik",
    "turun",
    "tumbuh",
    "berapa",
    "total",
    "kualitas",
    "duplikat",
    "bulan",
    "kontribusi",
    "porsi",
]
DIMENSION_WORDS = [
    ("outlet_type", [r"tipe outlet", r"jenis outlet", r"tipe toko", r"\bchannel\b", r"tipe pelanggan"]),
    ("salesman", [r"\bsalesman\b", r"\bsalesmen\b", r"\bsales rep", r"tenaga penjual", r"per sales\b", r"\bsales mana\b"]),
    ("branch", [r"\bcabang\b", r"\bbranch\b", r"\bkota\b"]),
    ("region", [r"\bregion\b", r"\bwilayah\b", r"\bdaerah\b", r"\bprovinsi\b", r"\bregional\b"]),
    ("brand", [r"\bbrand\b", r"\bmerek\b", r"\bmerk\b"]),
    ("sku", [r"\bsku\b", r"\bproduk\b", r"\bvarian\b", r"\bitem\b"]),
    ("outlet", [r"\boutlet\b", r"\btoko\b", r"\bpelanggan\b"]),
]
REGION_ALIASES = {
    "jabar": "Jawa Barat",
    "jawa barat": "Jawa Barat",
    "jateng": "Jawa Tengah",
    "jawa tengah": "Jawa Tengah",
    "jatim": "Jawa Timur",
    "jawa timur": "Jawa Timur",
    "jabodetabek": "Jabodetabek",
    "jabotabek": "Jabodetabek",
    "sumatera": "Sumatera",
    "sumatra": "Sumatera",
    "kalimantan": "Kalimantan",
}
BRAND_ALIASES = {
    "kacang dua kelinci": "Kacang Dua Kelinci",
    "dua kelinci": "Kacang Dua Kelinci",
    "kacang": "Kacang Dua Kelinci",
    "sukro": "Sukro",
    "tos tos": "Tos Tos",
    "tostos": "Tos Tos",
    "tos-tos": "Tos Tos",
    "tic tac": "Tic Tac",
    "tictac": "Tic Tac",
    "tic-tac": "Tic Tac",
    "deka": "Deka",
    "pilus": "Pilus",
    "usagi": "Usagi",
    "roni": "Roni",
}
OUTLET_TYPES = {"grosir": "Grosir", "minimarket": "Minimarket", "toko kelontong": "Toko Kelontong", "kelontong": "Toko Kelontong", "warung": "Warung"}


@dataclass
class Intent:
    name: str
    calls: list[tuple[str, dict]] = field(default_factory=list)
    refusal: str | None = None
    message: str | None = None
    note: str | None = None


def normalize(q: str) -> str:
    q = unicodedata.normalize("NFKC", q).lower()
    q = q.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", q).strip()


def _any(patterns: list[str], q: str) -> bool:
    return any(re.search(p, q) for p in patterns)


def _non_latin_ratio(q: str) -> float:
    letters = [c for c in q if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if ord(c) > 0x24F) / len(letters)


def precheck(q: str) -> str | None:
    """Deterministic guardrails shared by offline and LLM mode. Returns a refusal reason or None."""
    if _any(INJECTION, q):
        return "injection"
    if _any(SQL, q):
        return "sql"
    if _any(ACTION, q):
        return "action"
    if _any(PERSONAL, q):
        return "personal_data"
    if _any(MISSING, q):
        return "missing_data"
    years = {int(y) for y in re.findall(r"\b(20\d\d)\b", q)}
    if years - {2026}:
        return "missing_data"
    if any(re.search(rf"\b{m}\b", q) for m in OTHER_MONTHS):
        return "missing_data"
    if _non_latin_ratio(q) > 0.3:
        return "language"
    return None


def _fuzzy_find(q: str, aliases: dict[str, str]) -> list[str]:
    found = []
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", q):
            if aliases[alias] not in found:
                found.append(aliases[alias])
            q = q.replace(alias, " ")
    if not found:
        words = re.findall(r"[a-z][a-z\-]{3,}", q)
        for w in words:
            m = difflib.get_close_matches(w, [a for a in aliases if len(a) >= 4 and " " not in a], n=1, cutoff=0.84)
            if m and aliases[m[0]] not in found:
                found.append(aliases[m[0]])
    return found


def _period(q: str, months: list[str]) -> tuple[str | None, str | None]:
    """Returns (period, problem)."""
    hits = []
    for word, m in MONTHS.items():
        if re.search(rf"\b{word}\b", q):
            ym = f"2026-{m:02d}"
            if ym not in hits:
                hits.append(ym)
    if re.search(r"bulan (lalu|terakhir|ini)", q) and months:
        hits.append(months[-1])
    hits = sorted(set(hits))
    if not hits:
        return None, None
    missing = [h for h in hits if h not in months]
    if missing:
        return None, "missing_data"
    return ("all" if len(hits) > 1 else hits[0]), None


def parse(question: str, known: dict, outlets: list[tuple[str, str, str]], last: Intent | None = None) -> Intent:
    """Map a question to tool calls. outlets = [(outlet_id, name, branch)] the caller may access."""
    q = normalize(question)
    if not q:
        return Intent("refusal", refusal="empty")
    reason = precheck(q)
    if reason:
        return Intent("refusal", refusal=reason)

    period, problem = _period(q, known["months"])
    if problem:
        return Intent("refusal", refusal=problem)
    regions = _fuzzy_find(q, {**REGION_ALIASES, **{r.lower(): r for r in known["region"]}})
    brands = _fuzzy_find(q, {**BRAND_ALIASES, **{b.lower(): b for b in known["brand"]}})
    branches = [b for b in known["branch"] if re.search(rf"\b{re.escape(b.lower())}\b", q)]
    salesmen = [s for s in known["salesman"] if re.search(rf"\b{re.escape(s.lower())}\b", q)]
    types = []
    for k, v in OUTLET_TYPES.items():
        if re.search(rf"\b{k}\b", q) and v not in types:
            types.append(v)
    ids = sorted(set(m.upper() for m in re.findall(r"\bout\s?-?(\d{3,8})\b", q)))
    ids = [f"OUT{i}" for i in ids]
    named = [(oid, name, br) for oid, name, br in outlets if re.search(rf"\b{re.escape(name.lower())}\b", q)]
    if named:
        longest = max(len(n) for _, n, _ in named)
        named = [x for x in named if len(x[1]) == longest]
        if len(types) == 1 and types[0].lower() in named[0][1].lower():
            types = []  # "Toko Mulia" mentions "toko", not the outlet type filter

    n_match = re.search(r"\b(?:top|terbawah|terendah|teratas|tertinggi|terbesar|terkecil|terlemah)?\s*(\d{1,3})\b", q)
    n = int(n_match.group(1)) if n_match and int(n_match.group(1)) not in (2026,) and int(n_match.group(1)) < 1000 else None
    note = None
    if n is not None and n > 20:
        note = f"Maksimal 20 baris; saya tampilkan 20, bukan {n}."
        n = 20
    if n is not None and n < 1:
        n = None

    def filters(single: bool = True) -> dict:
        f: dict = {}
        if regions:
            f["region"] = regions[0]
        if brands:
            f["brand"] = brands[0]
        if types:
            f["outlet_type"] = types[0]
        if salesmen:
            f["salesman"] = salesmen[0]
        if branches:
            f["branch"] = branches[0]
        return f

    dims = [d for d, pats in DIMENSION_WORDS if _any(pats, q)]
    # "salesman Andi" or "cabang Medan" names a member, not a breakdown.
    if salesmen and "salesman" in dims:
        dims.remove("salesman")
    if branches and "branch" in dims:
        dims.remove("branch")
    if (regions or brands) and dims and dims[0] in ("region", "brand") and not re.search(r"\bper\b|\btiap\b|\bmasing", q):
        dims = [d for d in dims if not (d == "region" and regions) and not (d == "brand" and brands)]
    dim = dims[0] if dims else None
    p = period or "all"

    has_data_word = any(re.search(rf"\b{w}", q) for w in DATA_WORDS)
    any_entity = bool(regions or brands or branches or salesmen or types or ids or named)

    # 1. data quality
    if re.search(r"kualitas data|data (kotor|bersih|bermasalah)|duplikat|karantina|dibersihkan|cleaning|masalah data|\bdq\b|salesman kosong|data quality", q):
        return Intent("data_quality", [("data_quality_summary", {})])
    # 2. weakest outlets
    if re.search(
        r"(outlet|toko|pelanggan)\w* (yang )?(paling )?(lemah|terlemah|terburuk|terjelek|paling sedikit|perlu (di)?kunjungi|bermasalah)|terlemah|weakest|paling lemah",
        q,
    ) and not (dim and dim != "outlet"):
        return Intent("weakest_outlets", [("weakest_outlets", {"period": p, "n": n or 5})], note=note)
    # 3. a specific outlet
    if ids:
        return Intent("outlet_detail", [("outlet_detail", {"outlet_id": ids[0]})])
    if named:
        if len(named) > 1:
            opts = "; ".join(f"{oid} ({name}, {br})" for oid, name, br in named)
            return Intent(
                "clarify", message=f"Nama '{named[0][1]}' dipakai {len(named)} outlet: {opts}. Outlet yang mana? Sebutkan id-nya, misalnya {named[0][0]}."
            )
        return Intent("outlet_detail", [("outlet_detail", {"outlet_id": named[0][0]})])
    # 4. comparison / trend
    if re.search(r"\bnaik|\bturun|dibanding|banding|\bmom\b|month.on.month|pertumbuhan|\btumbuh|perubahan|growth|tren|trend|selisih", q):
        args = {"dimension": dim or "total", **{k: v for k, v in filters().items() if k in ("region", "brand")}}
        return Intent("compare", [("compare_periods", args)], note=note)
    # 5. top / bottom
    top = re.search(r"terbesar|tertinggi|teratas|terbaik|paling (besar|tinggi|banyak|laku)|\btop\b|juara|terlaris", q)
    bottom = re.search(r"terkecil|terendah|terbawah|paling (kecil|rendah|sedikit)|\bbottom\b|terburuk", q)
    if (top or bottom) and dim:
        args = {
            "dimension": dim,
            "n": n or (1 if re.search(r"\bmana\b|\bsiapa\b|\bapa\b", q) and not re.search(r"\bper\b", q) else 5),
            "order": "bottom" if bottom and not top else "top",
            "period": p,
        }
        args.update({k: v for k, v in filters().items() if k in ("region", "brand")})
        return Intent("top_bottom", [("top_bottom", args)], note=note)
    # 6. breakdown
    if dim:
        return Intent("breakdown", [("sales_by", {"dimension": dim, "period": p, **filters()})], note=note)
    # 7. totals, optionally filtered
    if any_entity or re.search(r"total|berapa|jumlah|omzet|omset|penjualan|jualan|revenue|karton|invoice", q):
        metric = "qty_carton" if re.search(r"karton|\bdus\b|\bcarton", q) else ("invoices" if re.search(r"invoice|faktur|\border\b", q) else "net_sales")
        if re.search(r"bruto|gross|kotor", q):
            metric = "gross_sales"
        return Intent("total", [("sales_by", {"dimension": "total", "period": p, "metric": metric, **filters()})], note=note)
    # 8. follow-up that only changes the period ("kalau Oktober?")
    if period and last and last.calls:
        tool, args = last.calls[0]
        if "period" in args:
            return Intent(last.name, [(tool, {**args, "period": period})])
    if has_data_word:
        return Intent("refusal", refusal="unknown")
    return Intent("refusal", refusal="off_topic")

"""Generated documentation: DQ audit, data dictionary, reconciliation.

Numbers in these documents come from the build, so the docs cannot drift from the data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from dk_sales.rules import ACTION_ID, RULES, SEVERITY_ID

if TYPE_CHECKING:
    from dk_sales.pipeline import BuildOutput


def rp(n: int | float) -> str:
    n = int(n)
    sign = "-" if n < 0 else ""
    return f"{sign}Rp{abs(n):,}".replace(",", ".")


def pct(v: float, digits: int = 2) -> str:
    return f"{v:.{digits}f}".replace(".", ",") + "%"


def _shared_name_sentence(build: BuildOutput, outlet_ids: list[str]) -> str:
    dim = build.tables["dim_outlet"].set_index("outlet_id")
    parts = []
    for o in outlet_ids:
        name = dim.at[o, "outlet_name"]
        peers = dim[(dim["outlet_name"] == name) & (dim.index != o)]
        if peers.empty:
            parts.append(f"{o} ({name}) namanya unik")
        else:
            where = ", ".join(f"{p} di {peers.at[p, 'branch']}" for p in peers.index)
            parts.append(f"{o} ({name}, {dim.at[o, 'branch']}) bernama sama dengan {where}")
    return "- Nama outlet: " + "; ".join(parts) + "."


def _non_trading_sentence(sales: pd.DataFrame, late: pd.DataFrame) -> str:
    nt = sales[sales["dq_non_trading_day"]]
    if nt.empty:
        return "- Tidak ada transaksi di hari non-dagang."
    in_late = nt[nt["dq_late_numbered_invoice"]]
    items = ", ".join(f"{r.date.date()} {r.invoice_no}" for r in nt.itertuples())
    return f"- Transaksi di hari non-dagang: {len(nt)} baris ({items}); {len(in_late)} di antaranya ada di blok ini."


def _cell(v: object) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        out.append("| " + " | ".join(_cell(v) for v in row) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# DQ audit


def _late_block_findings(build: BuildOutput) -> list[str]:
    f = build.tables["fact_sales_line"]
    sales = f[~f["is_return"]]
    late = sales[sales["dq_late_numbered_invoice"]]
    reg = sales[~sales["dq_late_numbered_invoice"]]
    if late.empty:
        return []
    reg_q1 = reg[reg["qty_carton"] == 1]
    zero_disc_q1 = (reg_q1["discount_idr"] == 0).mean() * 100 if len(reg_q1) else 0
    lines = [
        "## Temuan khusus: invoice di luar urutan (DQ-09, DQ-10)\n",
        f"- {late['invoice_no'].nunique()} invoice ({late['invoice_no'].min()} s.d. {late['invoice_no'].max()}), "
        f"{len(late)} baris, {int(late['qty_carton'].sum())} karton, net {rp(late['net_sales_idr'].sum())} "
        f"({pct(late['net_sales_idr'].sum() / sales['net_sales_idr'].sum() * 100)} dari net penjualan).",
        f"- Invoice reguler bernomor naik mengikuti tanggal tanpa pengecualian ({reg['invoice_no'].nunique()} invoice). "
        f"Blok ini bernomor setelah invoice reguler terakhir, tetapi tanggalnya tersebar dari "
        f"{late['date'].min().date()} sampai {late['date'].max().date()}.",
        f"- Setiap invoice di blok ini hanya 1 baris dan 1 karton, semua tanpa diskon. Pada baris reguler 1 karton, "
        f"yang tanpa diskon hanya {pct(zero_disc_q1, 0)}.",
        f"- Nomor dalam blok dikelompokkan per outlet: {', '.join(sorted(late['outlet_id'].unique()))}. "
        "Kelima outlet ini tidak pernah muncul di invoice reguler.",
        "- Di file mentah, setiap baris blok ini berada di posisi terakhir pada tanggalnya, setelah semua invoice reguler hari itu.",
        _non_trading_sentence(sales, late),
        _shared_name_sentence(build, sorted(late["outlet_id"].unique())),
        "",
        "Penjelasan yang paling cocok: baris-baris ini ditambahkan belakangan ke export, bukan dicatat saat transaksi. "
        "Bisa berupa input susulan (misalnya nota manual atau order kanvas yang diketik setelah tutup bulan), atau baris "
        "yang sengaja disisipkan ke data contoh. Dari data saja tidak bisa dipastikan. Keputusan: baris tetap dihitung "
        "karena angkanya konsisten (qty x harga, tanpa diskon), tetapi diberi tanda `dq_late_numbered_invoice` dan "
        "`dq_suspect_outlet` sehingga dashboard bisa menampilkan atau mengecualikannya.\n",
    ]
    return lines


def _return_findings(build: BuildOutput) -> list[str]:
    f = build.tables["fact_sales_line"]
    r = f[f["is_return"]]
    if r.empty:
        return []
    out = ["## Temuan khusus: retur (DQ-07, DQ-08)\n"]
    for row in r.itertuples():
        same = f[(~f["is_return"]) & (f["outlet_id"] == row.outlet_id) & (f["sku"] == row.sku) & (f["date"] <= row.date)]
        out.append(
            f"- {row.invoice_no} tanggal {row.date.date()}, outlet {row.outlet_id}, {row.sku}, qty {row.qty_carton}, "
            f"net {rp(row.net_sales_idr)}. Pembelian SKU ini oleh outlet yang sama sampai tanggal itu: "
            f"{int(same['qty_carton'].sum())} karton ({', '.join(same['invoice_no']) or 'tidak ada'})."
        )
    out.append(
        "\nRetur disimpan sebagai baris tersendiri dengan `is_return = true` dan `document_type = return`. "
        "Penjualan bruto dan neto penjualan hanya menjumlah baris `sale`. Neto setelah retur = neto penjualan + neto retur.\n"
    )
    return out


def _sample(build: BuildOutput, rule_id: str, n: int = 5) -> str:
    log = build.result.dq_log
    lg = log[log["rule_id"] == rule_id].drop_duplicates("raw_row_id").head(n)
    if lg.empty:
        return "_Tidak ada baris._"
    raw = build.result.raw.set_index("raw_row_id")
    rows = []
    for e in lg.itertuples():
        r = raw.loc[e.raw_row_id]
        rows.append(
            {
                "raw_row_id": e.raw_row_id,
                "baris file": e.source_line,
                "invoice": r["invoice_no"],
                "outlet": r["outlet_id"],
                "kolom": e.column,
                "sebelum": e.before,
                "sesudah": e.after,
                "alasan": e.reason,
            }
        )
    return _md_table(pd.DataFrame(rows))


def audit_markdown(build: BuildOutput) -> str:
    st = build.result.rule_stats
    m = build.result.meta
    s = [
        "# 01 Audit kualitas data\n",
        "Dibuat otomatis oleh `make data`. Setiap aturan punya id tetap (DQ-01 sampai DQ-27) yang dipakai di log "
        "(`data/processed/dq_log.csv`), karantina (`data/processed/quarantine_lines.csv`), kolom tanda di "
        "`fact_sales_line`, dan test (`tests/test_dq_rules.py`).\n",
        f"Baris masuk {m['rows_in']}, baris bersih {m['rows_clean']}, baris karantina {m['rows_quarantined']}. Tidak ada baris yang dibuang tanpa catatan.\n",
        "Arti kolom: **baris** = jumlah baris yang terkena aturan di data mentah; **entitas** = jumlah invoice/outlet/"
        "tanggal yang terkena bila aturan berlaku di level itu; **sisa** = pelanggaran yang masih ada setelah cleaning.\n",
        "## Ringkasan aturan\n",
    ]
    rows = []
    for r in RULES:
        x = st[r.rule_id]
        rows.append(
            {
                "id": r.rule_id,
                "aturan": r.title,
                "tingkat": SEVERITY_ID[r.severity],
                "level": r.level,
                "baris": x["rows"],
                "entitas": x["entities"],
                "sisa": x["remaining"],
                "tindakan": ACTION_ID[r.action],
            }
        )
    s.append(_md_table(pd.DataFrame(rows)))
    s.append("")
    s += _late_block_findings(build)
    s += _return_findings(build)
    s.append("## Detail per aturan\n")
    for r in RULES:
        x = st[r.rule_id]
        s.append(f"### {r.rule_id} {r.title}\n")
        s.append(f"- Tingkat: {SEVERITY_ID[r.severity]}; level: {r.level}; tindakan: {ACTION_ID[r.action]}")
        s.append(f"- Jumlah: {x['rows']} baris, {x['entities']} entitas, sisa setelah cleaning {x['remaining']}")
        if x["note"]:
            s.append(f"- Catatan: {x['note']}")
        if r.flag_column:
            s.append(f"- Kolom tanda di fact: `{r.flag_column}`")
        s.append(f"- Keputusan: {r.decision}\n")
        if x["rows"] and r.rule_id in set(build.result.dq_log["rule_id"]):
            s.append(_sample(build, r.rule_id))
            s.append("")
    return "\n".join(s) + "\n"


# ---------------------------------------------------------------------------
# data dictionary

DESCRIPTIONS: dict[str, dict[str, str]] = {
    "fact_sales_line": {
        "line_id": "Id baris, sama dengan raw_row_id (nomor baris data di file mentah, header tidak dihitung).",
        "date_key": "Tanggal dalam bentuk YYYYMMDD, kunci ke dim_date.",
        "date": "Tanggal dokumen.",
        "year_month": "Bulan dokumen, YYYY-MM.",
        "invoice_no": "Nomor dokumen. INV = penjualan, RTR = retur.",
        "document_type": "sale atau return.",
        "is_return": "true untuk baris retur.",
        "outlet_id": "Kunci ke dim_outlet.",
        "geo_key": "Kunci ke dim_geo (slug nama cabang).",
        "region": "Region baku (6 nilai).",
        "branch": "Cabang.",
        "salesman_code": "Kunci ke dim_salesman (slug nama). Kosong bila salesman tidak diketahui.",
        "salesman": "Nama salesman setelah DQ-05.",
        "sku_code": "Kunci ke dim_product (slug SKU).",
        "brand": "Brand.",
        "sku": "Nama SKU.",
        "qty_carton": "Jumlah karton. Negatif untuk retur.",
        "price_per_carton_idr": "Harga per karton dalam rupiah.",
        "gross_sales_idr": "qty_carton x price_per_carton_idr.",
        "discount_idr": "Diskon rupiah, 0/2/3/5% dari gross dibulatkan ke Rp100.",
        "net_sales_idr": "gross_sales_idr - discount_idr.",
        "discount_rate_pct": "discount_idr / gross_sales_idr x 100, dua desimal.",
        "dq_flags": "Daftar tanda DQ yang aktif pada baris, dipisah titik koma.",
    },
    "dim_outlet": {
        "outlet_id": "Id outlet dari sumber.",
        "outlet_name": "Nama outlet setelah DQ-04.",
        "outlet_type": "Grosir, Minimarket, Toko Kelontong atau Warung.",
        "branch": "Cabang outlet.",
        "region": "Region baku.",
        "first_date": "Tanggal transaksi pertama di data.",
        "last_date": "Tanggal transaksi terakhir di data.",
        "n_invoices": "Jumlah dokumen (penjualan dan retur).",
        "n_salesmen": "Jumlah salesman yang pernah melayani outlet.",
        "dq_suspect_outlet": "true bila outlet hanya muncul di invoice di luar urutan (DQ-10).",
        "dq_outlet_name_shared_in_branch": "true bila nama outlet dipakai outlet_id lain di cabang yang sama (DQ-12).",
        "name_shared_count": "Jumlah outlet_id yang memakai nama yang sama (DQ-13). 1 berarti nama unik.",
    },
    "dim_product": {
        "sku_code": "Slug SKU, kunci.",
        "brand": "Brand.",
        "sku": "Nama SKU.",
        "pack_size_g": "Ukuran kemasan dalam gram, diambil dari nama SKU.",
        "list_price_per_carton_idr": "Harga per karton yang berlaku di data.",
    },
    "dim_salesman": {
        "salesman_code": "Slug nama, kunci.",
        "salesman": "Nama salesman.",
        "branch": "Cabang tempat salesman bertugas.",
        "region": "Region cabang.",
        "n_outlets": "Jumlah outlet yang dilayani.",
        "n_invoices": "Jumlah dokumen.",
    },
    "dim_geo": {
        "geo_key": "Slug cabang, kunci.",
        "region": "Region baku.",
        "branch": "Cabang.",
        "n_outlets": "Jumlah outlet di cabang.",
        "n_salesmen": "Jumlah salesman di cabang.",
    },
    "dim_date": {
        "date_key": "YYYYMMDD, kunci.",
        "date": "Tanggal.",
        "day_of_week": "1 = Senin sampai 7 = Minggu.",
        "day_name_id": "Nama hari dalam bahasa Indonesia.",
        "iso_year": "Tahun ISO.",
        "iso_week": "Minggu ISO (Senin sebagai awal minggu).",
        "week_start": "Tanggal Senin di minggu itu.",
        "month": "Nomor bulan.",
        "month_name_id": "Nama bulan dalam bahasa Indonesia.",
        "year_month": "YYYY-MM.",
        "is_sunday": "true untuk hari Minggu.",
        "is_holiday": "true untuk libur nasional (data/reference/holidays_id.csv).",
        "holiday_name": "Nama libur nasional.",
        "is_trading_day": "Senin sampai Sabtu dan bukan libur nasional.",
        "has_sales": "true bila ada baris penjualan pada tanggal itu.",
    },
}
FLAG_DESCRIPTIONS = {r.flag_column: f"{r.rule_id}: {r.title}." for r in RULES if r.flag_column and r.flag_column != "is_return"}


def dictionary_markdown(build: BuildOutput) -> str:
    s = [
        "# 02 Kamus data\n",
        "Dibuat otomatis oleh `make data`. Semua tabel ada di `data/processed/` dalam format Parquet dan CSV "
        "(nama file sama). Model berbentuk star schema: satu tabel fakta per baris invoice dan lima dimensi.\n",
        "```",
        "dim_date ─┐",
        "dim_geo ──┤",
        "dim_outlet┼── fact_sales_line (1 baris = 1 SKU pada 1 dokumen)",
        "dim_product┤",
        "dim_salesman┘",
        "```\n",
        "Ukuran utama: penjualan neto = jumlah `net_sales_idr` baris `sale`. Retur dihitung terpisah "
        "(`is_return = true`). Neto setelah retur = neto penjualan + neto retur (retur bernilai negatif).\n",
        "File pendukung:\n",
        "- `dq_log.csv`: satu baris per perubahan, inferensi, tanda atau karantina (raw_row_id, source_line, rule_id, column, before, after, action, reason). source_line = nomor baris di file CSV termasuk header.",
        "- `quarantine_lines.csv`: baris yang dikeluarkan dari fakta, dengan nilai mentah, rule_id dan alasan.",
        "- `reconciliation_bridge.csv`: jembatan total mentah ke bersih per bulan dan region.",
        "- `sales_vs_returns.csv`: total penjualan dan retur per bulan dan region.",
        "- `dq_summary.json`: jumlah per aturan.\n",
    ]
    for name, df in build.tables.items():
        s.append(f"## {name}\n")
        s.append(f"{len(df)} baris.\n")
        desc = {**DESCRIPTIONS.get(name, {}), **FLAG_DESCRIPTIONS}
        rows = []
        for c in df.columns:
            sample = df[c].dropna()
            ex = sample.iloc[0] if len(sample) else ""
            if isinstance(ex, pd.Timestamp):
                ex = ex.date()
            rows.append({"kolom": c, "tipe": str(df[c].dtype), "contoh": ex, "keterangan": desc.get(c, "")})
        s.append(_md_table(pd.DataFrame(rows)))
        s.append("")
    return "\n".join(s) + "\n"


# ---------------------------------------------------------------------------
# reconciliation


def reconciliation_markdown(build: BuildOutput) -> str:
    b = build.bridge
    rule_ids = sorted({c.split("_")[0] for c in b.columns if c.startswith("DQ-")})
    s = [
        "# 02 Rekonsiliasi mentah ke bersih\n",
        "Dibuat otomatis oleh `make data`. Untuk setiap bulan dan label region seperti tertulis di file mentah: "
        "mentah + koreksi per aturan = bersih. Kolom selisih harus 0 untuk semua ukuran; test "
        "`tests/test_reconciliation.py` memeriksanya.\n",
        "- DQ-03 memindahkan baris dari label region tidak baku ke label baku (minus di label lama, plus di label baru).",
        "- DQ-06 mengeluarkan baris duplikat persis ke karantina.\n",
    ]
    for metric, label in [
        ("rows", "Baris"),
        ("qty_carton", "Karton"),
        ("gross_sales_idr", "Gross (Rp)"),
        ("discount_idr", "Diskon (Rp)"),
        ("net_sales_idr", "Net (Rp)"),
    ]:
        s.append(f"## {label}\n")
        cols = ["month", "region_label", f"raw_{metric}", *[f"{r}_{metric}" for r in rule_ids], f"clean_{metric}", f"diff_{metric}"]
        t = b[cols].copy()
        total = {"month": "Total", "region_label": "", **{c: int(t[c].sum()) for c in cols[2:]}}
        t = pd.concat([t, pd.DataFrame([total])], ignore_index=True)
        t.columns = ["bulan", "region (label mentah)", "mentah", *rule_ids, "bersih", "selisih"]
        if metric != "rows" and metric != "qty_carton":
            for c in ["mentah", *rule_ids, "bersih", "selisih"]:
                t[c] = t[c].map(lambda v: f"{int(v):,}".replace(",", "."))
        s.append(_md_table(t))
        s.append("")
    f = build.tables["fact_sales_line"]
    sale = f[~f["is_return"]]
    ret = f[f["is_return"]]
    s.append("## Penjualan dan retur di data bersih\n")
    rows = []
    for ym in sorted(f["year_month"].unique()):
        a = sale[sale["year_month"] == ym]
        r = ret[ret["year_month"] == ym]
        rows.append(
            {
                "bulan": ym,
                "baris penjualan": len(a),
                "gross penjualan": rp(a["gross_sales_idr"].sum()),
                "diskon": rp(a["discount_idr"].sum()),
                "net penjualan": rp(a["net_sales_idr"].sum()),
                "baris retur": len(r),
                "net retur": rp(r["net_sales_idr"].sum()),
                "net setelah retur": rp(a["net_sales_idr"].sum() + r["net_sales_idr"].sum()),
            }
        )
    rows.append(
        {
            "bulan": "Total",
            "baris penjualan": len(sale),
            "gross penjualan": rp(sale["gross_sales_idr"].sum()),
            "diskon": rp(sale["discount_idr"].sum()),
            "net penjualan": rp(sale["net_sales_idr"].sum()),
            "baris retur": len(ret),
            "net retur": rp(ret["net_sales_idr"].sum()),
            "net setelah retur": rp(f["net_sales_idr"].sum()),
        }
    )
    s.append(_md_table(pd.DataFrame(rows)))
    s.append("")
    late = sale[sale["dq_late_numbered_invoice"]]
    s.append(
        f"Bila invoice di luar urutan (DQ-09) dikecualikan, net penjualan berkurang {rp(late['net_sales_idr'].sum())} "
        f"({len(late)} baris). Angka di atas masih memasukkannya.\n"
    )
    return "\n".join(s) + "\n"

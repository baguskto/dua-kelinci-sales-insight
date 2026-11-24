"""Registry of data-quality rules.

Each rule has a stable id that appears in the DQ log, the quarantine file, the fact table flags,
the audit document and the tests. Titles and decisions are written in Indonesian because they are
shown to business readers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    severity: str  # high | medium | low | info
    level: str  # file | row | invoice | outlet | date
    action: str  # rejected | fixed | inferred | flagged | quarantined | none
    decision: str
    flag_column: str | None = None


RULES: list[Rule] = [
    Rule(
        "DQ-01",
        "Skema kolom: 15 kolom wajib dengan nama yang dikenal",
        "high",
        "file",
        "rejected",
        "File ditolak bila ada kolom wajib yang hilang. Nama kolom dinormalkan (huruf kecil, spasi jadi "
        "garis bawah); kolom tambahan diabaikan dan dicatat.",
    ),
    Rule(
        "DQ-02",
        "Format nilai: tanggal ISO, angka bulat, nomor invoice, kolom wajib terisi",
        "high",
        "row",
        "quarantined",
        "Baris yang tanggalnya tidak bisa dibaca, angkanya bukan bilangan bulat, nomor invoicenya tidak "
        "berpola INV/RTR + 6 digit, atau kolom wajibnya kosong masuk karantina dengan alasannya.",
    ),
    Rule(
        "DQ-03",
        "Penulisan region tidak baku (huruf besar/kecil, singkatan)",
        "medium",
        "row",
        "fixed",
        "Region dipetakan ke 6 nama baku (Jabodetabek, Jawa Barat, Jawa Tengah, Jawa Timur, Sumatera, "
        "Kalimantan). Singkatan seperti Jabar dipetakan lewat daftar alias. Nilai lama dicatat di log.",
    ),
    Rule(
        "DQ-04",
        "Spasi di awal/akhir teks (misalnya outlet_name)",
        "low",
        "row",
        "fixed",
        "Spasi di awal dan akhir semua kolom teks dihapus, spasi ganda di tengah dijadikan satu.",
    ),
    Rule(
        "DQ-05",
        "Salesman kosong",
        "medium",
        "row",
        "inferred",
        "Salesman diisi hanya bila ada bukti: (1) baris lain di invoice yang sama punya satu salesman, "
        "atau (2) outlet itu hanya pernah dilayani satu salesman. Tanpa bukti, nilainya dibiarkan kosong "
        "dan ditandai. Baris yang diisi diberi tanda dq_salesman_inferred.",
        "dq_salesman_inferred",
    ),
    Rule(
        "DQ-06",
        "Baris duplikat persis dalam invoice yang sama",
        "high",
        "row",
        "quarantined",
        "Kemunculan pertama dipertahankan, kemunculan berikutnya masuk karantina dengan nomor baris "
        "aslinya. Tidak ada nomor baris item di data, dan tidak ada invoice lain yang memuat SKU yang "
        "sama dua kali, sehingga baris kembar dianggap terinput dua kali.",
    ),
    Rule(
        "DQ-07",
        "Baris retur (dokumen RTR, qty dan nilai negatif)",
        "medium",
        "row",
        "flagged",
        "Retur tetap disimpan sebagai retur (is_return = true). Penjualan bruto hanya menjumlah baris "
        "penjualan; retur dilaporkan terpisah dan dikurangkan saat menghitung penjualan neto setelah retur.",
        "is_return",
    ),
    Rule(
        "DQ-08",
        "Retur tanpa pembelian yang cukup di periode data",
        "low",
        "row",
        "flagged",
        "Ditandai saja. Retur bisa berasal dari pembelian sebelum September 2026 yang tidak ada di file. "
        "Perlu konfirmasi ke tim sales/finance.",
        "dq_return_unmatched",
    ),
    Rule(
        "DQ-09",
        "Nomor invoice di luar urutan (nomor lebih besar dari invoice bertanggal lebih akhir)",
        "medium",
        "invoice",
        "flagged",
        "Nomor invoice reguler naik mengikuti tanggal. Invoice yang nomornya tidak cocok dengan urutan "
        "tanggal ditandai sebagai blok yang diterbitkan terlambat. Baris tetap dihitung karena angkanya "
        "konsisten, tetapi bisa dikecualikan lewat tanda dq_late_numbered_invoice.",
        "dq_late_numbered_invoice",
    ),
    Rule(
        "DQ-10",
        "Outlet yang hanya muncul di invoice di luar urutan",
        "medium",
        "outlet",
        "flagged",
        "Outlet ini tidak pernah muncul di urutan invoice reguler. Semua barisnya 1 karton tanpa diskon. "
        "Tetap disimpan dan ditandai dq_suspect_outlet; perlu dicek ke master outlet.",
        "dq_suspect_outlet",
    ),
    Rule(
        "DQ-11",
        "Transaksi di hari non-dagang (Minggu atau libur nasional)",
        "low",
        "row",
        "flagged",
        "Di data ini hari Minggu kosong kecuali satu baris. Baris ditandai, tidak diubah.",
        "dq_non_trading_day",
    ),
    Rule(
        "DQ-12",
        "Nama outlet sama, outlet_id berbeda, di cabang yang sama",
        "medium",
        "outlet",
        "flagged",
        "Kemungkinan outlet ganda di master data. Kedua id dipertahankan karena tidak ada bukti untuk "
        "menggabungkan; baris ditandai dq_outlet_name_shared_in_branch.",
        "dq_outlet_name_shared_in_branch",
    ),
    Rule(
        "DQ-13",
        "Nama outlet sama, outlet_id berbeda, di cabang berbeda",
        "info",
        "outlet",
        "none",
        "Nama toko umum yang dipakai di kota berbeda. Dianggap outlet berbeda. Dicatat di dim_outlet "
        "(name_shared_count) agar laporan per nama tidak tergabung keliru.",
    ),
    Rule(
        "DQ-14",
        "gross_sales_idr = qty_carton x price_per_carton_idr",
        "high",
        "row",
        "quarantined",
        "Baris yang tidak cocok masuk karantina karena tidak bisa ditentukan angka mana yang benar.",
    ),
    Rule(
        "DQ-15",
        "net_sales_idr = gross_sales_idr - discount_idr",
        "high",
        "row",
        "quarantined",
        "Baris yang tidak cocok masuk karantina karena tidak bisa ditentukan angka mana yang benar.",
    ),
    Rule(
        "DQ-16",
        "Pola diskon: 0, 2, 3 atau 5 persen dari gross, dibulatkan ke Rp100 terdekat",
        "low",
        "row",
        "flagged",
        "Selisih sampai Rp40 terhadap persentase tepat adalah efek pembulatan ke Rp100, bukan kesalahan. "
        "Baris di luar pola ditandai dq_discount_off_pattern.",
        "dq_discount_off_pattern",
    ),
    Rule(
        "DQ-17",
        "Satu harga per SKU",
        "medium",
        "row",
        "flagged",
        "Harga per karton dibandingkan dengan harga terbanyak untuk SKU itu; yang berbeda ditandai.",
        "dq_price_off_list",
    ),
    Rule(
        "DQ-18",
        "Satu brand per SKU",
        "medium",
        "row",
        "flagged",
        "SKU yang tercatat di brand berbeda ditandai.",
        "dq_brand_mismatch",
    ),
    Rule(
        "DQ-19",
        "Atribut outlet stabil (nama, tipe, cabang, region per outlet_id)",
        "medium",
        "outlet",
        "flagged",
        "Di data mentah tidak stabil hanya karena DQ-03 dan DQ-04. Setelah perbaikan dicek ulang; sisa "
        "perbedaan ditandai.",
        "dq_outlet_attr_conflict",
    ),
    Rule(
        "DQ-20",
        "Satu region per cabang",
        "medium",
        "row",
        "flagged",
        "Di data mentah tidak stabil hanya karena DQ-03. Setelah perbaikan dicek ulang.",
        "dq_branch_region_conflict",
    ),
    Rule(
        "DQ-21",
        "Salesman hanya di satu cabang",
        "medium",
        "row",
        "flagged",
        "Salesman yang muncul di lebih dari satu cabang ditandai pada baris cabang minoritas.",
        "dq_salesman_branch_conflict",
    ),
    Rule(
        "DQ-22",
        "Header invoice sama di semua baris (tanggal, outlet, cabang, region, salesman)",
        "medium",
        "invoice",
        "flagged",
        "Di data mentah tidak sama hanya karena DQ-03, DQ-04 dan DQ-05. Setelah perbaikan dicek ulang.",
        "dq_invoice_header_conflict",
    ),
    Rule(
        "DQ-23",
        "SKU tidak berulang dalam satu invoice (setelah duplikat persis dikarantina)",
        "low",
        "row",
        "flagged",
        "SKU yang muncul dua kali dengan angka berbeda ditandai, tidak digabung.",
        "dq_repeated_sku_in_invoice",
    ),
    Rule(
        "DQ-24",
        "Tanda qty sesuai jenis dokumen (INV positif, RTR negatif, tidak nol)",
        "high",
        "row",
        "quarantined",
        "Baris dengan qty nol atau tanda yang tidak sesuai jenis dokumennya masuk karantina.",
    ),
    Rule(
        "DQ-25",
        "Lebih dari satu invoice penjualan per outlet per hari",
        "info",
        "outlet",
        "flagged",
        "Ditandai saja; bisa kunjungan ulang yang sah.",
        "dq_multi_invoice_day",
    ),
    Rule(
        "DQ-26",
        "Hari dagang (Senin-Sabtu) tanpa transaksi",
        "info",
        "date",
        "none",
        "Dicatat di dim_date (has_sales). Tidak mengubah baris.",
    ),
    Rule(
        "DQ-27",
        "Tanggal di luar periode yang diharapkan",
        "medium",
        "row",
        "flagged",
        "Baris di luar periode ditandai dq_out_of_period dan tidak dibuang.",
        "dq_out_of_period",
    ),
]

RULES_BY_ID: dict[str, Rule] = {r.rule_id: r for r in RULES}
FLAG_COLUMNS: list[str] = [r.flag_column for r in RULES if r.flag_column and r.flag_column != "is_return"]

SEVERITY_ID = {"high": "tinggi", "medium": "sedang", "low": "rendah", "info": "info"}
ACTION_ID = {
    "rejected": "ditolak",
    "fixed": "diperbaiki",
    "inferred": "diisi (inferensi)",
    "flagged": "ditandai",
    "quarantined": "dikarantina",
    "none": "dicatat",
}

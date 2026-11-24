"""Generate Grafana dashboards (JSON) and alert rules (YAML) under ops/grafana. Run after changing metrics.

uv run python scripts/build_grafana.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "ops/grafana/dashboards"
ALERTS = ROOT / "ops/grafana/provisioning/alerting/rules.yaml"
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}


def panel(pid, title, exprs, kind="timeseries", unit="short", x=0, y=0, w=12, h=8, ds=PROM, desc=""):
    targets = [{"refId": chr(65 + i), "expr": e, "legendFormat": lg, "datasource": ds} for i, (e, lg) in enumerate(exprs)]
    p = {
        "id": pid,
        "type": kind,
        "title": title,
        "description": desc,
        "datasource": ds,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {},
    }
    if kind == "logs":
        p["options"] = {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending"}
        p.pop("fieldConfig")
    if kind == "stat":
        p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value", "graphMode": "area"}
    if kind == "bargauge":
        p["options"] = {"orientation": "horizontal", "displayMode": "basic", "reduceOptions": {"calcs": ["lastNotNull"]}}
    return p


def dashboard(uid, title, panels, desc):
    return {
        "uid": uid,
        "title": title,
        "description": desc,
        "tags": ["dua-kelinci"],
        "timezone": "Asia/Jakarta",
        "schemaVersion": 39,
        "time": {"from": "now-1h", "to": "now"},
        "refresh": "30s",
        "panels": panels,
        "templating": {"list": []},
        "annotations": {"list": []},
        "editable": False,
    }


def build_dashboards() -> dict[str, dict]:
    rate = "sum(rate(http_requests_total[5m]))"
    health = dashboard(
        "dk-service-health",
        "Dua Kelinci - Kesehatan layanan",
        [
            panel(1, "Aplikasi hidup", [("up{job='dua-kelinci-app'}", "up")], "stat", "none", 0, 0, 6, 4),
            panel(2, "Request per detik", [(rate, "total")], "stat", "reqps", 6, 0, 6, 4),
            panel(
                3,
                "Rasio error 5xx",
                [("sum(rate(http_requests_total{status=~'5..'}[5m])) / clamp_min(" + rate + ", 1e-9)", "5xx")],
                "stat",
                "percentunit",
                12,
                0,
                6,
                4,
            ),
            panel(
                4, "Latensi p95", [("histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))", "p95")], "stat", "s", 18, 0, 6, 4
            ),
            panel(5, "Request per route", [("sum by (route) (rate(http_requests_total[5m]))", "{{route}}")], unit="reqps", y=4),
            panel(
                6,
                "Latensi p95 per route",
                [("histogram_quantile(0.95, sum by (le, route) (rate(http_request_duration_seconds_bucket[5m])))", "{{route}}")],
                unit="s",
                x=12,
                y=4,
            ),
            panel(7, "Status HTTP", [("sum by (status) (rate(http_requests_total[5m]))", "{{status}}")], unit="reqps", y=12),
            panel(8, "Memori proses", [("process_resident_memory_bytes{job='dua-kelinci-app'}", "RSS")], unit="bytes", x=12, y=12),
            panel(9, "Log error aplikasi", [("{service='app-prod'} | json | level=~`ERROR|WARNING`", "")], "logs", y=20, w=24, h=8, ds=LOKI),
        ],
        "Uptime, request, error, latensi, memori dan log error aplikasi.",
    )
    usage = dashboard(
        "dk-sales-usage",
        "Dua Kelinci - Pemakaian aplikasi",
        [
            panel(1, "Dashboard dibuka (1 jam)", [("sum(increase(http_requests_total{route='/',status='200'}[1h]))", "views")], "stat", "short", 0, 0, 6, 4),
            panel(2, "Unggahan diterima (24 jam)", [("sum(increase(uploads_total{result='accepted'}[24h]))", "accepted")], "stat", "short", 6, 0, 6, 4),
            panel(3, "Unggahan ditolak (24 jam)", [("sum(increase(uploads_total{result='rejected'}[24h]))", "rejected")], "stat", "short", 12, 0, 6, 4),
            panel(4, "Kirim Telegram (24 jam)", [("sum by (result) (increase(telegram_sends_total[24h]))", "{{result}}")], "stat", "short", 18, 0, 6, 4),
            panel(
                5,
                "Halaman, API dan ekspor",
                [("sum by (route) (rate(http_requests_total{route=~'/|/api/.*|/export/.*|/outlet/.*'}[5m]))", "{{route}}")],
                unit="reqps",
                y=4,
            ),
            panel(6, "Baris diproses", [("increase(rows_processed_total[1h])", "baris")], y=4, x=12),
            panel(7, "Login gagal", [("increase(login_failures_total[15m])", "gagal")], y=12),
            panel(8, "Audit: unggah, kirim, login", [("{service='app-prod'} | json | audit=`true`", "")], "logs", y=12, x=12, ds=LOKI),
        ],
        "Siapa memakai apa: halaman, unggahan, Telegram, login.",
    )
    chat = dashboard(
        "dk-chat-guardrails",
        "Dua Kelinci - Chat dan guardrail",
        [
            panel(1, "Pertanyaan per mode", [("sum by (mode) (increase(chat_turns_total[1h]))", "{{mode}}")], "bargauge", "short", 0, 0, 8, 6),
            panel(2, "Penolakan per alasan", [("sum by (reason) (increase(chat_refusals_total[1h]))", "{{reason}}")], "bargauge", "short", 8, 0, 8, 6),
            panel(
                3,
                "Fallback guardrail",
                [("sum by (where, reason) (increase(guardrail_fallbacks_total[1h]))", "{{where}} {{reason}}")],
                "bargauge",
                "short",
                16,
                0,
                8,
                6,
            ),
            panel(4, "Pertanyaan per intent", [("sum by (intent) (rate(chat_turns_total[5m]))", "{{intent}}")], unit="reqps", y=6),
            panel(5, "Token LLM", [("sum by (kind) (increase(llm_tokens_total[1h]))", "{{kind}}")], y=6, x=12),
            panel(6, "Biaya LLM (USD, 24 jam)", [("increase(llm_cost_usd_total[24h])", "USD")], "stat", "currencyUSD", 0, 14, 8, 4),
            panel(7, "Anggaran token harian terpakai", [("max(llm_daily_budget_used_ratio)", "terpakai")], "stat", "percentunit", 8, 14, 8, 4),
            panel(8, "Log chat (tanpa teks pertanyaan)", [("{service='app-prod', msg='chat_turn'} | json", "")], "logs", y=18, w=24, ds=LOKI),
        ],
        "Mode jawaban, penolakan, fallback guardrail, token dan biaya LLM.",
    )
    dq = dashboard(
        "dk-data-quality",
        "Dua Kelinci - Kualitas data",
        [
            panel(1, "Baris bersih", [("dataset_rows{kind='clean'}", "bersih")], "stat", "short", 0, 0, 6, 4),
            panel(2, "Baris dikarantina", [("dataset_rows{kind='quarantined'}", "karantina")], "stat", "short", 6, 0, 6, 4),
            panel(3, "Unggahan ditolak (24 jam)", [("sum(increase(uploads_total{result='rejected'}[24h]))", "ditolak")], "stat", "short", 12, 0, 6, 4),
            panel(4, "Baris diproses (24 jam)", [("increase(rows_processed_total[24h])", "baris")], "stat", "short", 18, 0, 6, 4),
            panel(5, "Baris per aturan DQ (data aktif)", [("max by (rule_id) (dq_issue_rows) > 0", "{{rule_id}}")], "bargauge", "short", 0, 4, 12, 10),
            panel(6, "Tren temuan DQ", [("sum by (rule_id) (dq_issue_rows) > 0", "{{rule_id}}")], unit="short", x=12, y=4, h=10),
        ],
        "Temuan aturan DQ pada data aktif dan trennya setiap kali data diganti.",
    )
    return {"service-health.json": health, "sales-usage.json": usage, "chat-guardrails.json": chat, "data-quality.json": dq}


def rule(uid, title, expr, op, threshold, for_, summary, severity="warning"):
    return {
        "uid": uid,
        "title": title,
        "condition": "C",
        "for": for_,
        "labels": {"severity": severity, "service": "sales-insight"},
        "annotations": {"summary": summary},
        "noDataState": "OK",
        "execErrState": "Error",
        "data": [
            {"refId": "A", "relativeTimeRange": {"from": 900, "to": 0}, "datasourceUid": "prometheus", "model": {"refId": "A", "expr": expr, "instant": True}},
            {"refId": "B", "datasourceUid": "__expr__", "model": {"refId": "B", "type": "reduce", "expression": "A", "reducer": "last"}},
            {
                "refId": "C",
                "datasourceUid": "__expr__",
                "model": {"refId": "C", "type": "threshold", "expression": "B", "conditions": [{"evaluator": {"type": op, "params": [threshold]}}]},
            },
        ],
    }


def build_alerts() -> dict:
    rules = [
        rule(
            "dk-5xx",
            "Rasio error 5xx di atas 5%",
            "sum(rate(http_requests_total{status=~'5..'}[5m])) / clamp_min(sum(rate(http_requests_total[5m])), 1e-9)",
            "gt",
            0.05,
            "5m",
            "Lebih dari 5% request gagal 5xx dalam 5 menit.",
            "critical",
        ),
        rule(
            "dk-p95",
            "Latensi p95 di atas 2 detik",
            "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))",
            "gt",
            2,
            "10m",
            "Latensi p95 di atas 2 detik selama 10 menit.",
        ),
        rule(
            "dk-guardrail",
            "Lonjakan fallback guardrail",
            "sum(increase(guardrail_fallbacks_total[15m]))",
            "gt",
            5,
            "0m",
            "Lebih dari 5 jawaban AI diganti template dalam 15 menit. Cek model, prompt atau data.",
        ),
        rule(
            "dk-llm-budget",
            "Anggaran token LLM harian 80%",
            "max(llm_daily_budget_used_ratio)",
            "gt",
            0.8,
            "0m",
            "Pemakaian token LLM hari ini sudah di atas 80% anggaran.",
        ),
        rule(
            "dk-upload-fail",
            "Unggahan gagal berulang",
            "sum(increase(uploads_total{result='rejected'}[30m]))",
            "gt",
            3,
            "0m",
            "Lebih dari 3 unggahan ditolak dalam 30 menit. Mungkin format export berubah.",
        ),
        rule(
            "dk-down",
            "Aplikasi tidak bisa di-scrape",
            "up{job='dua-kelinci-app'}",
            "lt",
            1,
            "2m",
            "Prometheus tidak bisa membaca /metrics aplikasi selama 2 menit.",
            "critical",
        ),
    ]
    return {"apiVersion": 1, "groups": [{"orgId": 1, "name": "sales-insight", "folder": "Dua Kelinci", "interval": "1m", "rules": rules}]}


def to_yaml(obj, indent=0) -> str:
    """Tiny YAML writer for plain dicts/lists/scalars (JSON scalars are valid YAML)."""
    pad = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, dict | list) and v:
                lines.append(f"{pad}{k}:")
                lines.append(to_yaml(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {json.dumps(v, ensure_ascii=False)}")
        return "\n".join(lines)
    if isinstance(obj, list):
        lines = []
        for v in obj:
            if isinstance(v, dict | list):
                inner = to_yaml(v, indent + 1).lstrip()
                lines.append(f"{pad}- {inner}")
            else:
                lines.append(f"{pad}- {json.dumps(v, ensure_ascii=False)}")
        return "\n".join(lines)
    return f"{pad}{json.dumps(obj, ensure_ascii=False)}"


def main() -> None:
    DASH.mkdir(parents=True, exist_ok=True)
    for name, d in build_dashboards().items():
        (DASH / name).write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    ALERTS.write_text("# Generated by scripts/build_grafana.py\n" + to_yaml(build_alerts()) + "\n")
    print("ok")


if __name__ == "__main__":
    main()

"""Structured logs, Prometheus metrics, audit log and an optional Langfuse tracer.

Logs never contain question text, outlet-level personal data, passwords, tokens or cookies.
Langfuse is optional, sampled and non-blocking: if it is not installed, not configured or down,
every call here is a no-op and the request continues.
"""

from __future__ import annotations

import contextvars
import json
import logging
import random
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    root.setLevel(level)
    for name in ("uvicorn.access",):
        logging.getLogger(name).disabled = True  # replaced by our own access log without query strings


log = logging.getLogger("dk_sales")


def event(msg: str, **fields) -> None:
    log.info(msg, extra={"fields": fields})


# ---------------------------------------------------------------------------
# metrics


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        r = self.registry
        self.requests = Counter("http_requests_total", "HTTP requests", ["route", "method", "status"], registry=r)
        self.latency = Histogram(
            "http_request_duration_seconds", "HTTP latency", ["route", "method"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10), registry=r,
        )
        self.uploads = Counter("uploads_total", "File uploads", ["result"], registry=r)
        self.rows_processed = Counter("rows_processed_total", "Rows read from uploaded or startup files", registry=r)
        self.dq_issues = Gauge("dq_issue_rows", "Rows affected per DQ rule in the active dataset", ["rule_id"], registry=r)
        self.chat_turns = Counter("chat_turns_total", "Chat turns", ["mode", "intent"], registry=r)
        self.chat_refusals = Counter("chat_refusals_total", "Chat refusals", ["reason"], registry=r)
        self.guardrail_fallbacks = Counter("guardrail_fallbacks_total", "LLM output replaced by template", ["where", "reason"], registry=r)
        self.llm_tokens = Counter("llm_tokens_total", "LLM tokens", ["kind"], registry=r)
        self.llm_cost = Counter("llm_cost_usd_total", "Estimated LLM cost in USD", registry=r)
        self.llm_budget_used = Gauge("llm_daily_budget_used_ratio", "Share of daily LLM token budget used", registry=r)
        self.telegram_sends = Counter("telegram_sends_total", "Telegram sends", ["result"], registry=r)
        self.login_failures = Counter("login_failures_total", "Failed logins", registry=r)
        self.dataset_rows = Gauge("dataset_rows", "Rows in the active dataset", ["kind"], registry=r)


# ---------------------------------------------------------------------------
# audit log (separate file, append-only JSON lines)


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def write(self, action: str, user: str, outcome: str, **detail) -> None:
        rec = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "action": action,
            "user": user,
            "outcome": outcome,
            "request_id": request_id_var.get(),
            **detail,
        }
        line = json.dumps(rec, ensure_ascii=False, default=str)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            log.warning("audit log write failed", extra={"fields": {"action": action}})
        logging.getLogger("dk_sales.audit").info(action, extra={"fields": {"audit": True, "action": action, "outcome": outcome}})


# ---------------------------------------------------------------------------
# Langfuse (optional)


class Tracer:
    """Thin wrapper; every method swallows errors so tracing can never break a request."""

    def __init__(self, settings=None):
        self.client = None
        self.sample_rate = 1.0
        self.mask = True
        if settings is None or not getattr(settings, "langfuse_enabled", False):
            return
        self.sample_rate = settings.langfuse_sample_rate
        self.mask = not settings.log_question_text
        try:
            from langfuse import Langfuse

            self.client = Langfuse(
                host=settings.langfuse_host,
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                timeout=2,
            )
        except Exception:  # noqa: BLE001 - optional dependency or bad config must not stop the app
            log.warning("langfuse disabled: client init failed")
            self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def trace(self, name: str, **kwargs) -> TraceHandle:
        if not self.client or random.random() > self.sample_rate:
            return TraceHandle(None)
        try:
            span = self.client.start_span(name=name, **kwargs)
            return TraceHandle(span, self.client)
        except Exception:  # noqa: BLE001
            return TraceHandle(None)

    def flush(self) -> None:
        try:
            if self.client:
                self.client.flush()
        except Exception:  # noqa: BLE001
            pass


class TraceHandle:
    def __init__(self, span, client=None):
        self.span = span
        self.client = client
        self.started = time.perf_counter()

    def child(self, name: str, as_type: str = "span", **kwargs) -> TraceHandle:
        if not self.span:
            return TraceHandle(None)
        try:
            if as_type == "generation":
                return TraceHandle(self.span.start_generation(name=name, **kwargs), self.client)
            return TraceHandle(self.span.start_span(name=name, **kwargs), self.client)
        except Exception:  # noqa: BLE001
            return TraceHandle(None)

    def update(self, **kwargs) -> None:
        try:
            if self.span:
                self.span.update(**kwargs)
        except Exception:  # noqa: BLE001
            pass

    def score(self, name: str, value, comment: str | None = None) -> None:
        try:
            if self.span:
                self.span.score_trace(name=name, value=value, comment=comment)
        except Exception:  # noqa: BLE001
            pass

    def end(self, **kwargs) -> None:
        try:
            if self.span:
                if kwargs:
                    self.span.update(**kwargs)
                self.span.end()
        except Exception:  # noqa: BLE001
            pass

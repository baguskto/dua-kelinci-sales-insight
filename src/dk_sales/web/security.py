"""HTTP hardening: security headers, body size limit, rate limiting, CSRF, output escaping helpers."""

from __future__ import annotations

import hmac
import re
import secrets
import time
from collections import deque

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, hsts: bool = False):
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                extra = {
                    b"content-security-policy": CSP.encode(),
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=(), usb=()",
                    b"cross-origin-opener-policy": b"same-origin",
                    b"cross-origin-resource-policy": b"same-origin",
                    b"cache-control": b"no-store",
                }
                if self.hsts:
                    extra[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                existing = {k.lower() for k, _ in headers}
                path = scope.get("path", "")
                for k, v in extra.items():
                    if k == b"cache-control" and path.startswith("/static/"):
                        v = b"public, max-age=3600"
                    if k not in existing:
                        headers.append((k, v))
                headers = [(k, v) for k, v in headers if k.lower() != b"server"]
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodyLimitMiddleware:
    """Reject request bodies larger than max_bytes, including chunked bodies without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = Headers(scope=scope).get("content-length")
        if length and length.isdigit() and int(length) > self.max_bytes:
            await _plain(send, 413, "Ukuran request melebihi batas.")
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLarge:
            await _plain(send, 413, "Ukuran request melebihi batas.")


class BodyTooLarge(Exception):
    pass


async def _plain(send: Send, status: int, text: str) -> None:
    body = text.encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RateLimiter:
    """Sliding window per key, in memory. Good enough for one process; use the proxy for more."""

    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] > self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self._hits) > 10_000:  # bound memory
            for k in list(self._hits)[:1000]:
                self._hits.pop(k, None)
        return True

    def retry_after(self, key: str) -> int:
        q = self._hits.get(key)
        if not q:
            return 0
        return max(1, int(self.window_s - (time.monotonic() - q[0])))


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(session_token: str | None, supplied: str | None) -> bool:
    return bool(session_token and supplied and hmac.compare_digest(session_token, supplied))


_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")


def strip_control(text: str) -> str:
    """Remove control and bidi-override characters (used on chat input and on file values shown to an LLM)."""
    return _CONTROL.sub("", text)


def csv_safe(value: object) -> object:
    """Neutralise spreadsheet formula injection in exported cells (OWASP CSV injection)."""
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        # Keep plain negative numbers as numbers.
        if re.fullmatch(r"-\d+(\.\d+)?", value):
            return value
        return "'" + value
    return value

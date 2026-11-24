"""Optional Claude client for the chat and the summary polish.

Only used when ANTHROPIC_API_KEY is set. The `anthropic` package is an optional dependency
(`uv sync --extra llm`); without it the app runs in offline mode.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date

# USD per million tokens for the default model (Claude Haiku 4.5).
PRICE_PER_MTOK = {"input": 1.0, "output": 5.0}


@dataclass
class LLMResponse:
    content: list[dict]
    stop_reason: str
    input_tokens: int
    output_tokens: int

    @property
    def text(self) -> str:
        return "".join(b.get("text", "") for b in self.content if b.get("type") == "text").strip()

    @property
    def tool_uses(self) -> list[dict]:
        return [b for b in self.content if b.get("type") == "tool_use"]

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens * PRICE_PER_MTOK["input"] + self.output_tokens * PRICE_PER_MTOK["output"]) / 1e6


class LLMUnavailable(RuntimeError):
    pass


class AnthropicClient:
    def __init__(self, api_key: str, model: str, timeout_s: int, max_output_tokens: int):
        try:
            import anthropic
        except ImportError as exc:  # optional dependency
            raise LLMUnavailable("paket anthropic tidak terpasang (uv sync --extra llm)") from exc
        self._client = anthropic.Anthropic(api_key=api_key, timeout=float(timeout_s), max_retries=1)
        self.model = model
        self.max_output_tokens = max_output_tokens

    def create(self, system: str, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        kwargs = {"model": self.model, "max_tokens": self.max_output_tokens, "system": system, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        r = self._client.messages.create(**kwargs)  # type: ignore[call-overload]
        content = []
        for b in r.content:
            if b.type == "text":
                content.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                content.append({"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)})
        return LLMResponse(content, r.stop_reason or "", r.usage.input_tokens, r.usage.output_tokens)


class TokenBudget:
    """Hard daily token budget across all users (in-memory, resets at local midnight)."""

    def __init__(self, daily_limit: int):
        self.daily_limit = daily_limit
        self._day = date.today()
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        if date.today() != self._day:
            self._day = date.today()
            self._used = 0

    def available(self) -> bool:
        with self._lock:
            self._roll()
            return self._used < self.daily_limit

    def add(self, tokens: int) -> None:
        with self._lock:
            self._roll()
            self._used += tokens

    @property
    def used_ratio(self) -> float:
        return self._used / self.daily_limit if self.daily_limit else 1.0

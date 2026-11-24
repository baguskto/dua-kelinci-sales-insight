"""Runtime configuration from environment variables.

Development (default): no login, binds to 127.0.0.1, random secret per process.
Production (APP_ENV=production): refuses to start unless auth, a strong secret, allowed hosts and
HTTPS/proxy settings are configured. See docs/ops/configuration.md.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dk_sales import config


class ConfigError(RuntimeError):
    """Raised when the configuration is unsafe for the selected APP_ENV."""


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _int(env: dict, key: str, default: int) -> int:
    v = env.get(key, "")
    try:
        return int(v) if v.strip() else default
    except ValueError as exc:
        raise ConfigError(f"{key} harus angka bulat") from exc


def _list(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


@dataclass
class Settings:
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    secret_key_from_env: bool = False
    auth_mode: str = "none"  # none | local | oidc
    local_users_file: Path | None = None
    allowed_hosts: list[str] = field(default_factory=lambda: ["127.0.0.1", "localhost", "testserver"])
    force_https: bool = False
    trusted_proxies: list[str] = field(default_factory=list)
    session_ttl_minutes: int = 60
    data_file: Path = config.ROOT / "sales.csv"
    data_dir: Path = config.ROOT / "var"
    max_upload_mb: int = 10
    max_upload_rows: int = 200_000
    rate_limit_per_minute: int = 120
    chat_rate_per_minute: int = 10
    chat_max_question_chars: int = 500
    chat_max_tool_calls: int = 4
    chat_memory_turns: int = 3
    log_question_text: bool = False
    log_level: str = "INFO"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_timeout_s: int = 20
    llm_max_output_tokens: int = 600
    llm_daily_token_budget: int = 200_000
    llm_polish_summary: bool = False
    metrics_token: str = ""
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_sample_rate: float = 1.0
    oidc_tenant_id: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""
    oidc_role_claim: str = "roles"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_host and self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def audit_log_path(self) -> Path:
        return self.data_dir / "audit.jsonl"

    def validate(self) -> None:
        if self.app_env not in {"development", "production", "test"}:
            raise ConfigError("APP_ENV harus development, production atau test")
        if self.auth_mode not in {"none", "local", "oidc"}:
            raise ConfigError("AUTH_MODE harus none, local atau oidc")
        if not self.is_production:
            return
        problems = []
        if self.auth_mode == "none":
            problems.append("AUTH_MODE=none tidak boleh di production (pakai local atau oidc)")
        if not self.secret_key_from_env or len(self.secret_key) < 32 or len(set(self.secret_key)) < 10:
            problems.append("SECRET_KEY wajib diisi, minimal 32 karakter acak")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            problems.append("ALLOWED_HOSTS wajib diisi dengan nama host, bukan *")
        if not self.force_https:
            problems.append("FORCE_HTTPS=true wajib (aplikasi harus di belakang TLS)")
        if not self.trusted_proxies:
            problems.append("TRUSTED_PROXIES wajib diisi (alamat reverse proxy, mis. Caddy)")
        if self.auth_mode == "local" and (not self.local_users_file or not self.local_users_file.exists()):
            problems.append("LOCAL_USERS_FILE wajib menunjuk ke file akun yang ada")
        if self.auth_mode == "oidc" and not (self.oidc_tenant_id and self.oidc_client_id and self.oidc_client_secret and self.oidc_redirect_uri):
            problems.append("OIDC_TENANT_ID, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET dan OIDC_REDIRECT_URI wajib untuk AUTH_MODE=oidc")
        if not self.metrics_token or len(self.metrics_token) < 24:
            problems.append("METRICS_TOKEN wajib, minimal 24 karakter")
        if problems:
            raise ConfigError("Konfigurasi production tidak aman:\n- " + "\n- ".join(problems))


def from_env(env: dict | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    s = Settings()
    s.app_env = env.get("APP_ENV", "development").strip().lower() or "development"
    # Production runs in a container behind the proxy, so it listens on all interfaces of that container.
    s.host = env.get("HOST", "0.0.0.0" if s.is_production else "127.0.0.1")  # noqa: S104  # nosec B104 - container only, behind the proxy
    s.port = _int(env, "PORT", 8000)
    if env.get("SECRET_KEY"):
        s.secret_key = env["SECRET_KEY"]
        s.secret_key_from_env = True
    s.auth_mode = env.get("AUTH_MODE", "none").strip().lower()
    s.local_users_file = Path(env["LOCAL_USERS_FILE"]) if env.get("LOCAL_USERS_FILE") else None
    if env.get("ALLOWED_HOSTS") is not None:
        s.allowed_hosts = _list(env.get("ALLOWED_HOSTS"))
    elif s.is_production:
        s.allowed_hosts = []
    s.force_https = _bool(env.get("FORCE_HTTPS"), False)
    s.trusted_proxies = _list(env.get("TRUSTED_PROXIES"))
    s.session_ttl_minutes = _int(env, "SESSION_TTL_MINUTES", 60)
    if env.get("DATA_FILE"):
        s.data_file = Path(env["DATA_FILE"])
    if env.get("DATA_DIR"):
        s.data_dir = Path(env["DATA_DIR"])
    s.max_upload_mb = _int(env, "MAX_UPLOAD_MB", 10)
    s.max_upload_rows = _int(env, "MAX_UPLOAD_ROWS", 200_000)
    s.rate_limit_per_minute = _int(env, "RATE_LIMIT_PER_MINUTE", 120)
    s.chat_rate_per_minute = _int(env, "CHAT_RATE_PER_MINUTE", 10)
    s.chat_max_question_chars = _int(env, "CHAT_MAX_QUESTION_CHARS", 500)
    s.chat_max_tool_calls = _int(env, "CHAT_MAX_TOOL_CALLS", 4)
    s.chat_memory_turns = _int(env, "CHAT_MEMORY_TURNS", 3)
    s.log_question_text = _bool(env.get("LOG_QUESTION_TEXT"), False)
    s.log_level = env.get("LOG_LEVEL", "INFO").upper()
    s.telegram_bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    s.telegram_chat_id = env.get("TELEGRAM_CHAT_ID", "")
    s.anthropic_api_key = env.get("ANTHROPIC_API_KEY", "")
    s.llm_model = env.get("LLM_MODEL", s.llm_model) or s.llm_model
    s.llm_timeout_s = _int(env, "LLM_TIMEOUT_S", 20)
    s.llm_max_output_tokens = _int(env, "LLM_MAX_OUTPUT_TOKENS", 600)
    s.llm_daily_token_budget = _int(env, "LLM_DAILY_TOKEN_BUDGET", 200_000)
    s.llm_polish_summary = _bool(env.get("LLM_POLISH_SUMMARY"), False)
    s.metrics_token = env.get("METRICS_TOKEN", "")
    s.langfuse_host = env.get("LANGFUSE_HOST", "")
    s.langfuse_public_key = env.get("LANGFUSE_PUBLIC_KEY", "")
    s.langfuse_secret_key = env.get("LANGFUSE_SECRET_KEY", "")
    try:
        s.langfuse_sample_rate = float(env.get("LANGFUSE_SAMPLE_RATE", "1.0") or 1.0)
    except ValueError as exc:
        raise ConfigError("LANGFUSE_SAMPLE_RATE harus angka 0-1") from exc
    s.oidc_tenant_id = env.get("OIDC_TENANT_ID", "")
    s.oidc_client_id = env.get("OIDC_CLIENT_ID", "")
    s.oidc_client_secret = env.get("OIDC_CLIENT_SECRET", "")
    s.oidc_redirect_uri = env.get("OIDC_REDIRECT_URI", "")
    s.oidc_role_claim = env.get("OIDC_ROLE_CLAIM", "roles")
    s.validate()
    return s

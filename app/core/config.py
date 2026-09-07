from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Known-weak secret values that must never be used in production.
_WEAK_SECRET_KEYS = {
    "supersecretkey_change_me_in_production",
    "super-secret-key-change-in-production-please",
    "changeme",
    "secret",
    "your-secret-key",
}


class Settings(BaseSettings):
    database_url: str
    environment: str = "development"
    pgvector_extension: str = "vector"
    llm_provider: str = Field(
        default="groq",
        validation_alias=AliasChoices("LLM_PROVIDER", "GROQ_PROVIDER", "MISTRAL_PROVIDER"),
    )
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY"),
    )
    llm_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "GROQ_BASE_URL", "MISTRAL_BASE_URL"),
    )
    llm_model: str = Field(
        default="openai/gpt-oss-120b",
        validation_alias=AliasChoices("LLM_MODEL", "GROQ_MODEL", "MISTRAL_MODEL"),
    )
    llm_timeout: float = Field(
        default=60.0,
        validation_alias=AliasChoices("LLM_TIMEOUT", "GROQ_TIMEOUT", "MISTRAL_TIMEOUT"),
    )
    llm_temperature: float = Field(
        default=0.3,
        validation_alias=AliasChoices("LLM_TEMPERATURE", "GROQ_TEMPERATURE", "MISTRAL_TEMPERATURE"),
    )
    llm_max_tokens: int = Field(
        default=1024,
        validation_alias=AliasChoices("LLM_MAX_TOKENS", "GROQ_MAX_TOKENS", "MISTRAL_MAX_TOKENS"),
    )
    llm_optimization_max_tokens: int = Field(
        default=8192,
        validation_alias=AliasChoices(
            "LLM_OPTIMIZATION_MAX_TOKENS",
            "GROQ_OPTIMIZATION_MAX_TOKENS",
            "MISTRAL_OPTIMIZATION_MAX_TOKENS",
        ),
    )
    # Connect timeout for the shared OpenAI-compatible HTTP client. Kept short
    # and separate from the (long) read timeout so a dead/slow TCP+TLS
    # handshake fails fast instead of waiting the full llm_timeout.
    llm_connect_timeout: float = Field(
        default=5.0,
        validation_alias=AliasChoices("LLM_CONNECT_TIMEOUT", "GROQ_CONNECT_TIMEOUT", "MISTRAL_CONNECT_TIMEOUT"),
    )
    # Bounds for the process-wide shared httpx.AsyncClient connection pool
    # (reused across all LLM calls instead of opening a new TLS connection
    # per request). Keepalive lets warm connections be reused; max_connections
    # caps concurrent sockets so bursts can't exhaust ephemeral ports.
    httpx_max_connections: int = 100
    httpx_max_keepalive_connections: int = 20
    max_retries: int = 3
    # Prompt-injection hardening: when True, trusted instructions are sent as a
    # separate `system` chat message (user text stays in the `user` message) and
    # user-derived text has section delimiters (===, <<<, >>>, ```) neutralized
    # before interpolation. Set to False to restore the legacy single-message
    # prompt assembly unchanged.
    prompt_injection_protection: bool = True
    prompt_analysis_temperature: float = 0.2
    prompt_score_threshold: float = 5.0
    quality_threshold: float = 0.70
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k_results: int = 5
    similarity_threshold: float = 0.05
    role_match_threshold: float = 0.50
    mode_match_threshold: float = 0.50
    cache_model: bool = True
    enable_soft_delete: bool = True
    max_version_history: int = 50
    auto_generate_embedding: bool = True
    prompt_top_k: int = 10
    duplicate_threshold: float = 0.90
    enable_recommendations: bool = True
    enable_dev_auth_bypass: bool = False
    google_client_id: str = ""

    # JWT Authentication Config
    secret_key: str = "supersecretkey_change_me_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Cookie & CORS Config
    # Comma-separated list of allowed browser origins for CORS (credentials enabled).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Optional regex matching additional allowed origins (e.g. browser
    # extensions, whose chrome-extension://<id> origin varies between builds in
    # development). Wired to CORSMiddleware's allow_origin_regex, which — unlike
    # a "*" wildcard — is compatible with allow_credentials=True. Empty disables
    # regex matching. In production, pin the exact published extension origin.
    cors_origin_regex: str = ""
    # Name of the httpOnly cookie that carries the JWT access token.
    access_cookie_name: str = "promptiq_access_token"
    # Name of the httpOnly cookie that carries the JWT refresh token.
    refresh_cookie_name: str = "promptiq_refresh_token"
    # SameSite policy for the auth cookie. "lax" works for same-site dev
    # (localhost:3000 <-> localhost:8000). Set to "none" for cross-domain
    # production deployments (requires Secure, which is auto-enabled in prod).
    cookie_samesite: str = "lax"

    # Coarse global rate limiter (per client IP). Kept generous so normal
    # frontend traffic never trips it; disable via env if needed.
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 300
    rate_limit_window_seconds: int = 60

    # Tighter per-IP limit for the expensive LLM routes (enhance / analyze /
    # compare / tool-recommend). Each of these costs an upstream LLM call, so
    # they get their own bucket, far stricter than the coarse global limiter
    # above. Enforced by a Redis-backed limiter (shared across workers) that
    # falls back to a per-process counter when Redis is unavailable.
    llm_rate_limit_max_requests: int = 20
    llm_rate_limit_window_seconds: int = 60
    # Hard cap on the length of any single prompt field accepted by the LLM
    # routes. Oversized bodies are rejected at validation time (HTTP 422) before
    # they reach the model — bounding both memory use and per-request LLM cost.
    # Sized to comfortably fit a full deep-enhancement output (the LLM
    # optimization cap is 8192 tokens ~= 32k chars), since that output may be
    # re-submitted to /analyze or /compare — while still rejecting the multi-MB
    # bodies a cost/OOM attack would use. The per-IP LLM rate limit above is the
    # complementary control on sustained cost.
    max_prompt_chars: int = 40000

    # ── Database connection pool ──────────────────────────────────────────
    # Explicit pool sizing + health checks for the async engine. pool_pre_ping
    # discards connections a proxy/DB closed while idle (avoids stale-connection
    # 500s after quiet periods); pool_recycle proactively retires connections
    # before typical server-side idle timeouts. Keep
    # db_pool_size * WEB_CONCURRENCY below your Postgres max_connections.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: float = 30.0
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    # ── Redis (optional) ──────────────────────────────────────────────────
    # Empty redis_url (or redis_enabled=False) disables Redis entirely and the
    # app falls back to its original in-process behaviour. Nothing breaks when
    # Redis is absent or unreachable — see app/core/redis_client.py.
    # Upstash and most managed providers require TLS: use rediss://...
    redis_url: str = ""
    redis_enabled: bool = True
    redis_key_prefix: str = "promptiq"
    # Kept short on purpose: a slow Redis must never dominate request latency.
    redis_socket_timeout_seconds: float = 2.0
    redis_connect_timeout_seconds: float = 2.0
    redis_max_connections: int = 10
    # After this many consecutive failures, stop dialling Redis for the
    # cooldown window so a dead host can't add its timeout to every request.
    redis_circuit_breaker_threshold: int = 3
    redis_circuit_breaker_cooldown_seconds: int = 30

    # ── Cache TTLs, in seconds ────────────────────────────────────────────
    # Deliberately distinct per data type: each value is derived from how long
    # that specific data stays meaningful, not from one shared default.
    #
    # Auth state — TTL is a safety net; the stored timestamp remains the
    # authority, so each gets a small buffer over its logical lifetime.
    redis_ttl_otp: int = 960                  # 16 min = otp_expire_minutes(15) + 1
    redis_ttl_reset_token: int = 1080         # 18 min = reset token life(15) + 3
    # Outlives the OTP on purpose: a brute-forcer must not be able to clear
    # their failed-attempt count simply by waiting for the OTP to lapse.
    redis_ttl_otp_attempts: int = 2700        # 45 min
    #
    # Reference data — changes only when an admin approves a template, which
    # also means a manual flush is the real invalidation path.
    redis_ttl_roles_modes: int = 21600        # 6 hours
    #
    # Derived data — deterministic, so it never goes stale; TTLs here exist to
    # bound memory, and are ordered by payload size (smallest lives longest).
    redis_ttl_classification: int = 86400     # 24 hours; tiny JSON, temperature=0.0
    redis_ttl_embedding: int = 604800         # 7 days; ~3 KB per entry
    redis_ttl_tool_embeddings: int = 2592000  # 30 days; derived from a static table

    # SMTP & OTP Config
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@promptiq.com"
    otp_expire_minutes: int = 15
    smtp_host: str = "localhost"
    smtp_port: int = 587

    @property
    def SMTP_USER(self) -> str:
        return self.smtp_user

    @property
    def SMTP_PASSWORD(self) -> str:
        return self.smtp_password

    @property
    def FROM_EMAIL(self) -> str:
        return self.from_email

    @property
    def OTP_EXPIRE_MINUTES(self) -> int:
        return self.otp_expire_minutes

    @property
    def SMTP_HOST(self) -> str:
        return self.smtp_host

    @property
    def SMTP_PORT(self) -> int:
        return self.smtp_port

    # Map settings for jose library case sensitivity
    @property
    def SECRET_KEY(self) -> str:
        return self.secret_key

    @property
    def ALGORITHM(self) -> str:
        return self.algorithm

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.access_token_expire_minutes

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        return self.refresh_token_expire_days

    @property
    def REFRESH_COOKIE_NAME(self) -> str:
        return self.refresh_cookie_name

    @property
    def GOOGLE_CLIENT_ID(self) -> str:
        return self.google_client_id

    @property
    def prompt_analysis_model(self) -> str:
        return self.llm_model

    @property
    def mistral_api_key(self) -> str:
        return self.llm_api_key

    @property
    def mistral_model(self) -> str:
        return self.llm_model

    @property
    def mistral_timeout(self) -> float:
        return self.llm_timeout

    @property
    def mistral_temperature(self) -> float:
        return self.llm_temperature

    @property
    def mistral_max_tokens(self) -> int:
        return self.llm_max_tokens

    @property
    def mistral_optimization_max_tokens(self) -> int:
        return self.llm_optimization_max_tokens

    @property
    def mistral_connect_timeout(self) -> float:
        return self.llm_connect_timeout

    @property
    def GOOGLE_CLIENT_IDS(self) -> list[str]:
        return [value.strip() for value in self.google_client_id.split(",") if value.strip()]

    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def CORS_ORIGIN_REGEX(self) -> str | None:
        """Optional regex of allowed origins (e.g. chrome-extension://.*); None when unset."""
        return self.cors_origin_regex or None

    @property
    def COOKIE_SECURE(self) -> bool:
        """Auth cookie is marked Secure (HTTPS-only) in production."""
        return self.environment == "production"

    @model_validator(mode="after")
    def _enforce_production_security(self) -> "Settings":
        """Fail fast on insecure production configuration (VULN-002 / VULN-006)."""
        if self.environment == "production":
            if self.enable_dev_auth_bypass:
                raise ValueError(
                    "enable_dev_auth_bypass must be False in production."
                )
            if self.secret_key in _WEAK_SECRET_KEYS or len(self.secret_key) < 32:
                raise ValueError(
                    "secret_key must be a strong, unique value (>=32 chars) in production."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

def get_settings() -> Settings:
    return settings

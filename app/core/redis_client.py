"""
redis_client.py — Optional Redis backing for shared state and caching.

DESIGN CONTRACT — GRACEFUL DEGRADATION
======================================
Redis is strictly optional. Every helper in this module swallows connection
and protocol errors and reports a plain cache miss / no-op instead of
propagating. When ``redis_url`` is unset, ``redis_enabled`` is False, the
``redis`` package is missing, or the server is unreachable, the application
behaves exactly as it did before Redis was introduced.

**No request may ever fail because of Redis.**

A small circuit breaker keeps a hung or dead Redis from adding its socket
timeout to every request: after ``redis_circuit_breaker_threshold``
consecutive failures the client stops dialling for
``redis_circuit_breaker_cooldown_seconds``, then probes again. Without it a
single unreachable host would silently add seconds of latency to every
call — the opposite of why the cache exists.

Keys are namespaced ``<prefix>:<schema>:<namespace>:<id>``. Bumping
CACHE_SCHEMA_VERSION orphans every old entry, so a payload shape change
never requires a manual flush.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger("promptiq.redis")

# Bump this when a cached payload's *shape* changes. Old keys then become
# unreachable and expire on their own — no manual FLUSH needed.
CACHE_SCHEMA_VERSION = "v1"

# ── Key namespaces (kept short; they appear in every key) ────────────────
NS_OTP = "otp"              # email -> {otp, expires_at}
NS_OTP_ATTEMPTS = "otpat"   # email -> failed-verification counter
NS_RESET_JTI = "rjti"       # jti   -> issued password-reset token
NS_ROLES = "roles"          # distinct template roles
NS_MODES = "modes"          # distinct template modes
NS_ROLE_MODES = "rmodes"    # modes scoped to one role
NS_CLASSIFY = "cls"         # prompt hash -> {level, reason}
NS_EMBED = "emb"            # text hash   -> embedding vector
NS_TOOL_EMBED = "toolemb"   # tool-ranking task embeddings

# ── Module state ─────────────────────────────────────────────────────────
_client: Any = None
_client_lock: Optional[asyncio.Lock] = None
_missing_package_logged = False

# Circuit breaker
_consecutive_failures = 0
_circuit_open_until = 0.0


def _get_lock() -> asyncio.Lock:
    """Lazily create the init lock.

    Created on first use rather than at import time so it always binds to
    the running event loop.
    """
    global _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    return _client_lock


def is_configured() -> bool:
    """True when Redis is switched on and a URL is present."""
    return bool(settings.redis_enabled and settings.redis_url.strip())


def _circuit_open() -> bool:
    return time.monotonic() < _circuit_open_until


def _record_failure(exc: BaseException, op: str) -> None:
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures += 1
    if _consecutive_failures >= settings.redis_circuit_breaker_threshold:
        _circuit_open_until = (
            time.monotonic() + settings.redis_circuit_breaker_cooldown_seconds
        )
        logger.warning(
            "Redis unreachable after %d consecutive failures (last op=%s: %s). "
            "Pausing Redis use for %ds — the app continues without it.",
            _consecutive_failures,
            op,
            exc,
            settings.redis_circuit_breaker_cooldown_seconds,
        )
    else:
        logger.debug("Redis op '%s' failed: %s", op, exc)


def _record_success() -> None:
    global _consecutive_failures, _circuit_open_until
    if _consecutive_failures or _circuit_open_until:
        logger.info("Redis is responding again; cache re-enabled.")
    _consecutive_failures = 0
    _circuit_open_until = 0.0


async def get_client() -> Any:
    """Return a live Redis client, or None when Redis is unavailable.

    Never raises. A None return is the caller's signal to take the
    pre-Redis code path.
    """
    global _client, _missing_package_logged

    if not is_configured() or _circuit_open():
        return None
    if _client is not None:
        return _client

    async with _get_lock():
        # Another coroutine may have connected while we waited.
        if _client is not None:
            return _client

        try:
            from redis.asyncio import Redis  # optional dependency
        except Exception:
            if not _missing_package_logged:
                logger.warning(
                    "redis_url is set but the 'redis' package is not installed; "
                    "running without Redis."
                )
                _missing_package_logged = True
            return None

        try:
            client = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=settings.redis_socket_timeout_seconds,
                socket_connect_timeout=settings.redis_connect_timeout_seconds,
                max_connections=settings.redis_max_connections,
                health_check_interval=30,
            )
            await client.ping()
        except Exception as exc:
            _record_failure(exc, "connect")
            return None

        _client = client
        _record_success()
        logger.info(
            "Redis connected (prefix=%s schema=%s).",
            settings.redis_key_prefix,
            CACHE_SCHEMA_VERSION,
        )
        return _client


async def close_client() -> None:
    """Close the pooled connection. Safe to call when never connected."""
    global _client
    client, _client = _client, None
    if client is None:
        return
    try:
        # redis-py >= 5 exposes aclose(); older builds only have close().
        closer = getattr(client, "aclose", None) or getattr(client, "close", None)
        if closer is not None:
            await closer()
    except Exception:
        logger.debug("Redis close failed", exc_info=True)


# ── Key helpers ──────────────────────────────────────────────────────────

def make_key(namespace: str, *parts: Any) -> str:
    """Build a namespaced, schema-versioned key."""
    return ":".join(
        (settings.redis_key_prefix, CACHE_SCHEMA_VERSION, namespace, *(str(p) for p in parts))
    )


def hash_text(text: str) -> str:
    """Stable short digest for content-addressed keys.

    128 bits of SHA-256 — collision risk is negligible and it keeps keys
    short enough to stay readable in redis-cli.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


# ── Operations (all non-raising) ─────────────────────────────────────────

async def get_json(key: str) -> Any:
    """Fetch and decode a JSON value. None means miss OR Redis unavailable."""
    client = await get_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        _record_success()
    except Exception as exc:
        _record_failure(exc, "get")
        return None

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        # A malformed entry would otherwise keep failing forever.
        logger.warning("Discarding malformed cache entry at %s", key)
        await delete(key)
        return None


async def set_json(key: str, value: Any, ttl: int) -> bool:
    """Store a JSON value with an expiry. Returns False when not stored."""
    client = await get_client()
    if client is None:
        return False
    try:
        # No `default=` fallback on purpose: a value that isn't already plain
        # JSON is refused here (and logged) rather than silently stringified,
        # written, and then rejected by the reader's validation on every hit
        # until it expires. Callers pass primitives only.
        payload = json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError):
        logger.warning("Value for %s is not JSON-serialisable; skipping cache.", key)
        return False
    try:
        await client.set(key, payload, ex=max(1, int(ttl)))
        _record_success()
        return True
    except Exception as exc:
        _record_failure(exc, "set")
        return False


async def delete(*keys: str) -> None:
    """Delete keys, ignoring absent ones and any failure."""
    if not keys:
        return
    client = await get_client()
    if client is None:
        return
    try:
        await client.delete(*keys)
        _record_success()
    except Exception as exc:
        _record_failure(exc, "delete")


async def incr_with_ttl(key: str, ttl: int) -> Optional[int]:
    """Atomically increment a counter and refresh its expiry.

    Returns the new count, or None when Redis is unavailable so the caller
    can fall back to its local counter.
    """
    client = await get_client()
    if client is None:
        return None
    try:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, max(1, int(ttl)))
        result = await pipe.execute()
        _record_success()
        return int(result[0])
    except Exception as exc:
        _record_failure(exc, "incr")
        return None


async def incr_fixed_window(key: str, window_seconds: int) -> Optional[int]:
    """Increment a fixed-window counter, setting the expiry only when the
    window first opens (count == 1).

    Unlike :func:`incr_with_ttl`, the TTL is *not* refreshed on every hit, so
    the window is a true fixed interval that resets ``window_seconds`` after the
    first request rather than sliding forward on each call. Returns the new
    count, or None when Redis is unavailable so the caller can fall back to a
    local counter.
    """
    client = await get_client()
    if client is None:
        return None
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, max(1, int(window_seconds)))
        _record_success()
        return int(count)
    except Exception as exc:
        _record_failure(exc, "incr_fixed_window")
        return None


async def ping() -> bool:
    """Round-trip check for /health."""
    client = await get_client()
    if client is None:
        return False
    try:
        await client.ping()
        _record_success()
        return True
    except Exception as exc:
        _record_failure(exc, "ping")
        return False


def status() -> str:
    """Current state for /health. Does no network I/O.

    disabled | not_configured | unavailable | idle | connected
    """
    if not settings.redis_enabled:
        return "disabled"
    if not settings.redis_url.strip():
        return "not_configured"
    if _circuit_open():
        return "unavailable"
    return "connected" if _client is not None else "idle"

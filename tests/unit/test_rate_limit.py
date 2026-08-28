"""Unit tests for app/middleware/rate_limit.py.

Three independent limiters live in this module and the suite depends on all of
them: the coarse global middleware is *disabled* for tests (every request shares
one client IP, so 300/60s would trip partway through a run), the 5/60s
``sensitive_rate_limiter`` is why the auth fixtures mint tokens instead of
logging in, and ``llm_rate_limiter`` guards every enhance route.

Time is injected by replacing the module-global ``time`` name with a fake clock.
Patching ``time.monotonic`` itself would also re-time the asyncio event loop.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app.core import redis_client
from app.core.config import settings
from app.middleware import rate_limit as rate_limit_module
from app.middleware.rate_limit import (
    RateLimiter,
    RateLimitMiddleware,
    RedisBackedRateLimiter,
    llm_rate_limiter,
    sensitive_rate_limiter,
)
from tests.unit.asgi_helpers import (
    FakeClock,
    RecordingApp,
    SendRecorder,
    make_request,
    make_scope,
    noop_receive,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(rate_limit_module, "time", fake)
    return fake


# ─────────────────────────────────────────────────────────────────────────────
# Wiring of the shared singletons
# ─────────────────────────────────────────────────────────────────────────────


def test_sensitive_limiter_is_five_per_minute() -> None:
    """The number the auth fixtures are designed around.

    If this ever loosens, ``tests/conftest.py`` can stop minting tokens directly
    and the dedicated auth tests can stop rationing their login attempts.
    """
    assert sensitive_rate_limiter.max_requests == 5
    assert sensitive_rate_limiter.window_seconds == 60


def test_llm_limiter_is_configured_from_settings() -> None:
    assert llm_rate_limiter.max_requests == settings.llm_rate_limit_max_requests
    assert llm_rate_limiter.window_seconds == settings.llm_rate_limit_window_seconds
    assert llm_rate_limiter.scope == "llm"


# ─────────────────────────────────────────────────────────────────────────────
# RateLimiter — the per-endpoint dependency
# ─────────────────────────────────────────────────────────────────────────────


async def test_requests_up_to_the_cap_are_allowed(clock: FakeClock) -> None:
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    request = make_request()

    for _ in range(3):
        assert await limiter(request) is None


async def test_the_request_after_the_cap_is_429(clock: FakeClock) -> None:
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    request = make_request()
    for _ in range(3):
        await limiter(request)

    with pytest.raises(HTTPException) as exc_info:
        await limiter(request)

    assert exc_info.value.status_code == 429
    assert "Too many requests" in exc_info.value.detail


async def test_a_rejected_request_does_not_consume_a_slot(clock: FakeClock) -> None:
    """A blocked caller must not extend their own lockout.

    The window is only advanced by *allowed* hits, so the bucket drains a fixed
    ``window_seconds`` after the first accepted request no matter how hard the
    caller hammers it in between.
    """
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    request = make_request()
    await limiter(request)

    for _ in range(5):
        with pytest.raises(HTTPException):
            await limiter(request)

    clock.advance(61)
    assert await limiter(request) is None


async def test_the_window_slides(clock: FakeClock) -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    request = make_request()
    await limiter(request)
    clock.advance(30)
    await limiter(request)

    # 30s in: both hits are still inside the window.
    with pytest.raises(HTTPException):
        await limiter(request)

    # 31s later the first hit has aged out, so exactly one slot frees up.
    clock.advance(31)
    assert await limiter(request) is None
    with pytest.raises(HTTPException):
        await limiter(request)


async def test_a_hit_exactly_at_the_window_edge_has_expired(clock: FakeClock) -> None:
    """The comparison is ``now - ts < window``, so ``==`` counts as expired."""
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    request = make_request()
    await limiter(request)

    clock.advance(60)

    assert await limiter(request) is None


async def test_each_path_gets_its_own_bucket(clock: FakeClock) -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(make_request(path="/api/v1/auth/login"))

    with pytest.raises(HTTPException):
        await limiter(make_request(path="/api/v1/auth/login"))

    assert await limiter(make_request(path="/api/v1/auth/register")) is None


async def test_each_client_ip_gets_its_own_bucket(clock: FakeClock) -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(make_request(client_ip="198.51.100.1"))

    with pytest.raises(HTTPException):
        await limiter(make_request(client_ip="198.51.100.1"))

    assert await limiter(make_request(client_ip="198.51.100.2")) is None


async def test_clientless_requests_share_one_unknown_bucket(clock: FakeClock) -> None:
    """Behind a proxy that strips the peer address, everyone is ``unknown``.

    Worth pinning: the limit then applies to that entire population at once,
    which is protective but also a shared-fate denial-of-service.
    """
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(make_request(client_ip=None))

    with pytest.raises(HTTPException):
        await limiter(make_request(client_ip=None, path=make_scope()["path"]))


async def test_the_query_string_does_not_split_the_bucket(clock: FakeClock) -> None:
    """Keyed on ``url.path``, so ``?a=1`` cannot be used to mint fresh buckets."""
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(make_request(path="/api/v1/auth/login"))

    request = make_request(path="/api/v1/auth/login")
    request.scope["query_string"] = b"cache-buster=1"

    with pytest.raises(HTTPException):
        await limiter(request)


# ─────────────────────────────────────────────────────────────────────────────
# RateLimitMiddleware — the coarse global limiter
# ─────────────────────────────────────────────────────────────────────────────


async def test_middleware_forwards_requests_under_the_cap(clock: FakeClock) -> None:
    inner = RecordingApp()
    middleware = RateLimitMiddleware(inner, max_requests=2, window_seconds=60)

    for _ in range(2):
        await middleware(make_scope(), noop_receive, SendRecorder())

    assert len(inner.calls) == 2


async def test_middleware_returns_a_json_429_past_the_cap(clock: FakeClock) -> None:
    inner = RecordingApp()
    middleware = RateLimitMiddleware(inner, max_requests=1, window_seconds=60)
    await middleware(make_scope(), noop_receive, SendRecorder())
    forwarded_before = len(inner.calls)

    recorder = SendRecorder()
    await middleware(make_scope(), noop_receive, recorder)

    assert recorder.status == 429
    assert json.loads(recorder.body) == {
        "success": False,
        "error": "Too many requests. Please try again later.",
    }
    assert recorder.header("content-type") == b"application/json"
    # A wrong content-length here would hang or truncate the client rather than
    # produce a visible error, so it is worth asserting explicitly.
    assert recorder.header("content-length") == str(len(recorder.body)).encode()
    # The first request was under the cap and legitimately reached the app; the
    # second must not have, so the count is unchanged.
    assert len(inner.calls) == forwarded_before == 1, (
        "the blocked request still reached the application"
    )


async def test_middleware_isolates_client_ips(clock: FakeClock) -> None:
    inner = RecordingApp()
    middleware = RateLimitMiddleware(inner, max_requests=1, window_seconds=60)
    await middleware(make_scope(client_ip="198.51.100.1"), noop_receive, SendRecorder())

    blocked, allowed = SendRecorder(), SendRecorder()
    await middleware(make_scope(client_ip="198.51.100.1"), noop_receive, blocked)
    await middleware(make_scope(client_ip="198.51.100.2"), noop_receive, allowed)

    assert blocked.status == 429
    assert allowed.status == 200


async def test_middleware_ignores_the_path(clock: FakeClock) -> None:
    """Global by design: one budget per IP across every endpoint, unlike
    ``RateLimiter``, which buckets per path."""
    inner = RecordingApp()
    middleware = RateLimitMiddleware(inner, max_requests=1, window_seconds=60)
    await middleware(make_scope(path="/health"), noop_receive, SendRecorder())

    recorder = SendRecorder()
    await middleware(make_scope(path="/api/v1/templates"), noop_receive, recorder)

    assert recorder.status == 429


async def test_middleware_lets_non_http_scopes_straight_through(
    clock: FakeClock,
) -> None:
    """Lifespan and websocket scopes have no client and must not be counted."""
    inner = RecordingApp()
    middleware = RateLimitMiddleware(inner, max_requests=1, window_seconds=60)

    for _ in range(3):
        await middleware(
            make_scope(scope_type="lifespan", client_ip=None), noop_receive, SendRecorder()
        )

    assert len(inner.calls) == 3


async def test_middleware_window_expires(clock: FakeClock) -> None:
    inner = RecordingApp()
    middleware = RateLimitMiddleware(inner, max_requests=1, window_seconds=60)
    await middleware(make_scope(), noop_receive, SendRecorder())

    clock.advance(61)
    recorder = SendRecorder()
    await middleware(make_scope(), noop_receive, recorder)

    assert recorder.status == 200


# ─────────────────────────────────────────────────────────────────────────────
# RedisBackedRateLimiter
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def redis_counter(monkeypatch: pytest.MonkeyPatch):
    """Replace the Redis fixed-window counter with an in-memory equivalent.

    Returns the dict of observed keys so a test can assert how the bucket was
    namespaced — the part that decides whether the cap is really per-IP.
    """
    counts: dict[str, int] = {}

    async def fake_incr(key: str, window_seconds: int) -> int:
        counts[key] = counts.get(key, 0) + 1
        return counts[key]

    monkeypatch.setattr(redis_client, "incr_fixed_window", fake_incr)
    return counts


async def test_redis_path_allows_up_to_the_cap_then_429s(redis_counter) -> None:
    limiter = RedisBackedRateLimiter(max_requests=2, window_seconds=60)
    request = make_request()

    assert await limiter(request) is None
    assert await limiter(request) is None
    with pytest.raises(HTTPException) as exc_info:
        await limiter(request)

    assert exc_info.value.status_code == 429


async def test_redis_key_namespaces_by_scope_path_and_ip(redis_counter) -> None:
    limiter = RedisBackedRateLimiter(max_requests=10, window_seconds=60, scope="llm")

    await limiter(make_request(path="/api/v1/enhance", client_ip="198.51.100.7"))

    (key,) = redis_counter
    assert key == redis_client.make_key("rl", "llm", "/api/v1/enhance", "198.51.100.7")


async def test_redis_path_isolates_ips(redis_counter) -> None:
    limiter = RedisBackedRateLimiter(max_requests=1, window_seconds=60)
    await limiter(make_request(client_ip="198.51.100.1"))

    with pytest.raises(HTTPException):
        await limiter(make_request(client_ip="198.51.100.1"))

    assert await limiter(make_request(client_ip="198.51.100.2")) is None


async def test_it_never_fails_open_when_redis_is_unavailable(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``None`` from Redis must fall back to the local counter, not skip the check.

    This is the documented contract of the class and the reason the suite can run
    with ``redis_enabled=False`` while the limiter is still enforced.
    """

    async def unavailable(key: str, window_seconds: int) -> None:
        return None

    monkeypatch.setattr(redis_client, "incr_fixed_window", unavailable)
    limiter = RedisBackedRateLimiter(max_requests=2, window_seconds=60)
    request = make_request()

    assert await limiter(request) is None
    assert await limiter(request) is None
    with pytest.raises(HTTPException) as exc_info:
        await limiter(request)

    assert exc_info.value.status_code == 429


async def test_the_local_fallback_keeps_its_own_window(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unavailable(key: str, window_seconds: int) -> None:
        return None

    monkeypatch.setattr(redis_client, "incr_fixed_window", unavailable)
    limiter = RedisBackedRateLimiter(max_requests=1, window_seconds=60)
    await limiter(make_request())

    clock.advance(61)

    assert await limiter(make_request()) is None

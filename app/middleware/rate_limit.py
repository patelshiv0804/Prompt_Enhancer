"""
In-memory rate limiting.

Provides two layers:
  * ``RateLimitMiddleware`` — a coarse global sliding-window limiter (pure ASGI)
    that guards against blunt request floods.
  * ``RateLimiter`` — a reusable FastAPI dependency for strict per-endpoint
    limits (e.g. login / OTP) to defeat brute-force attacks (VULN-005).

Both use an ``asyncio.Lock`` around their bookkeeping so counters stay correct
under concurrent requests within a worker (VULN-012). State is per-process:
for multi-worker / multi-container deployments, back this with Redis instead.
"""

import asyncio
import json
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core import redis_client
from app.core.config import settings


class RateLimitMiddleware:
    """Simple sliding-window rate limiter (pure ASGI), keyed by client IP."""

    def __init__(self, app: ASGIApp, max_requests: int = 300, window_seconds: int = 60):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        now = time.monotonic()

        async with self._lock:
            recent = [
                ts for ts in self._requests[client_ip]
                if now - ts < self.window_seconds
            ]
            allowed = len(recent) < self.max_requests
            if allowed:
                recent.append(now)
            self._requests[client_ip] = recent

        if not allowed:
            body = json.dumps({
                "success": False,
                "error": "Too many requests. Please try again later.",
            }).encode()
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        await self.app(scope, receive, send)


class RateLimiter:
    """Strict per-endpoint rate-limit dependency.

    Buckets are keyed by (route path, client IP) so each endpoint gets its own
    independent window. Use as a route dependency:

        dependencies=[Depends(sensitive_rate_limiter)]
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def __call__(self, request: Request) -> None:
        client = request.client
        client_ip = client.host if client else "unknown"
        key = f"{request.url.path}:{client_ip}"
        now = time.monotonic()

        async with self._lock:
            recent = [ts for ts in self._hits[key] if now - ts < self.window_seconds]
            if len(recent) >= self.max_requests:
                self._hits[key] = recent
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down and try again shortly.",
                )
            recent.append(now)
            self._hits[key] = recent


# Shared strict limiter for sensitive auth / OTP endpoints (5 requests / minute per IP).
sensitive_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)


class RedisBackedRateLimiter:
    """Per-IP limiter for expensive endpoints, coordinated across workers.

    Uses a Redis fixed-window counter (shared by every worker and container)
    when Redis is available, so the limit holds globally rather than per
    process. When Redis is down or disabled, it falls back to an in-process
    ``RateLimiter`` — still protective, just not coordinated across workers.
    It never fails open: a Redis error degrades to the local limiter rather
    than skipping the check.

    Use as a route dependency:

        dependencies=[Depends(llm_rate_limiter)]
    """

    def __init__(self, max_requests: int, window_seconds: int, scope: str = "llm"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope
        # Per-process fallback used when Redis is unavailable.
        self._local = RateLimiter(max_requests, window_seconds)

    async def __call__(self, request: Request) -> None:
        client = request.client
        client_ip = client.host if client else "unknown"
        key = redis_client.make_key("rl", self.scope, request.url.path, client_ip)
        count = await redis_client.incr_fixed_window(key, self.window_seconds)
        if count is None:
            # Redis unavailable — enforce with the per-process limiter instead.
            await self._local(request)
            return
        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
            )


# Strict limiter for the expensive LLM routes (enhance / analyze / compare /
# tool-recommend). Redis-backed so the cap holds across all workers; falls back
# to a per-process counter when Redis is absent.
llm_rate_limiter = RedisBackedRateLimiter(
    max_requests=settings.llm_rate_limit_max_requests,
    window_seconds=settings.llm_rate_limit_window_seconds,
)

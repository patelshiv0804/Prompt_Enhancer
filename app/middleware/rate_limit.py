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

"""
Simple in-memory rate limiter middleware — Pure ASGI implementation.
"""

import json
import time
from collections import defaultdict

from starlette.types import ASGIApp, Receive, Scope, Send


class RateLimitMiddleware:
    """
    Simple sliding-window rate limiter (pure ASGI).
    In production, use Redis-based rate limiting.
    """

    def __init__(self, app: ASGIApp, max_requests: int = 100, window_seconds: int = 60):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        now = time.time()

        # Clean old entries
        self._requests[client_ip] = [
            ts
            for ts in self._requests[client_ip]
            if now - ts < self.window_seconds
        ]

        # Check rate limit
        if len(self._requests[client_ip]) >= self.max_requests:
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

        # Record this request
        self._requests[client_ip].append(now)

        await self.app(scope, receive, send)

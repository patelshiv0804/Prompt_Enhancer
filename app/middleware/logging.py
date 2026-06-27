"""
Request/response logging middleware — Pure ASGI implementation.
"""

import time
from starlette.types import ASGIApp, Receive, Scope, Send
import logging

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """Log all incoming requests and their response times (pure ASGI)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_host = client[0] if client else "unknown"

        logger.info(f"→ {method} {path} (client: {client_host})")

        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Add timing header
                duration_ms = (time.time() - start_time) * 1000
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-response-time", f"{duration_ms:.1f}ms".encode())
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"← {method} {path} → {status_code} ({duration_ms:.1f}ms)")

"""
Request/response logging middleware with Correlation ID support — Pure ASGI implementation.
"""

import time
import uuid
import logging
from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.logging_context import set_correlation_id, get_correlation_id

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """Log all incoming requests, tracking and injecting Correlation IDs (pure ASGI)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract correlation ID from request headers or generate a new one
        headers_dict = {h[0].lower(): h[1] for h in scope.get("headers", [])}
        correlation_id = headers_dict.get(b"x-correlation-id", headers_dict.get(b"x-request-id"))
        
        if correlation_id:
            corr_id_str = correlation_id.decode("utf-8", errors="ignore")
        else:
            corr_id_str = str(uuid.uuid4())

        # Set correlation ID context variable
        set_correlation_id(corr_id_str)

        start_time = time.time()
        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_host = client[0] if client else "unknown"

        logger.info(f"[{corr_id_str}] → {method} {path} (client: {client_host})")

        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration_ms = (time.time() - start_time) * 1000
                headers = list(message.get("headers", []))
                
                # Append Response Time and Correlation ID headers
                headers.append((b"x-response-time", f"{duration_ms:.1f}ms".encode()))
                headers.append((b"x-correlation-id", corr_id_str.encode()))
                
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[{corr_id_str}] ← {method} {path} → {status_code} ({duration_ms:.1f}ms)")

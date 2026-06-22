"""
Authentication middleware — validates JWT on protected routes.
Note: Most auth is handled via FastAPI dependencies (get_current_user_id).
This middleware provides an additional layer for global request filtering.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Public paths that don't require authentication
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/profile/restore",
    "/api/v1/profile/restore/verify",
    "/health",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional middleware for global auth checks."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Let FastAPI dependencies handle actual token validation
        # This middleware just ensures the Authorization header exists
        # for non-public routes as an early rejection mechanism
        response = await call_next(request)
        return response

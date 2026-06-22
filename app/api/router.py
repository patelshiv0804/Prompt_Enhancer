"""
Central API router — aggregates all v1 module routers.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as profile_router
from app.modules.users.settings_router import router as settings_router

# ── Main API router ──────────────────────────────────────
api_router = APIRouter(prefix="/api/v1")

# Register module routers
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(settings_router)

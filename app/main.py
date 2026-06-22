"""
Prompt Enhancer — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppException, app_exception_handler, generic_exception_handler
from app.core.logger import logger
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()


# ── Lifespan ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Create upload directory if it doesn't exist
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "avatars").mkdir(parents=True, exist_ok=True)

    yield

    logger.info(f"👋 Shutting down {settings.APP_NAME}")


# ── App factory ──────────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered prompt optimization and management platform",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom middleware (pure ASGI — order matters, last added = first to run) ──
    # Rate limiting runs first (outermost), then logging
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(
        RateLimitMiddleware,
        max_requests=1000 if settings.DEBUG else 100,
        window_seconds=60,
    )

    # ── Exception handlers ───────────────────────────────
    application.add_exception_handler(AppException, app_exception_handler)
    application.add_exception_handler(Exception, generic_exception_handler)

    # ── Static files (uploads) ───────────────────────────
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    application.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

    # ── Routes ───────────────────────────────────────────
    application.include_router(api_router)

    # ── Health check ─────────────────────────────────────
    @application.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "version": settings.APP_VERSION}

    return application


# ── Create the app instance ──────────────────────────────
app = create_app()

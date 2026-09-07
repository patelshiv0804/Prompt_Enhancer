import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.router import api_router
from app.core import redis_client
from app.core.config import settings
from app.core.exceptions import http_error_handler
from app.core.logging import setup_logging
from app.db.session import ensure_vector_indexes, verify_database_startup
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger("promptiq.startup")


async def _warm_embedding_model() -> None:
    """Preload the sentence-transformers embedding model at startup so the first
    user request doesn't pay the multi-second cold-load cost. The load is
    CPU-bound and synchronous, so it runs in a worker thread to avoid blocking
    the event loop. Failures are non-fatal — the model then loads lazily on
    first use."""
    try:
        from app.services.embedding_service import EmbeddingService

        service = EmbeddingService()
        await asyncio.to_thread(lambda: service.model)
        logger.info("Embedding model preloaded at startup.")
    except Exception:
        logger.exception(
            "Embedding model warmup failed; it will load lazily on first use."
        )

API_DESCRIPTION = """
# PromptIQ API Backend

Welcome to the **PromptIQ** API documentation. PromptIQ is an advanced prompt optimization, template management, and version control platform.

### Key Features:
* **AI Model Repository**: Manage provider configurations and specific model capability flags.
* **Profiles Directory**: Track active user profiles and authentication details.
* **Template Retrieval Engine**: Maintain prompt enhancement templates and retrieve them semantically using **pgvector** vector similarity search.
* **Prompt Optimization Pipeline**: Analyze prompt quality, apply contextual templates, optimize prompts via LLMs, and auto-grade prompt clarity.
* **Prompt Versioning**: Maintain an audit trail of prompt version histories with complete conflict-free restoration.

### Authentication
Protected endpoints require a valid JWT. Browser clients are authenticated via a secure
httpOnly cookie set at login; API clients may also send `Authorization: Bearer <token>`.
"""


def create_app() -> FastAPI:
    setup_logging()
    is_production = settings.environment == "production"
    app = FastAPI(
        title="PromptIQ API",
        description=API_DESCRIPTION,
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        # Do not expose the OpenAPI schema (and therefore the docs) in production (VULN-008).
        openapi_url=None if is_production else "/openapi.json",
        swagger_ui_parameters={
            "syntaxHighlight.theme": "obsidian",
            "defaultModelsExpandDepth": 1,
            "docExpansion": "list",
        },
    )

    # Coarse global rate limiter (VULN-012 / N3). Registered before CORS so its
    # 429 responses still pass back out through the CORS layer.
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            max_requests=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

    # Specific-origin CORS with credentials (VULN-003). Wildcard origins are
    # incompatible with credentialed cookie auth and are rejected by browsers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Correlation-ID + access logging. Added last so it wraps every other
    # middleware (outermost): a correlation id is assigned before anything else
    # runs and the timing/log covers the full request, including the CORS and
    # rate-limit layers. Emits x-correlation-id and x-response-time response
    # headers so a production request can be traced end-to-end (N8).
    app.add_middleware(LoggingMiddleware)

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html() -> HTMLResponse:
        # Interactive docs are disabled in production (VULN-008).
        if is_production:
            raise HTTPException(status_code=404, detail="Not Found")
        response = get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=app.title + " - Interactive API Documentation",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )
        
        custom_css = """
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            html {
                box-sizing: border-box;
            }
            body {
                margin: 0;
                background: #0f172a !important;
            }
            .swagger-ui {
                background-color: #0f172a !important;
                color: #cbd5e1 !important;
                font-family: 'Inter', sans-serif !important;
            }
            .swagger-ui .topbar {
                background-color: #0b0f19 !important;
                border-bottom: 1px solid #1e293b !important;
                padding: 12px 0;
            }
            .swagger-ui .info .title {
                color: #f8fafc !important;
                font-family: 'Outfit', sans-serif !important;
                font-weight: 700 !important;
            }
            .swagger-ui .info p, .swagger-ui .info a, .swagger-ui .info li {
                color: #94a3b8 !important;
            }
            .swagger-ui .opblock-tag {
                color: #f8fafc !important;
                font-family: 'Outfit', sans-serif !important;
                border-bottom: 1px solid #1e293b !important;
            }
            .swagger-ui .opblock-tag p {
                color: #64748b !important;
            }
            .swagger-ui .opblock .opblock-summary-path {
                color: #f8fafc !important;
                font-weight: 600 !important;
            }
            .swagger-ui .opblock .opblock-summary-description {
                color: #94a3b8 !important;
            }
            .swagger-ui .opblock.opblock-get {
                background: rgba(14, 165, 233, 0.08) !important;
                border-color: #0ea5e9 !important;
            }
            .swagger-ui .opblock.opblock-get .opblock-summary-method {
                background: #0ea5e9 !important;
                color: #fff !important;
                border-radius: 4px !important;
            }
            .swagger-ui .opblock.opblock-post {
                background: rgba(16, 185, 129, 0.08) !important;
                border-color: #10b981 !important;
            }
            .swagger-ui .opblock.opblock-post .opblock-summary-method {
                background: #10b981 !important;
                color: #fff !important;
                border-radius: 4px !important;
            }
            .swagger-ui .opblock.opblock-put {
                background: rgba(245, 158, 11, 0.08) !important;
                border-color: #f59e0b !important;
            }
            .swagger-ui .opblock.opblock-put .opblock-summary-method {
                background: #f59e0b !important;
                color: #fff !important;
                border-radius: 4px !important;
            }
            .swagger-ui .opblock.opblock-delete {
                background: rgba(239, 68, 68, 0.08) !important;
                border-color: #ef4444 !important;
            }
            .swagger-ui .opblock.opblock-delete .opblock-summary-method {
                background: #ef4444 !important;
                color: #fff !important;
                border-radius: 4px !important;
            }
            .swagger-ui .btn.authorize {
                background-color: #10b981 !important;
                color: #fff !important;
                border-color: #10b981 !important;
                border-radius: 6px !important;
                font-weight: 600 !important;
            }
            .swagger-ui .btn.authorize svg {
                fill: #fff !important;
            }
            .swagger-ui input[type=text], .swagger-ui select, .swagger-ui textarea {
                background: #1e293b !important;
                color: #f8fafc !important;
                border: 1px solid #334155 !important;
                border-radius: 6px !important;
            }
            .swagger-ui .response-col_status, .swagger-ui .response-col_links, .swagger-ui table.headers td, .swagger-ui .parameter__name, .swagger-ui .parameter__type, .swagger-ui .parameter__in {
                color: #f8fafc !important;
            }
            .swagger-ui .opblock-body pre.microlight {
                background: #0b0f19 !important;
                border: 1px solid #1e293b !important;
                border-radius: 8px !important;
            }
            .swagger-ui .model-box {
                background: #1e293b !important;
                border: 1px solid #334155 !important;
                border-radius: 6px !important;
                padding: 10px !important;
            }
            .swagger-ui section.models {
                border: 1px solid #1e293b !important;
                border-radius: 8px !important;
            }
            .swagger-ui section.models h4 {
                color: #f8fafc !important;
                border-bottom: 1px solid #1e293b !important;
            }
            .swagger-ui .model-title {
                color: #f8fafc !important;
            }
            .swagger-ui .prop-type {
                color: #0ea5e9 !important;
            }
            .swagger-ui .prop-format {
                color: #64748b !important;
            }
            .swagger-ui .tabli button {
                color: #cbd5e1 !important;
            }
            .swagger-ui .tabli.active button {
                color: #f8fafc !important;
                font-weight: 600 !important;
            }
        </style>
        """
        html_content = response.body.decode("utf-8")
        modified_html = html_content.replace("</head>", f"{custom_css}</head>")
        return HTMLResponse(content=modified_html, status_code=response.status_code)

    # Single catch-all handler; it dispatches typed exceptions to the right
    # status code and sanitizes anything unexpected into a generic 500 (VULN-014).
    app.add_exception_handler(Exception, http_error_handler)

    @app.get("/health", tags=["health"])
    async def root_health():
        from app.db.session import verify_database_startup
        db_status = "connected"
        try:
            await verify_database_startup()
        except Exception:
            db_status = "failed"
        return {
            "status": "healthy" if db_status == "connected" else "unhealthy",
            "database": db_status,
            # Reported for visibility only — Redis is an optional accelerator, so
            # its state never affects the overall "healthy" verdict.
            "redis": redis_client.status(),
            "environment": settings.environment,
        }

    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    async def startup_event() -> None:
        await verify_database_startup()
        # Ensure the pgvector ANN indexes exist (safety net alongside the
        # Alembic migration). Idempotent and non-fatal.
        await ensure_vector_indexes()
        await _warm_embedding_model()

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        # Release Redis sockets on shutdown. A no-op when Redis was never used.
        await redis_client.close_client()
        # Close the shared LLM HTTP client's connection pool.
        from app.services.llm.mistral_provider import close_shared_client
        await close_shared_client()

    return app


app = create_app()


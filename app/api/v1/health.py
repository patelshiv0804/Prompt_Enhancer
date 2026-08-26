from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from app.db.session import verify_database_startup
from app.api.v1.deps import get_llm_provider, get_embedding_service
from app.services.llm.mistral_provider import MistralProvider
from app.services.embedding_service import EmbeddingService

router = APIRouter()


class HealthStatus(BaseModel):
    status: str = Field(..., description="Overall application status", examples=["ok"])
    database: str = Field(..., description="Database connection health status", examples=["connected"])
    embedding_model: str = Field(..., description="Sentence embedding engine status", examples=["active"])
    llm_provider: str = Field(..., description="Mistral AI connection health status", examples=["healthy"])


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="System Health Check",
    description="Validates PostgreSQL connections, SentenceTransformer loading, and Mistral completions API statuses.",
)
async def health_check(
    llm: MistralProvider = Depends(get_llm_provider),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> HealthStatus:
    # 1. Database Check
    db_status = "connected"
    try:
        await verify_database_startup()
    except Exception:
        db_status = "failed"

    # 2. Embedding Model Check
    emb_status = "active"
    try:
        await emb.generate_for_prompt_async("health check")
    except Exception:
        emb_status = "failed"

    # 3. LLM Check
    llm_status = "healthy"
    try:
        check = await llm.health_check()
        if not check.healthy:
            llm_status = "unhealthy"
    except Exception:
        llm_status = "unhealthy"

    overall_status = "ok" if (db_status == "connected" and emb_status == "active" and llm_status == "healthy") else "degraded"

    return HealthStatus(
        status=overall_status,
        database=db_status,
        embedding_model=emb_status,
        llm_provider=llm_status,
    )


@router.get(
    "/health/liveness",
    summary="Liveness Probe",
    description="Indicates whether the application container is running. Always returns 200 OK.",
)
async def liveness() -> dict[str, str]:
    return {"status": "healthy"}


@router.get(
    "/health/readiness",
    summary="Readiness Probe",
    description="Validates PostgreSQL database connectivity and model status, returning 503 if any service is down.",
)
async def readiness(
    llm: MistralProvider = Depends(get_llm_provider),
    emb: EmbeddingService = Depends(get_embedding_service),
) -> Response:
    # 1. Database Check
    db_ok = True
    try:
        await verify_database_startup()
    except Exception:
        db_ok = False

    # 2. Embedding Model Check
    emb_ok = True
    try:
        await emb.generate_for_prompt_async("health check")
    except Exception:
        emb_ok = False

    # 3. LLM Check
    llm_ok = True
    try:
        check = await llm.health_check()
        if not check.healthy:
            llm_ok = False
    except Exception:
        llm_ok = False

    is_ready = db_ok and emb_ok and llm_ok
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return Response(
        content=f'{{"status": "{"healthy" if is_ready else "unhealthy"}", "database": "{"connected" if db_ok else "failed"}", "embedding_model": "{"active" if emb_ok else "failed"}", "llm_provider": "{"healthy" if llm_ok else "unhealthy"}"}}',
        media_type="application/json",
        status_code=status_code,
    )


@router.get(
    "/health/startup",
    summary="Startup Probe",
    description="Verifies that all dependency models and database connectivity checkouts are finished.",
)
async def startup_check(
    emb: EmbeddingService = Depends(get_embedding_service),
) -> Response:
    db_ok = True
    try:
        await verify_database_startup()
    except Exception:
        db_ok = False
        
    emb_ok = True
    try:
        # Check if the SentenceTransformer model resides in memory
        if not hasattr(emb, "model") or emb.model is None:
            emb_ok = False
    except Exception:
        emb_ok = False
        
    is_ready = db_ok and emb_ok
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return Response(
        content=f'{{"status": "{"healthy" if is_ready else "starting"}", "database": "{"connected" if db_ok else "failed"}", "embedding_model": "{"active" if emb_ok else "loading"}"}}',
        media_type="application/json",
        status_code=status_code,
    )

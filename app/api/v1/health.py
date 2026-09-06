from fastapi import APIRouter, Depends
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
    llm_provider: str = Field(..., description="OpenAI-compatible LLM connection health status", examples=["healthy"])


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="System Health Check",
    description="Validates PostgreSQL connections, SentenceTransformer loading, and OpenAI-compatible LLM API statuses.",
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

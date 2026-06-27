from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db.session import verify_database_startup

router = APIRouter()


class HealthStatus(BaseModel):
    status: str = Field(..., description="Overall application health status status", examples=["ok"])
    pgvector: bool = Field(..., description="Database pgvector extension availability", examples=[True])


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="System Health Check",
    description="Checks the backend status, verifies database connectivity, and ensures the pgvector extension is active.",
)
async def health_check() -> HealthStatus:
    await verify_database_startup()
    return HealthStatus(status="ok", pgvector=True)


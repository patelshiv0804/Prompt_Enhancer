from typing import Optional

from fastapi import APIRouter, Depends

from app.api.v1.deps import get_session
from app.repositories.ai_model import AIModelRepository
from app.schemas.ai_model import AIModelSummary
from app.schemas.common import PaginatedResponse
from app.services.ai_model_service import AIModelService

router = APIRouter(prefix="/ai-models", tags=["ai_models"])

ai_model_service = AIModelService(AIModelRepository())


@router.get(
    "/",
    response_model=PaginatedResponse[AIModelSummary],
    summary="List AI Models",
    description="Retrieves a paginated list of all registered AI models in the system. Can filter to return active models only.",
    responses={
        500: {"description": "Internal server error occurred while retrieving AI models."},
    },
)
async def list_ai_models(
    session=Depends(get_session),
    only_active: Optional[bool] = False,
    limit: int = 20,
    offset: int = 0,
) -> PaginatedResponse[AIModelSummary]:
    models = await ai_model_service.list_models(session, only_active=only_active, limit=limit, offset=offset)
    return PaginatedResponse(
        message="AI model list retrieved.",
        data=[AIModelSummary(**model.model_dump()) for model in models],
        page=(offset // limit) + 1,
        page_size=limit,
        total=len(models),
    )


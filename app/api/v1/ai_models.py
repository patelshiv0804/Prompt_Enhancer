from typing import Optional

from fastapi import APIRouter, Depends

from app.api.v1.deps import get_session
from app.api.v1.exceptions import map_service_error
from app.repositories.ai_model import AIModelRepository
from app.schemas.ai_model import AIModelCreate, AIModelRead, AIModelSummary, AIModelUpdate
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.services.ai_model_service import AIModelService

router = APIRouter(prefix="/ai-models", tags=["ai_models"])

ai_model_service = AIModelService(AIModelRepository())


@router.post(
    "/",
    response_model=APIResponse[AIModelRead],
    summary="Create AI Model",
    description="Registers a new AI Model configuration in the system. The provider and model_name combination must be unique.",
    responses={
        400: {"model": ErrorResponse, "description": "AI model details are invalid or provider/model name duplicate already exists."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while creating the AI model."},
    },
)
async def create_ai_model(payload: AIModelCreate, session=Depends(get_session)) -> APIResponse[AIModelRead]:
    try:
        model = await ai_model_service.create_model(session, payload)
        return APIResponse(message="AI model created.", data=AIModelRead(**model.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/",
    response_model=PaginatedResponse[AIModelSummary],
    summary="List AI Models",
    description="Retrieves a paginated list of all registered AI models in the system. Can filter to return active models only.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving AI models."},
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


@router.get(
    "/{model_id}",
    response_model=APIResponse[AIModelRead],
    summary="Get AI Model Details",
    description="Fetches detailed configuration fields of a registered AI Model using its unique UUID identifier.",
    responses={
        404: {"model": ErrorResponse, "description": "The AI model with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving the AI model details."},
    },
)
async def get_ai_model(model_id: str, session=Depends(get_session)) -> APIResponse[AIModelRead]:
    try:
        model = await ai_model_service.get_model(session, model_id)
        return APIResponse(message="AI model retrieved.", data=AIModelRead(**model.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.put(
    "/{model_id}",
    response_model=APIResponse[AIModelRead],
    summary="Update AI Model",
    description="Updates one or more fields on an existing AI Model configuration using its UUID.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error on the updated fields."},
        404: {"model": ErrorResponse, "description": "The AI model with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while updating the AI model."},
    },
)
async def update_ai_model(model_id: str, payload: AIModelUpdate, session=Depends(get_session)) -> APIResponse[AIModelRead]:
    try:
        model = await ai_model_service.update_model(session, model_id, payload.model_dump(exclude_none=True))
        return APIResponse(message="AI model updated.", data=AIModelRead(**model.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


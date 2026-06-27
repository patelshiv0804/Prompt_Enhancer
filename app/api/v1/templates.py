from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_session
from app.api.v1.exceptions import map_service_error
from app.repositories.template import TemplateRepository
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.schemas.template import TemplateCreate, TemplateRead, TemplateSummary, TemplateUpdate
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])

template_service = TemplateService(TemplateRepository())


@router.post(
    "/",
    response_model=APIResponse[TemplateRead],
    summary="Create Template",
    description="Registers a new prompt enhancement template. Templates define structural rules applied during optimization.",
    responses={
        400: {"model": ErrorResponse, "description": "Template details are invalid."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while creating the template."},
    },
)
async def create_template(payload: TemplateCreate, session=Depends(get_session)) -> APIResponse[TemplateRead]:
    try:
        template = await template_service.create_template(session, payload)
        return APIResponse(message="Template created.", data=TemplateRead(**template.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/",
    response_model=PaginatedResponse[TemplateSummary],
    summary="List Templates",
    description="Retrieves a paginated list of templates. Supports filtering by mode, category, target AI Model, approval status, and active models.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving templates."},
    },
)
async def list_templates(
    session=Depends(get_session),
    mode: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    ai_model_id: Optional[str] = Query(default=None),
    is_approved: Optional[bool] = Query(default=None),
    only_active_models: Optional[bool] = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[TemplateSummary]:
    templates = await template_service.list_templates(
        session=session,
        mode=mode,
        category=category,
        ai_model_id=ai_model_id,
        is_approved=is_approved,
        only_active_models=only_active_models,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        message="Template list retrieved.",
        data=[TemplateSummary(**template.model_dump()) for template in templates],
        page=(offset // limit) + 1,
        page_size=limit,
        total=len(templates),
    )


@router.get(
    "/{template_id}",
    response_model=APIResponse[TemplateRead],
    summary="Get Template Details",
    description="Retrieves the detailed configuration of a specific prompt template using its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "The template with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving the template details."},
    },
)
async def get_template(template_id: str, session=Depends(get_session)) -> APIResponse[TemplateRead]:
    try:
        template = await template_service.get_template(session, template_id)
        return APIResponse(message="Template retrieved.", data=TemplateRead(**template.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.put(
    "/{template_id}",
    response_model=APIResponse[TemplateRead],
    summary="Update Template",
    description="Updates fields on an existing template configuration (e.g. title, category, mode, body, tags, is_approved).",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error on the updated fields."},
        404: {"model": ErrorResponse, "description": "The template with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while updating the template."},
    },
)
async def update_template(
    template_id: str,
    payload: TemplateUpdate,
    session=Depends(get_session),
) -> APIResponse[TemplateRead]:
    try:
        template = await template_service.update_template(session, template_id, payload.model_dump(exclude_none=True))
        return APIResponse(message="Template updated.", data=TemplateRead(**template.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.delete(
    "/{template_id}",
    response_model=APIResponse[None],
    summary="Delete Template",
    description="Deletes a prompt template from the database using its unique UUID identifier.",
    responses={
        404: {"model": ErrorResponse, "description": "The template with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while deleting the template."},
    },
)
async def delete_template(template_id: str, session=Depends(get_session)) -> APIResponse[None]:
    try:
        await template_service.delete_template(session, template_id)
        return APIResponse(message="Template deleted.", data=None)
    except Exception as exc:
        raise map_service_error(exc)


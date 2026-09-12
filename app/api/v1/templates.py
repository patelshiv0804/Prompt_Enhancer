from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session, get_template_service
from app.core.security import get_current_user_id, get_optional_current_user_id
from app.schemas.common import PaginatedResponse
from app.schemas.template import (
    TemplateCreate,
    TemplateListItem,
    TemplateResponse,
    TemplateUpdate,
)
from app.services.exceptions import TemplateNotFoundError
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get(
    "/",
    response_model=PaginatedResponse[TemplateListItem],
    summary="List Templates",
    description="Retrieves a paginated list of templates. Supports filtering by mode, category, target AI Model, approval status, and active models. Authenticated users see public templates and their own custom templates. Pass mine=true to view only your custom templates.",
    responses={
        401: {"description": "Authentication required when filtering by mine=true."},
        500: {"description": "Internal server error occurred while retrieving templates."},
    },
)
async def list_templates(
    session: AsyncSession = Depends(get_session),
    current_user_id: Optional[UUID] = Depends(get_optional_current_user_id),
    template_service: TemplateService = Depends(get_template_service),
    mode: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    ai_model_id: Optional[str] = Query(default=None),
    is_approved: Optional[bool] = Query(default=None),
    is_featured: Optional[bool] = Query(default=None),
    only_active_models: Optional[bool] = Query(default=False),
    mine: Optional[bool] = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[TemplateListItem]:
    if mine and not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view your custom templates.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    templates = await template_service.list_templates(
        session=session,
        mode=mode,
        category=category,
        role=role,
        ai_model_id=ai_model_id,
        is_approved=is_approved,
        is_featured=is_featured,
        only_active_models=only_active_models,
        user_id=current_user_id,
        mine=bool(mine),
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(
        message="Template list retrieved.",
        data=[TemplateListItem(**template.model_dump()) for template in templates],
        page=(offset // limit) + 1,
        page_size=limit,
        total=len(templates),
    )


@router.post(
    "/",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Template",
    description="Creates a new custom template for the authenticated user. Automatically generates vector embedding and enables immediate usage.",
    responses={
        401: {"description": "Authentication required to create custom templates."},
        422: {"description": "Validation error in template payload."},
    },
)
async def create_template(
    payload: TemplateCreate,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    template_service: TemplateService = Depends(get_template_service),
) -> TemplateResponse:
    template = await template_service.create_template(
        session=session,
        template_data=payload,
        user_id=user_id,
    )
    return TemplateResponse(**template.model_dump())


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Get Template Details",
    description="Retrieves a specific template. For custom templates owned by the caller, the prompt body (recipe) is included.",
    responses={
        404: {"description": "Template not found."},
    },
)
async def get_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: Optional[UUID] = Depends(get_optional_current_user_id),
    template_service: TemplateService = Depends(get_template_service),
) -> TemplateResponse:
    try:
        template = await template_service.get_template_for_user(
            session=session,
            template_id=template_id,
            user_id=user_id,
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found.",
        )

    data = template.model_dump()
    # If this is not the caller's custom template, protect the proprietary body recipe
    if template.user_id is None or (user_id and template.user_id != user_id):
        data["body"] = None

    return TemplateResponse(**data)


@router.patch(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Update Custom Template",
    description="Updates a custom template owned by the authenticated user. Re-computes vector embeddings if metadata changed.",
    responses={
        401: {"description": "Authentication required."},
        404: {"description": "Template not found or not owned by user."},
    },
)
async def update_template(
    template_id: UUID,
    payload: TemplateUpdate,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    template_service: TemplateService = Depends(get_template_service),
) -> TemplateResponse:
    update_values = payload.model_dump(exclude_unset=True)
    try:
        updated = await template_service.update_template_for_user(
            session=session,
            template_id=template_id,
            user_id=user_id,
            values=update_values,
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found.",
        )

    return TemplateResponse(**updated.model_dump())


@router.delete(
    "/{template_id}",
    summary="Delete Custom Template",
    description="Deletes a custom template owned by the authenticated user.",
    responses={
        401: {"description": "Authentication required."},
        404: {"description": "Template not found or not owned by user."},
    },
)
async def delete_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    template_service: TemplateService = Depends(get_template_service),
) -> dict[str, Any]:
    try:
        await template_service.delete_template_for_user(
            session=session,
            template_id=template_id,
            user_id=user_id,
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found.",
        )

    return {"message": "Template deleted successfully.", "id": str(template_id)}

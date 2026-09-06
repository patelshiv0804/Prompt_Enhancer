from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_session
from app.repositories.template import TemplateRepository
from app.schemas.common import PaginatedResponse
from app.schemas.template import TemplateListItem
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])

template_service = TemplateService(TemplateRepository())


@router.get(
    "/",
    response_model=PaginatedResponse[TemplateListItem],
    summary="List Templates",
    description="Retrieves a paginated list of templates. Supports filtering by mode, category, target AI Model, approval status, and active models. The prompt body is intentionally omitted from list results.",
    responses={
        500: {"description": "Internal server error occurred while retrieving templates."},
    },
)
async def list_templates(
    session=Depends(get_session),
    mode: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    ai_model_id: Optional[str] = Query(default=None),
    is_approved: Optional[bool] = Query(default=None),
    is_featured: Optional[bool] = Query(default=None),
    only_active_models: Optional[bool] = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[TemplateListItem]:
    templates = await template_service.list_templates(
        session=session,
        mode=mode,
        category=category,
        role=role,
        ai_model_id=ai_model_id,
        is_approved=is_approved,
        is_featured=is_featured,
        only_active_models=only_active_models,
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

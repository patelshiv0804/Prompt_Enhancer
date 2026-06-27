from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.deps import get_current_user, get_session
from app.api.v1.exceptions import map_service_error
from app.repositories.prompt import PromptRepository
from app.repositories.profile import ProfileRepository
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.schemas.prompt import (
    AIModelSummary,
    PromptCreate,
    PromptDetailResponse,
    PromptRead,
    PromptSummary,
    PromptUpdate,
    PromptVersionSummary,
    TemplateSummary,
)
from app.services.prompt_service import PromptService

router = APIRouter(prefix="/prompts", tags=["prompts"])

prompt_service = PromptService(PromptRepository())
profile_repository = ProfileRepository()


@router.post(
    "/",
    response_model=APIResponse[PromptRead],
    summary="Create Prompt",
    description="Registers a new prompt entry in the platform. Requires standard mock user authentication via header `X-Current-User`.",
    responses={
        400: {"model": ErrorResponse, "description": "The prompt configuration is invalid."},
        401: {"model": ErrorResponse, "description": "Authentication required. Send header X-Current-User."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while creating the prompt."},
    },
)
async def create_prompt(
    payload: PromptCreate,
    session=Depends(get_session),
    current_user: Optional[str] = Depends(get_current_user),
) -> APIResponse[PromptRead]:
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        profile = await profile_repository.get_by_email(session, current_user)
        if not profile:
            raise HTTPException(status_code=404, detail="Authenticated profile not found.")
        prompt = await prompt_service.create_prompt(session, str(profile.id), payload)
        return APIResponse(message="Prompt created.", data=PromptRead(**prompt.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/",
    response_model=PaginatedResponse[PromptSummary],
    summary="List Prompts",
    description="Retrieves a paginated list of prompts. Supports filtering by user, template, or AI Model.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error occurred while listing prompts."},
    },
)
async def list_prompts(
    session=Depends(get_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = Query(default=None),
    template_id: Optional[str] = Query(default=None),
    ai_model_id: Optional[str] = Query(default=None),
) -> PaginatedResponse[PromptSummary]:
    prompts = await prompt_service.list_prompts(
        session=session,
        limit=limit,
        offset=offset,
        user_id=user_id,
        template_id=template_id,
        ai_model_id=ai_model_id,
    )
    return PaginatedResponse(
        message="Prompt list retrieved.",
        data=[PromptSummary(**prompt.model_dump()) for prompt in prompts],
        page=(offset // limit) + 1,
        page_size=limit,
        total=len(prompts),
    )


@router.get(
    "/{prompt_id}",
    response_model=APIResponse[PromptDetailResponse],
    summary="Get Prompt Details",
    description="Retrieves complete details of a prompt, including related template configuration, target AI model metadata, version count, and active version content.",
    responses={
        404: {"model": ErrorResponse, "description": "The prompt with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving the prompt details."},
    },
)
async def get_prompt(prompt_id: str, session=Depends(get_session)) -> APIResponse[PromptDetailResponse]:
    try:
        prompt = await prompt_service.get_prompt(
            session,
            prompt_id,
            include_template=True,
            include_ai_model=True,
            include_versions=True,
        )
        detail = PromptDetailResponse(
            id=prompt.id,
            title=prompt.title,
            original_prompt=prompt.original_prompt,
            template=TemplateSummary(**prompt.template.model_dump()) if prompt.template else None,
            ai_model=AIModelSummary(**prompt.ai_model.model_dump()) if prompt.ai_model else None,
            current_version=PromptVersionSummary(**prompt.current_version.model_dump()) if prompt.current_version else None,
            version_count=len(prompt.versions) if prompt.versions else 0,
            total_score=prompt.total_score,
            grade=prompt.grade,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
        return APIResponse(message="Prompt retrieved.", data=detail)
    except Exception as exc:
        raise map_service_error(exc)


@router.put(
    "/{prompt_id}",
    response_model=APIResponse[PromptRead],
    summary="Update Prompt",
    description="Updates the title, grade, total score, active version, or configuration link for an existing prompt.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error on the updated fields."},
        404: {"model": ErrorResponse, "description": "The prompt with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while updating the prompt."},
    },
)
async def update_prompt(prompt_id: str, payload: PromptUpdate, session=Depends(get_session)) -> APIResponse[PromptRead]:
    try:
        prompt = await prompt_service.update_prompt(session, prompt_id, payload.model_dump(exclude_none=True))
        return APIResponse(message="Prompt updated.", data=PromptRead(**prompt.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.delete(
    "/{prompt_id}",
    response_model=APIResponse[None],
    summary="Delete Prompt",
    description="Permanently deletes a prompt and all associated version history from the database using its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "The prompt with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while deleting the prompt."},
    },
)
async def delete_prompt(prompt_id: str, session=Depends(get_session)) -> APIResponse[None]:
    try:
        await prompt_service.delete_prompt(session, prompt_id)
        return APIResponse(message="Prompt deleted.", data=None)
    except Exception as exc:
        raise map_service_error(exc)


from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.deps import get_session
from app.api.v1.exceptions import map_service_error
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.schemas.prompt_version import (
    PromptVersionCreate,
    PromptVersionRead,
    PromptVersionRestoreRequest,
    PromptVersionSummary,
)
from app.services.embedding_service import EmbeddingService
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.services.prompt_restore_service import PromptRestoreService
from app.services.prompt_version_service import PromptVersionService

router = APIRouter(prefix="/prompt-versions", tags=["prompt_versions"])

prompt_repository = PromptRepository()
prompt_version_repository = PromptVersionRepository()

prompt_version_service = PromptVersionService(
    prompt_repository=prompt_repository,
    prompt_version_repository=prompt_version_repository,
)

prompt_embedding_service = PromptEmbeddingService(
    prompt_repository=prompt_repository,
    prompt_version_repository=prompt_version_repository,
    embedding_service=EmbeddingService(),
)

prompt_restore_service = PromptRestoreService(
    prompt_repository=prompt_repository,
    prompt_version_repository=prompt_version_repository,
    prompt_embedding_service=prompt_embedding_service,
)


@router.post(
    "/",
    response_model=APIResponse[PromptVersionRead],
    summary="Create Prompt Version",
    description="Appends a new version to an existing prompt. The new version is automatically marked as the active version.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error on the version properties."},
        404: {"model": ErrorResponse, "description": "The prompt with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while creating the version."},
    },
)
async def create_prompt_version(
    payload: PromptVersionCreate,
    prompt_id: str = Query(...),
    session=Depends(get_session),
) -> APIResponse[PromptVersionRead]:
    try:
        version = await prompt_version_service.create_version_for_prompt(
            session=session,
            prompt_id=prompt_id,
            content=payload.content,
            version_type=payload.version_type or "draft",
        )
        return APIResponse(message="Prompt version created.", data=PromptVersionRead(**version.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/",
    response_model=PaginatedResponse[PromptVersionSummary],
    summary="List Prompt Versions",
    description="Retrieves a paginated history list of prompt versions. Can filter by a specific `prompt_id`.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving versions."},
    },
)
async def list_prompt_versions(
    session=Depends(get_session),
    prompt_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[PromptVersionSummary]:
    try:
        versions = await prompt_version_service.list_versions(session, prompt_id=prompt_id, limit=limit, offset=offset)
        return PaginatedResponse(
            message="Prompt versions retrieved.",
            data=[PromptVersionSummary(**version.model_dump()) for version in versions],
            page=(offset // limit) + 1,
            page_size=limit,
            total=len(versions),
        )
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/{version_id}",
    response_model=APIResponse[PromptVersionRead],
    summary="Get Prompt Version Details",
    description="Retrieves detailed content and type for a specific prompt version using its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "The prompt version with the specified UUID was not found."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while retrieving the version details."},
    },
)
async def get_prompt_version(version_id: str, session=Depends(get_session)) -> APIResponse[PromptVersionRead]:
    try:
        version = await prompt_version_service.get_version(session, version_id)
        return APIResponse(message="Prompt version retrieved.", data=PromptVersionRead(**version.model_dump()))
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/{prompt_id}/restore",
    response_model=APIResponse[None],
    summary="Restore Prompt Version",
    description="Restores a historical version of a prompt as the active one. Recalculates prompt embeddings using the restored content.",
    responses={
        404: {"model": ErrorResponse, "description": "The prompt or version UUID was not found."},
        409: {"model": ErrorResponse, "description": "Conflict: Cannot restore a version that is already the active version."},
        500: {"model": ErrorResponse, "description": "Internal server error occurred while restoring the version."},
    },
)
async def restore_prompt_version(
    prompt_id: str,
    payload: PromptVersionRestoreRequest,
    session=Depends(get_session),
) -> APIResponse[None]:
    try:
        await prompt_restore_service.restore_version(session=session, prompt_id=prompt_id, version_id=str(payload.version_id))
        return APIResponse(message="Prompt version restored.", data=None)
    except Exception as exc:
        raise map_service_error(exc)


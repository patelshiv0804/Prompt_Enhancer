from __future__ import annotations

import logging
from typing import Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel, Field
from datetime import datetime

from app.api.v1.deps import (
    get_session,
    get_current_user,
    get_prompt_service,
    get_prompt_history_service,
    get_prompt_version_service,
    get_profile_repository,
    get_prompt_similarity_service,
    get_duplicate_detection_service,
    get_prompt_recommendation_service,
    get_prompt_search_service,
    get_prompt_regeneration_service,
    get_tool_recommendation_service,
)
from app.services.tool_recommendation_service import ToolRecommendationService
from app.api.v1.exceptions import map_service_error
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.schemas.prompt import (
    PromptDetailResponse,
    PromptRead,
    PromptSummary,
    AIModelSummary,
    TemplateSummary,
    RegeneratePromptRequest,
    RegeneratePromptResponse,
)
from app.schemas.prompt_version import PromptVersionSummary
from app.services.prompt_service import PromptService
from app.services.prompt_regeneration_service import PromptRegenerationService
from app.services.prompt_history_service import PromptHistoryService
from app.services.prompt_version_service import PromptVersionService
from app.services.prompt_similarity_service import PromptSimilarityService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.prompt_recommendation_service import PromptRecommendationService
from app.services.prompt_search_service import PromptSearchService

logger = logging.getLogger("promptiq.api.prompts")
router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get(
    "/",
    response_model=PaginatedResponse[PromptSummary],
    summary="List Prompts",
    description="Retrieves a paginated list of prompts. Excludes soft-deleted records when enabled and supports sorting.",
)
async def list_prompts(
    session: AsyncSession = Depends(get_session),
    current_user: Optional[str] = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Optional[str] = Query(default="created_at"),
    sort_order: Optional[str] = Query(default="desc"),
    user_id: Optional[str] = Query(default=None),
    template_id: Optional[str] = Query(default=None),
    ai_model_id: Optional[str] = Query(default=None),
    prompt_service: PromptService = Depends(get_prompt_service),
    profile_repo=Depends(get_profile_repository),
) -> PaginatedResponse[PromptSummary]:
    try:
        limit = page_size
        offset = (page - 1) * page_size

        target_user_id = user_id
        if not target_user_id and current_user:
            profile = await profile_repo.get_by_email(session, current_user)
            if profile:
                target_user_id = str(profile.id)

        prompts = await prompt_service.list_prompts(
            session=session,
            limit=limit,
            offset=offset,
            user_id=target_user_id,
            template_id=template_id,
            ai_model_id=ai_model_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return PaginatedResponse(
            message="Prompt list retrieved.",
            data=[PromptSummary(**prompt.model_dump()) for prompt in prompts],
            page=page,
            page_size=page_size,
            total=len(prompts),
        )
    except Exception as exc:
        raise map_service_error(exc)


# Pydantic Schemas for Prompt Intelligence Endpoints
class PromptSearchRequest(BaseModel):
    prompt: str = Field(..., description="The query prompt for semantic lookup.")
    limit: Optional[int] = Field(default=None, description="Max results to return.")
    role: Optional[str] = Field(default=None, description="Filter by prompt template role.")
    mode: Optional[str] = Field(default=None, description="Filter by prompt template mode.")
    template_id: Optional[UUID] = Field(default=None, description="Filter by template UUID.")
    user_id: Optional[str] = Field(default=None, description="Filter by user email/profile ID.")
    date_from: Optional[datetime] = Field(default=None, description="Filter prompts created after this timestamp.")
    date_to: Optional[datetime] = Field(default=None, description="Filter prompts created before this timestamp.")

class PromptSearchMatch(BaseModel):
    prompt_id: UUID
    title: str
    original_prompt: str
    similarity_score: float
    total_score: Optional[float] = None
    grade: Optional[str] = None
    created_at: datetime

class PromptSearchResponse(BaseModel):
    success: bool = True
    message: str = "Semantic search complete."
    results: list[PromptSearchMatch]

class DuplicateCheckRequest(BaseModel):
    prompt: str = Field(..., description="Prompt text to analyze for duplicates.")
    threshold: Optional[float] = Field(default=None, description="Configurable similarity threshold override.")

class DuplicatePromptDetail(BaseModel):
    id: UUID
    original_prompt: str
    title: str

class DuplicateCheckResponse(BaseModel):
    success: bool = True
    message: str
    is_duplicate: bool
    similarity: Optional[float] = None
    duplicate_prompt: Optional[DuplicatePromptDetail] = None

class RecommendedPromptDetail(BaseModel):
    prompt_id: UUID
    title: str
    original_prompt: str
    similarity_score: float
    version_count: int
    recommendation_score: float
    created_at: datetime

class PromptRecommendationsResponse(BaseModel):
    success: bool = True
    message: str = "Recommendations generated."
    results: list[RecommendedPromptDetail]


@router.post(
    "/search",
    response_model=PromptSearchResponse,
    summary="Semantic Search Prompts",
    description="Find user prompts semantically similar to a query prompt using pgvector cosine similarity, with support for advanced metadata filters.",
)
async def semantic_search(
    payload: PromptSearchRequest,
    session: AsyncSession = Depends(get_session),
    search_service: PromptSearchService = Depends(get_prompt_search_service),
) -> PromptSearchResponse:
    try:
        t_id = str(payload.template_id) if payload.template_id else None
        res = await search_service.search(
            session=session,
            prompt_text=payload.prompt,
            limit=payload.limit,
            role=payload.role,
            mode=payload.mode,
            template_id=t_id,
            user_id=payload.user_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
        return PromptSearchResponse(
            results=[PromptSearchMatch(**r) for r in res]
        )
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/duplicates",
    response_model=DuplicateCheckResponse,
    summary="Detect Duplicate Prompts",
    description="Detects whether a nearly identical user prompt already exists using a similarity threshold.",
)
async def detect_duplicates(
    payload: DuplicateCheckRequest,
    session: AsyncSession = Depends(get_session),
    dup_service: DuplicateDetectionService = Depends(get_duplicate_detection_service),
) -> DuplicateCheckResponse:
    try:
        res = await dup_service.detect_duplicate(
            session=session,
            prompt_text=payload.prompt,
            threshold=payload.threshold,
        )
        dup_prompt = None
        if res["duplicate_prompt"]:
            dup_prompt = DuplicatePromptDetail(
                id=UUID(res["duplicate_prompt"]["id"]),
                original_prompt=res["duplicate_prompt"]["original_prompt"],
                title=res["duplicate_prompt"]["title"],
            )
        
        msg = "Possible duplicate detected." if res["is_duplicate"] else "No duplicates detected."
        return DuplicateCheckResponse(
            message=msg,
            is_duplicate=res["is_duplicate"],
            similarity=res["similarity"],
            duplicate_prompt=dup_prompt,
        )
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/recommendations",
    response_model=PromptRecommendationsResponse,
    summary="Get Recommended Prompts",
    description="Generates a list of recommended previous prompts based on hybrid scoring (similarity, reuse frequency, and recency).",
)
async def get_recommendations(
    prompt: str = Query(..., description="Reference prompt text to base recommendations on."),
    limit: Optional[int] = Query(default=None, description="Max recommendations to return."),
    session: AsyncSession = Depends(get_session),
    rec_service: PromptRecommendationService = Depends(get_prompt_recommendation_service),
) -> PromptRecommendationsResponse:
    try:
        res = await rec_service.recommend_prompts(
            session=session,
            prompt_text=prompt,
            limit=limit,
        )
        return PromptRecommendationsResponse(
            results=[RecommendedPromptDetail(**r) for r in res]
        )
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/{prompt_id}",
    response_model=APIResponse[PromptDetailResponse],
    summary="Get Prompt Details",
    description="Retrieves prompt details, active version content, and dynamic score evaluation summaries.",
)
async def get_prompt(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
    prompt_service: PromptService = Depends(get_prompt_service),
    tool_recommendation_service: ToolRecommendationService = Depends(get_tool_recommendation_service),
) -> APIResponse[PromptDetailResponse]:
    try:
        prompt = await prompt_service.get_prompt(
            session,
            prompt_id,
            include_template=True,
            include_ai_model=True,
            include_versions=True,
        )
        
        # Build normalized analysis summary for display
        analysis_data = None
        if prompt.total_score is not None:
            analysis_data = {
                "overall_score": int(prompt.total_score * 10),
                "grade": prompt.grade,
            }

        tool_rec_summary = None
        try:
            tool_rec = await tool_recommendation_service.recommend(
                prompt=prompt.original_prompt,
                mode=prompt.title,
            )
            tool_rec_summary = {
                "matched_task": tool_rec["matched_task"],
                "match_type": tool_rec["match_type"],
                "match_confidence": tool_rec["match_confidence"],
                "tools": tool_rec["tools"],
            }
        except Exception as exc:
            logger.warning(f"Could not calculate tool recommendations for prompt {prompt_id}: {exc}")

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
            analysis=analysis_data,
            tool_recommendations=tool_rec_summary,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
        return APIResponse(message="Prompt retrieved.", data=detail)
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/{prompt_id}/versions",
    response_model=PaginatedResponse[PromptVersionSummary],
    summary="Get Prompt Version History",
    description="Retrieves the complete sequential list of historical enhanced versions for the specified prompt.",
)
async def get_prompt_version_history(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
    history_service: PromptHistoryService = Depends(get_prompt_history_service),
) -> PaginatedResponse[PromptVersionSummary]:
    try:
        versions = await history_service.get_history(session, prompt_id)
        return PaginatedResponse(
            message="Prompt version history retrieved.",
            data=[PromptVersionSummary(**v.model_dump()) for v in versions],
            page=1,
            page_size=len(versions),
            total=len(versions),
        )
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/{prompt_id}/restore/{version}",
    response_model=APIResponse[None],
    summary="Restore Prompt Version",
    description="Reverts the prompt's active version reference to a previous state, identified by version UUID or integer sequence number.",
)
async def restore_prompt_version(
    prompt_id: str,
    version: str,
    session: AsyncSession = Depends(get_session),
    version_service: PromptVersionService = Depends(get_prompt_version_service),
    history_service: PromptHistoryService = Depends(get_prompt_history_service),
) -> APIResponse[None]:
    try:
        import uuid
        version_id = None
        try:
            # Check if it is a valid UUID
            uuid.UUID(version)
            version_id = version
        except ValueError:
            # Not a UUID, check if integer version number
            try:
                v_num = int(version)
                ver_record = await history_service.get_specific_version(session, prompt_id, v_num)
                version_id = str(ver_record.id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Version parameter must be a UUID or integer sequence number.")

        await version_service.restore_version(session, prompt_id, version_id)
        await session.commit()
        return APIResponse(message="Prompt version restored successfully.", data=None)
    except Exception as exc:
        raise map_service_error(exc)


@router.delete(
    "/{prompt_id}",
    response_model=APIResponse[None],
    summary="Delete Prompt",
    description="Deletes a prompt. Applies a soft delete (timestamp update) if enabled by configuration.",
)
async def delete_prompt(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> APIResponse[None]:
    try:
        await prompt_service.delete_prompt(session, prompt_id)
        await session.commit()
        return APIResponse(message="Prompt deleted successfully.", data=None)
    except Exception as exc:
        raise map_service_error(exc)


@router.get(
    "/similar/{prompt_id}",
    response_model=PromptSearchResponse,
    summary="Get Similar Prompts",
    description="Finds prompts semantically similar to an existing prompt in the database, excluding the prompt itself.",
)
async def get_similar_to_prompt(
    prompt_id: str,
    limit: Optional[int] = Query(default=None, description="Max results to return."),
    session: AsyncSession = Depends(get_session),
    prompt_service: PromptService = Depends(get_prompt_service),
    similarity_service: PromptSimilarityService = Depends(get_prompt_similarity_service),
) -> PromptSearchResponse:
    try:
        # Load existing prompt to get its original_prompt or active version content
        prompt = await prompt_service.get_prompt(
            session,
            prompt_id,
            include_versions=True,
        )
        # Use active version content if available, fallback to original_prompt
        query_text = prompt.current_version.content if (prompt.current_version and prompt.current_version.content) else prompt.original_prompt
        
        # Increase search limit by 1 since we'll filter out the query prompt itself
        search_limit = (limit or 10) + 1
        res = await similarity_service.search_similar_prompts(
            session=session,
            prompt_text=query_text,
            limit=search_limit,
        )
        
        # Filter out the query prompt itself
        filtered_results = [r for r in res if r["prompt_id"] != prompt_id]
        # Slice to the requested limit
        filtered_results = filtered_results[:(limit or 10)]
        
        return PromptSearchResponse(
            message=f"Found {len(filtered_results)} similar prompts.",
            results=[PromptSearchMatch(**r) for r in filtered_results]
        )
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/{prompt_id}/regenerate",
    response_model=RegeneratePromptResponse,
    summary="Regenerate Prompt Version",
    description="Generates a new enhanced version of an existing prompt using its original text and template.",
)
async def regenerate_prompt(
    prompt_id: str,
    payload: Optional[RegeneratePromptRequest] = None,
    session: AsyncSession = Depends(get_session),
    regeneration_service: PromptRegenerationService = Depends(get_prompt_regeneration_service),
) -> RegeneratePromptResponse:
    try:
        feedback = payload.feedback if payload else None
        result = await regeneration_service.regenerate_prompt(
            session=session,
            prompt_id=prompt_id,
            feedback=feedback,
        )
        return RegeneratePromptResponse(**result)
    except Exception as exc:
        raise map_service_error(exc)

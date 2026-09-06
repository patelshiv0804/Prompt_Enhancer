from __future__ import annotations

import json
import logging
from typing import Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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
    get_prompt_search_service,
    get_prompt_reenhance_service,
    get_tool_recommendation_service,
)
from app.services.tool_recommendation_service import ToolRecommendationService
from app.api.v1.exceptions import map_service_error
from app.core.security import get_current_user_id
from app.services.exceptions import PromptNotFoundError, PromptVersionException, DatabaseTransactionException
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse
from app.schemas.prompt import (
    PromptDetailResponse,
    PromptRead,
    PromptSummary,
    AIModelSummary,
    TemplateSummary,
)
from app.schemas.prompt_version import PromptVersionSummary, ReenhanceVersionResponse
from app.services.prompt_service import PromptService
from app.services.prompt_reenhance_service import PromptReenhanceService
from app.services.prompt_history_service import PromptHistoryService
from app.services.prompt_version_service import PromptVersionService
from app.services.prompt_search_service import PromptSearchService

logger = logging.getLogger("promptiq.api.prompts")
router = APIRouter(prefix="/prompts", tags=["prompts"])


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a single Server-Sent Events frame (mirror of the helper in
    enhancement.py). ``event:`` names the event type the client dispatches on;
    ``data:`` carries the JSON payload; a blank line terminates the frame.
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _assert_owner(prompt, user_id: UUID) -> None:
    """Ensure the prompt belongs to the caller (VULN-007 / N4).

    Raises PromptNotFoundError (mapped to 404) for non-owners so the endpoint
    never reveals whether a prompt id belonging to someone else exists.
    """
    if str(prompt.user_id) != str(user_id):
        raise PromptNotFoundError("Prompt not found.")


@router.get(
    "/",
    response_model=PaginatedResponse[PromptSummary],
    summary="List Prompts",
    description="Retrieves a paginated list of prompts. Excludes soft-deleted records when enabled and supports sorting.",
)
async def list_prompts(
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
    sort_by: Optional[str] = Query(default="created_at"),
    sort_order: Optional[str] = Query(default="desc"),
    template_id: Optional[str] = Query(default=None),
    ai_model_id: Optional[str] = Query(default=None),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> PaginatedResponse[PromptSummary]:
    try:
        limit = page_size
        offset = (page - 1) * page_size

        # Always scope to the authenticated caller; a client-supplied user_id is
        # no longer honored (prevents cross-user enumeration — N4).
        target_user_id = str(user_id)

        total_count = await prompt_service.count_prompts(
            session=session,
            user_id=target_user_id,
            template_id=template_id,
            ai_model_id=ai_model_id,
        )

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
            total=total_count,
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
    old_analysis: Optional[dict] = None
    new_analysis: Optional[dict] = None
    grade: Optional[str] = None
    created_at: datetime

class PromptSearchResponse(BaseModel):
    success: bool = True
    message: str = "Semantic search complete."
    results: list[PromptSearchMatch]


@router.post(
    "/search",
    response_model=PromptSearchResponse,
    summary="Semantic Search Prompts",
    description="Find user prompts semantically similar to a query prompt using pgvector cosine similarity, with support for advanced metadata filters.",
)
async def semantic_search(
    payload: PromptSearchRequest,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
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
            # Force the caller's own id; ignore any client-supplied user_id (N4).
            user_id=str(user_id),
            date_from=payload.date_from,
            date_to=payload.date_to,
        )
        return PromptSearchResponse(
            results=[PromptSearchMatch(**r) for r in res]
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
    user_id: UUID = Depends(get_current_user_id),
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
        _assert_owner(prompt, user_id)
        
        # Build normalized analysis summary for display
        analysis_data = None
        if prompt.new_analysis:
            analysis_data = {
                "overall_score": prompt.new_analysis.get("overall_score", 0),
                "grade": prompt.grade,
            }

        # Use DB-stored tool recommendations (written by background task),
        # or compute an in-memory fallback without committing to avoid
        # expiring eagerly loaded relationships after session.commit().
        tool_rec_summary = prompt.tool_recommendations
        if not tool_rec_summary:
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
                # NOTE: Do NOT commit here — committing expires all eagerly-loaded
                # relationships (template, versions, etc.) causing greenlet errors.
                # The background task writes tool_recommendations to DB separately.
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
            old_analysis=prompt.old_analysis,
            new_analysis=prompt.new_analysis,
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
    user_id: UUID = Depends(get_current_user_id),
    prompt_service: PromptService = Depends(get_prompt_service),
    history_service: PromptHistoryService = Depends(get_prompt_history_service),
) -> PaginatedResponse[PromptVersionSummary]:
    try:
        prompt = await prompt_service.get_prompt(session, prompt_id)
        _assert_owner(prompt, user_id)
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
    user_id: UUID = Depends(get_current_user_id),
    prompt_service: PromptService = Depends(get_prompt_service),
    version_service: PromptVersionService = Depends(get_prompt_version_service),
    history_service: PromptHistoryService = Depends(get_prompt_history_service),
) -> APIResponse[None]:
    try:
        prompt = await prompt_service.get_prompt(session, prompt_id)
        _assert_owner(prompt, user_id)

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
    description="Permanently deletes a prompt and its version history.",
)
async def delete_prompt(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    prompt_service: PromptService = Depends(get_prompt_service),
) -> APIResponse[None]:
    try:
        prompt = await prompt_service.get_prompt(session, prompt_id)
        _assert_owner(prompt, user_id)
        await prompt_service.delete_prompt(session, prompt_id)
        await session.commit()
        return APIResponse(message="Prompt deleted successfully.", data=None)
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/{prompt_id}/reenhance",
    response_model=ReenhanceVersionResponse,
    summary="Re-enhance Prompt",
    description=(
        "Generates a new enhanced version by taking the latest version's content "
        "and passing it through the same template used in the original enhancement. "
        "Stores the new version in prompt_versions with per-version quality scores. "
        "Does NOT modify the prompts table beyond updating current_version_id."
    ),
)
async def reenhance_prompt(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    prompt_service: PromptService = Depends(get_prompt_service),
    reenhance_service: PromptReenhanceService = Depends(get_prompt_reenhance_service),
) -> ReenhanceVersionResponse:
    try:
        prompt = await prompt_service.get_prompt(session, prompt_id)
        _assert_owner(prompt, user_id)
        result = await reenhance_service.reenhance_prompt(
            session=session,
            prompt_id=prompt_id,
        )
        return ReenhanceVersionResponse(**result)
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/{prompt_id}/reenhance/stream",
    summary="Re-enhance Prompt (Streaming, SSE)",
    description=(
        "Streaming counterpart of POST /prompts/{prompt_id}/reenhance. Emits "
        "Server-Sent Events so the client renders the re-enhanced prompt "
        "token-by-token. Event sequence: `meta` (template) → many `token` frames "
        "(raw text deltas) → `done` (persisted new version + per-version quality "
        "scores and tool recommendations). On failure a single `error` frame is sent. "
        "Unlike the initial enhancement, scores are computed synchronously and "
        "delivered inside the `done` frame, so no follow-up polling is required."
    ),
    response_class=StreamingResponse,
)
async def reenhance_prompt_stream(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
    prompt_service: PromptService = Depends(get_prompt_service),
    reenhance_service: PromptReenhanceService = Depends(get_prompt_reenhance_service),
) -> StreamingResponse:
    # Pre-stream ownership check so a missing/forbidden prompt returns a real
    # 404 before the 200 event-stream begins (mirrors the blocking endpoint).
    # Once the StreamingResponse is returned the status line is already 200, so
    # anything that must surface as a real HTTP status has to run here first.
    try:
        prompt = await prompt_service.get_prompt(session, prompt_id)
        _assert_owner(prompt, user_id)
    except Exception as exc:
        raise map_service_error(exc)

    async def event_generator():
        try:
            final_ev: Optional[dict] = None
            async for ev in reenhance_service.reenhance_prompt_stream(
                session=session,
                prompt_id=prompt_id,
            ):
                etype = ev.get("type")
                if etype == "meta":
                    yield _sse("meta", {
                        "template": {
                            "id": ev["template_id"],
                            "title": ev["template_title"],
                            "similarity": ev["similarity_score"],
                        },
                    })
                elif etype == "delta":
                    yield _sse("token", {"text": ev["text"]})
                elif etype == "final":
                    final_ev = ev

            if final_ev is None:
                raise PromptVersionException("Re-enhance stream ended before producing a result.")

            # The service already persisted + committed the new version; the
            # `done` frame carries the same data the blocking endpoint returns.
            yield _sse("done", final_ev["data"])
        except (PromptNotFoundError, PromptVersionException, DatabaseTransactionException) as exc:
            # Client-safe messages defined in our own service layer.
            logger.warning("Streaming re-enhancement failed: %s", exc)
            yield _sse("error", {"detail": str(exc)})
        except Exception:
            logger.exception("Unexpected error during streaming re-enhancement")
            yield _sse("error", {"detail": "Prompt re-enhancement failed during streaming."})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering (nginx) so tokens flush immediately.
            "X-Accel-Buffering": "no",
        },
    )

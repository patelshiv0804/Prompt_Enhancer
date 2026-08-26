from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import (
    get_session,
    get_current_user,
    get_prompt_enhancement_service,
    get_prompt_analysis_service,
    get_prompt_comparison_service,
    get_prompt_persistence_service,
    get_profile_repository,
    get_template_repository,
    get_tool_recommendation_service,
    get_prompt_classification_service,
)
from app.api.v1.exceptions import map_service_error
from app.services.exceptions import (
    TemplateNotFoundError,
    PromptValidationException,
    PromptEnhancementException,
    TemplateRenderException,
    LLMTimeoutException,
    LLMResponseException,
    SimilarityBelowThresholdError,
    NoTemplateMatchError,
)
from app.services.prompt_enhancement_service import PromptEnhancementService
from app.services.prompt_analysis_service import PromptAnalysisService
from app.services.prompt_comparison_service import PromptComparisonService
from app.services.prompt_persistence_service import PromptPersistenceService
from app.services.tool_recommendation_service import ToolRecommendationService
from app.services.prompt_classification_service import PromptClassificationService

from app.core.config import settings
from app.middleware.rate_limit import llm_rate_limiter

logger = logging.getLogger("promptiq.api.enhancement")
router = APIRouter(tags=["Enhancement & Analysis"])


# Strong references to fire-and-forget background tasks scheduled from inside a
# streaming response. asyncio only keeps a weak reference to the task, so
# without this set a task could be garbage-collected mid-run.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a single Server-Sent Events frame.

    ``event:`` names the event type the browser's reader dispatches on;
    ``data:`` carries the JSON payload. A blank line terminates the frame.
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# Request Models
class EnhancePromptRequest(BaseModel):
    role: Optional[str] = Field(default=None, description="Target role category for template selection", examples=["Marketer"])
    mode: Optional[str] = Field(default=None, description="Target work or study mode", examples=["Market Research"])
    prompt: str = Field(..., max_length=settings.max_prompt_chars, description="Raw prompt content to enhance", examples=["Find the ideal customer for my SaaS."])
    variables: Optional[dict[str, str]] = Field(default=None, description="Template placeholder replacements", examples=[{"BUSINESS_CONTEXT": "remote SaaS", "LANGUAGE": "English"}])
    apply_style: bool = Field(default=False, description="Apply style profile")
    style_profile_id: Optional[UUID] = Field(default=None, description="Style profile UUID")
    enhancement_level: Optional[str] = Field(
        default=None,
        description="Enhancement depth override: 'minimal', 'standard', or 'deep'. Omit (or pass null) to let the AI auto-detect.",
        examples=["standard"],
    )
    template_id: Optional[UUID] = Field(
        default=None,
        description="Explicitly selected library template UUID. When provided, this template's recipe is used for enhancement instead of automatic semantic retrieval.",
    )


class AnalyzePromptRequest(BaseModel):
    prompt: str = Field(..., max_length=settings.max_prompt_chars, description="Prompt content to analyze", examples=["Find my ideal customer."])


class ComparePromptsRequest(BaseModel):
    original_prompt: str = Field(..., max_length=settings.max_prompt_chars, description="Original raw prompt content")
    enhanced_prompt: str = Field(..., max_length=settings.max_prompt_chars, description="Enhanced optimized prompt content")


# Response Models
class EnhanceAnalysisSummary(BaseModel):
    overall_score: int = Field(..., description="Score out of 100", examples=[72])
    grade: str = Field(..., description="Letter grade", examples=["B"])


class EnhanceComparisonSummary(BaseModel):
    before_score: int = Field(..., description="Original prompt score out of 100", examples=[72])
    after_score: int = Field(..., description="Enhanced prompt score out of 100", examples=[95])
    grade_before: str = Field(..., description="Original prompt grade", examples=["B"])
    grade_after: str = Field(..., description="Enhanced prompt grade", examples=["A+"])
    improvements: list[str] = Field(..., description="Key improvement bullets list")


class EnhanceTemplateSummary(BaseModel):
    id: str = Field(..., description="UUID of the matched template")
    title: str = Field(..., description="Title of the matched template")
    similarity: float = Field(..., description="Cosine similarity score", examples=[0.95])


class EnhanceVersionSummary(BaseModel):
    prompt_id: str = Field(..., description="ID of the persisted prompt")
    version_number: int = Field(..., description="Version sequence number", examples=[1])


class ToolEntry(BaseModel):
    name: str = Field(..., description="Name of the recommended AI tool", examples=["Claude"])
    rank: int = Field(..., description="Rank position (1, 2, or 3)", examples=[1])


class ToolRecommendationSummary(BaseModel):
    matched_task: str = Field(..., description="The user task matched from ranking table", examples=["Coding"])
    match_type: str = Field(..., description="How the match was found: exact, alias, consensus, prompt_semantic, mode_semantic, or fallback", examples=["consensus"])
    match_confidence: float = Field(..., description="Confidence of the match (0.0 to 1.0)", examples=[0.87])
    tools: list[ToolEntry] = Field(..., description="Top 3 recommended AI tools for this task")


class EnhancePromptData(BaseModel):
    original_prompt: str
    enhanced_prompt: str
    template: EnhanceTemplateSummary
    version: EnhanceVersionSummary
    analysis: Optional[EnhanceAnalysisSummary] = None
    comparison: Optional[EnhanceComparisonSummary] = None
    tool_recommendations: Optional[ToolRecommendationSummary] = None
    original_analysis: Optional[dict[str, Any]] = None
    enhanced_analysis: Optional[dict[str, Any]] = None
    detected_level: Optional[str] = Field(default=None, description="The enhancement depth that was applied: minimal, standard, or deep")
    level_reason: Optional[str] = Field(default=None, description="Short explanation of why this depth was chosen")


class EnhancePromptResponse(BaseModel):
    success: bool
    message: str
    data: EnhancePromptData


async def _process_background_analysis(
    prompt_id: str,
    original_prompt: str,
    enhanced_prompt: str,
    role: Optional[str],
    mode: Optional[str],
) -> None:
    """
    Background task executing deep LLM analyses, comparison, and tool recommendations.
    Updates Prompt and PromptVersion records in PostgreSQL asynchronously.
    """
    logger.info("Starting background analysis for prompt_id=%s", prompt_id)
    try:
        from app.db.session import async_session
        from app.services.llm.mistral_provider import MistralProvider
        from app.services.prompt_analysis_service import PromptAnalysisService
        from app.services.prompt_comparison_service import PromptComparisonService
        from app.services.tool_recommendation_service import ToolRecommendationService
        from app.services.embedding_service import EmbeddingService
        from app.repositories.prompt import PromptRepository
        from app.repositories.prompt_version import PromptVersionRepository

        llm_provider = MistralProvider()
        analysis_service = PromptAnalysisService(llm_provider=llm_provider)
        comparison_service = PromptComparisonService(llm_provider=llm_provider)
        embedding_service = EmbeddingService()
        tool_rec_service = ToolRecommendationService(embedding_service=embedding_service)

        # Run independent LLM tasks concurrently
        orig_analysis_task = analysis_service.analyze(original_prompt)
        enh_analysis_task = analysis_service.analyze(enhanced_prompt)
        comparison_task = comparison_service.compare(original_prompt, enhanced_prompt)

        async def _safe_tool_rec():
            try:
                return await tool_rec_service.recommend(prompt=original_prompt, mode=mode, role=role)
            except Exception:
                return tool_rec_service.get_fallback()

        orig_analysis, enh_analysis, comparison, tool_rec = await asyncio.gather(
            orig_analysis_task,
            enh_analysis_task,
            comparison_task,
            _safe_tool_rec(),
        )

        tool_rec_summary = {
            "matched_task": tool_rec["matched_task"],
            "match_type": tool_rec["match_type"],
            "match_confidence": tool_rec["match_confidence"],
            "tools": tool_rec["tools"],
        }
        grade_after = comparison["summary"]["grade_improvement"].split(" to ")[-1]
        prompt_update_data = {
            "old_analysis": orig_analysis,
            "new_analysis": enh_analysis,
            "grade": grade_after,
            "tool_recommendations": tool_rec_summary,
        }
        version_update_data = {
            "old_analysis": orig_analysis,
            "new_analysis": enh_analysis,
            "tool_recommendations": tool_rec_summary,
        }

        prompt_repo = PromptRepository()
        version_repo = PromptVersionRepository()

        async with async_session() as session:
            prompt = await prompt_repo.get_by_id(session, prompt_id)
            if not prompt:
                logger.error("Prompt id=%s not found in background task", prompt_id)
                return

            if prompt.current_version_id:
                version = await version_repo.get_by_id(session, str(prompt.current_version_id))
                if version:
                    await version_repo.update(session, version, version_update_data)

            await prompt_repo.update(session, prompt, prompt_update_data)
            logger.info("Successfully completed background analysis for prompt_id=%s, grade=%s", prompt_id, grade_after)
    except Exception as exc:
        logger.exception("Error in background analysis task for prompt_id=%s", prompt_id)


@router.post(
    "/enhance",
    response_model=EnhancePromptResponse,
    dependencies=[Depends(llm_rate_limiter)],
    summary="Enhance Prompt End-to-End",
    description="Orchestrates template search, quality analysis, prompt enhancement, differential comparison, and saves the prompt with its version history.",
)
async def enhance_prompt(
    payload: EnhancePromptRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: Optional[str] = Depends(get_current_user),
    enhancement_service: PromptEnhancementService = Depends(get_prompt_enhancement_service),
    persistence_service: PromptPersistenceService = Depends(get_prompt_persistence_service),
    profile_repo=Depends(get_profile_repository),
    template_repo=Depends(get_template_repository),
    classification_service: PromptClassificationService = Depends(get_prompt_classification_service),
) -> EnhancePromptResponse:
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        profile = await profile_repo.get_by_email(session, current_user)
        if not profile:
            raise HTTPException(status_code=404, detail="Authenticated profile user not found.")

        # Check and load style profile
        style_attributes = None
        if payload.apply_style and payload.style_profile_id:
            from app.db.models import StyleProfile
            style_profile = await session.get(StyleProfile, payload.style_profile_id)
            if not style_profile or style_profile.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Style profile not found.")
            # Owner-or-null scoping: a style is usable only if it belongs to the
            # caller or is a shared/legacy profile with no owner (VULN-013).
            if style_profile.user_id is not None and str(style_profile.user_id) != str(profile.id):
                raise HTTPException(status_code=404, detail="Style profile not found.")
            style_attributes = style_profile.attributes

        # Resolve enhancement level: forced override OR AI auto-detection
        _valid_levels = {"minimal", "standard", "deep"}
        if payload.enhancement_level and payload.enhancement_level.lower() in _valid_levels:
            resolved_level = payload.enhancement_level.lower()
            resolved_reason = f"Manually set to {resolved_level}."
            logger.info("Enhancement level forced by user: %s", resolved_level)
        else:
            # Auto-detect via classifier (never blocks — has internal fallback)
            classification = await classification_service.classify(payload.prompt)
            resolved_level = classification["level"]
            resolved_reason = classification["reason"]
            logger.info("Enhancement level auto-detected: %s (%s)", resolved_level, resolved_reason)

        # If the user explicitly applied a library template in the optimizer,
        # that template drives the enhancement: load it and pass it as an
        # override so its own recipe (body) and role/mode framing are used,
        # mirroring the re-enhance flow. With no template_id supplied, the
        # normal semantic-retrieval path runs completely unchanged.
        template_override = None
        effective_role = payload.role
        effective_mode = payload.mode
        if payload.template_id is not None:
            template_override = await template_repo.get_by_id(session, str(payload.template_id))
            if not template_override or getattr(template_override, "deleted_at", None) is not None:
                raise TemplateNotFoundError("Selected template not found.")
            effective_role = template_override.role or payload.role
            effective_mode = template_override.mode or payload.mode

        # 1. Run prompt enhancement (~5s)
        enhance_res = await enhancement_service.enhance_prompt(
            session=session,
            role=effective_role,
            mode=effective_mode,
            prompt=payload.prompt,
            variables=payload.variables,
            style_attributes=style_attributes,
            template_override=template_override,
            enhancement_level=resolved_level,
        )
        enhanced_text = enhance_res["enhanced_prompt"]

        # 2. Persist initial record in PostgreSQL immediately
        prompt_record = await persistence_service.create_prompt_with_version(
            session=session,
            user_id=str(profile.id),
            original_prompt=payload.prompt,
            enhanced_prompt=enhanced_text,
            template_id=enhance_res["template_id"],
            old_analysis=None,
            new_analysis=None,
            grade=None,
            title=f"{effective_role} - {effective_mode}",
            tool_recommendations=None,
        )
        await session.commit()

        # 3. Schedule background analysis & DB update
        background_tasks.add_task(
            _process_background_analysis,
            prompt_id=str(prompt_record.id),
            original_prompt=payload.prompt,
            enhanced_prompt=enhanced_text,
            role=effective_role,
            mode=effective_mode,
        )

        # 4. Return instant response (~5s)
        data = EnhancePromptData(
            original_prompt=payload.prompt,
            enhanced_prompt=enhanced_text,
            original_analysis=None,
            enhanced_analysis=None,
            analysis=None,
            comparison=None,
            tool_recommendations=None,
            detected_level=resolved_level,
            level_reason=resolved_reason,
            template=EnhanceTemplateSummary(
                id=enhance_res["template_id"],
                title=enhance_res["template_title"],
                similarity=enhance_res["similarity_score"],
            ),
            version=EnhanceVersionSummary(
                version_number=1,
                prompt_id=str(prompt_record.id),
            ),
        )
        return EnhancePromptResponse(
            success=True,
            message="Prompt enhanced successfully. Detailed quality analysis is processing in background.",
            data=data,
        )
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/enhance/stream",
    dependencies=[Depends(llm_rate_limiter)],
    summary="Enhance Prompt (Streaming, SSE)",
    description=(
        "Streaming counterpart of POST /enhance. Emits Server-Sent Events so the "
        "client can render the optimized prompt token-by-token instead of waiting "
        "for the full response. Event sequence: `meta` (template + detected depth) "
        "→ many `token` frames (raw text deltas) → `done` (authoritative cleaned "
        "prompt + persisted prompt_id). On failure a single `error` frame is sent. "
        "Detailed quality scores are still computed in the background and fetched via "
        "GET /prompts/{id}, exactly as with the non-streaming endpoint."
    ),
    response_class=StreamingResponse,
)
async def enhance_prompt_stream(
    payload: EnhancePromptRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Optional[str] = Depends(get_current_user),
    enhancement_service: PromptEnhancementService = Depends(get_prompt_enhancement_service),
    persistence_service: PromptPersistenceService = Depends(get_prompt_persistence_service),
    profile_repo=Depends(get_profile_repository),
    template_repo=Depends(get_template_repository),
    classification_service: PromptClassificationService = Depends(get_prompt_classification_service),
) -> StreamingResponse:
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required.")

    # ---- Pre-stream setup ---------------------------------------------------
    # Everything that can fail with a meaningful HTTP status (auth, profile,
    # style-profile scoping, template override, level classification) runs here,
    # BEFORE the response body starts. Once we return the StreamingResponse the
    # status line is already 200 and errors can only be reported as SSE `error`
    # frames — so we front-load anything that should surface as a real 4xx/5xx.
    try:
        profile = await profile_repo.get_by_email(session, current_user)
        if not profile:
            raise HTTPException(status_code=404, detail="Authenticated profile user not found.")

        style_attributes = None
        if payload.apply_style and payload.style_profile_id:
            from app.db.models import StyleProfile
            style_profile = await session.get(StyleProfile, payload.style_profile_id)
            if not style_profile or style_profile.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Style profile not found.")
            if style_profile.user_id is not None and str(style_profile.user_id) != str(profile.id):
                raise HTTPException(status_code=404, detail="Style profile not found.")
            style_attributes = style_profile.attributes

        # Resolve enhancement level: forced override OR AI auto-detection
        _valid_levels = {"minimal", "standard", "deep"}
        if payload.enhancement_level and payload.enhancement_level.lower() in _valid_levels:
            resolved_level = payload.enhancement_level.lower()
            resolved_reason = f"Manually set to {resolved_level}."
            logger.info("Enhancement level forced by user: %s", resolved_level)
        else:
            classification = await classification_service.classify(payload.prompt)
            resolved_level = classification["level"]
            resolved_reason = classification["reason"]
            logger.info("Enhancement level auto-detected: %s (%s)", resolved_level, resolved_reason)

        template_override = None
        effective_role = payload.role
        effective_mode = payload.mode
        if payload.template_id is not None:
            template_override = await template_repo.get_by_id(session, str(payload.template_id))
            if not template_override or getattr(template_override, "deleted_at", None) is not None:
                raise TemplateNotFoundError("Selected template not found.")
            effective_role = template_override.role or payload.role
            effective_mode = template_override.mode or payload.mode
    except HTTPException:
        raise
    except Exception as exc:
        raise map_service_error(exc)

    # ---- Stream -------------------------------------------------------------
    async def event_generator():
        try:
            final_ev: Optional[dict] = None
            async for ev in enhancement_service.enhance_prompt_stream(
                session=session,
                role=effective_role,
                mode=effective_mode,
                prompt=payload.prompt,
                variables=payload.variables,
                style_attributes=style_attributes,
                template_override=template_override,
                enhancement_level=resolved_level,
            ):
                etype = ev.get("type")
                if etype == "meta":
                    yield _sse("meta", {
                        "template": {
                            "id": ev["template_id"],
                            "title": ev["template_title"],
                            "similarity": ev["similarity_score"],
                        },
                        "detected_level": resolved_level,
                        "level_reason": resolved_reason,
                    })
                elif etype == "delta":
                    yield _sse("token", {"text": ev["text"]})
                elif etype == "final":
                    final_ev = ev

            if final_ev is None:
                raise PromptEnhancementException("Streaming ended before producing a result.")

            enhanced_text = final_ev["enhanced_prompt"]

            # Persist the prompt + first version now that the full text is known.
            # The request-scoped session stays open until this generator is
            # exhausted, so the commit here (and the dependency's own trailing
            # commit) both operate on a live session.
            prompt_record = await persistence_service.create_prompt_with_version(
                session=session,
                user_id=str(profile.id),
                original_prompt=payload.prompt,
                enhanced_prompt=enhanced_text,
                template_id=final_ev["template_id"],
                old_analysis=None,
                new_analysis=None,
                grade=None,
                title=f"{effective_role} - {effective_mode}",
                tool_recommendations=None,
            )
            await session.commit()

            # Fire-and-forget deep analysis. Can't use FastAPI BackgroundTasks
            # here (no Response object to attach them to inside a generator), so
            # schedule directly and hold a strong reference until it completes.
            analysis_task = asyncio.create_task(
                _process_background_analysis(
                    prompt_id=str(prompt_record.id),
                    original_prompt=payload.prompt,
                    enhanced_prompt=enhanced_text,
                    role=effective_role,
                    mode=effective_mode,
                )
            )
            _BACKGROUND_TASKS.add(analysis_task)
            analysis_task.add_done_callback(_BACKGROUND_TASKS.discard)

            yield _sse("done", {
                "original_prompt": payload.prompt,
                "enhanced_prompt": enhanced_text,
                "template": {
                    "id": final_ev["template_id"],
                    "title": final_ev["template_title"],
                    "similarity": final_ev["similarity_score"],
                },
                "version": {
                    "prompt_id": str(prompt_record.id),
                    "version_number": 1,
                },
                "detected_level": resolved_level,
                "level_reason": resolved_reason,
            })
        except (
            PromptValidationException,
            PromptEnhancementException,
            TemplateRenderException,
            TemplateNotFoundError,
            LLMTimeoutException,
            LLMResponseException,
            SimilarityBelowThresholdError,
            NoTemplateMatchError,
        ) as exc:
            if isinstance(exc, (SimilarityBelowThresholdError, NoTemplateMatchError)):
                err_detail = "Try selecting a specific role or mode, or rephrasing your prompt."
            else:
                err_detail = str(exc)
            logger.warning("Streaming enhancement failed: %s", exc)
            yield _sse("error", {"detail": err_detail})
        except Exception:
            logger.exception("Unexpected error during streaming enhancement")
            yield _sse("error", {"detail": "Prompt enhancement failed during streaming."})

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


@router.post(
    "/analyze",
    response_model=dict[str, Any],
    dependencies=[Depends(llm_rate_limiter)],
    summary="Analyze Prompt Quality",
    description="Evaluates a prompt against 8 dimensions of prompt engineering, scoring quality metrics and generating grade and suggestion reports.",
)
async def analyze_prompt(
    payload: AnalyzePromptRequest,
    analysis_service: PromptAnalysisService = Depends(get_prompt_analysis_service),
) -> dict[str, Any]:
    try:
        return await analysis_service.analyze(payload.prompt)
    except Exception as exc:
        raise map_service_error(exc)


@router.post(
    "/compare",
    response_model=dict[str, Any],
    dependencies=[Depends(llm_rate_limiter)],
    summary="Compare Original and Enhanced Prompts",
    description="Generates differential metrics, fixed gaps, readability scores, and estimated quality score delta between two prompts.",
)
async def compare_prompts(
    payload: ComparePromptsRequest,
    comparison_service: PromptComparisonService = Depends(get_prompt_comparison_service),
) -> dict[str, Any]:
    try:
        return await comparison_service.compare(payload.original_prompt, payload.enhanced_prompt)
    except Exception as exc:
        raise map_service_error(exc)


class RecommendToolsRequest(BaseModel):
    prompt: str = Field(..., max_length=settings.max_prompt_chars, description="Prompt text to analyze for tool recommendation")
    mode: Optional[str] = Field(default=None, description="Task mode")
    role: Optional[str] = Field(default=None, description="User role")


@router.post(
    "/tools/recommend",
    response_model=ToolRecommendationSummary,
    dependencies=[Depends(llm_rate_limiter)],
    summary="Get Recommended AI Tools",
    description="Recommends the top 3 AI tools for a given prompt, mode, and role.",
)
async def recommend_tools(
    payload: RecommendToolsRequest,
    tool_recommendation_service: ToolRecommendationService = Depends(get_tool_recommendation_service),
) -> ToolRecommendationSummary:
    try:
        tool_rec = await tool_recommendation_service.recommend(
            prompt=payload.prompt,
            mode=payload.mode,
            role=payload.role,
        )
    except Exception:
        tool_rec = tool_recommendation_service.get_fallback()

    return ToolRecommendationSummary(
        matched_task=tool_rec["matched_task"],
        match_type=tool_rec["match_type"],
        match_confidence=tool_rec["match_confidence"],
        tools=[ToolEntry(**t) for t in tool_rec["tools"]],
    )


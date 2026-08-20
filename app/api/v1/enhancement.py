from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
    get_tool_recommendation_service,
)
from app.api.v1.exceptions import map_service_error
from app.services.prompt_enhancement_service import PromptEnhancementService
from app.services.prompt_analysis_service import PromptAnalysisService
from app.services.prompt_comparison_service import PromptComparisonService
from app.services.prompt_persistence_service import PromptPersistenceService
from app.services.tool_recommendation_service import ToolRecommendationService

logger = logging.getLogger("promptiq.api.enhancement")
router = APIRouter(tags=["Enhancement & Analysis"])


# Request Models
class EnhancePromptRequest(BaseModel):
    role: Optional[str] = Field(default=None, description="Target role category for template selection", examples=["Marketer"])
    mode: Optional[str] = Field(default=None, description="Target work or study mode", examples=["Market Research"])
    prompt: str = Field(..., description="Raw prompt content to enhance", examples=["Find the ideal customer for my SaaS."])
    variables: Optional[dict[str, str]] = Field(default=None, description="Template placeholder replacements", examples=[{"BUSINESS_CONTEXT": "remote SaaS", "LANGUAGE": "English"}])
    apply_style: bool = Field(default=False, description="Apply style profile")
    style_profile_id: Optional[UUID] = Field(default=None, description="Style profile UUID")


class AnalyzePromptRequest(BaseModel):
    prompt: str = Field(..., description="Prompt content to analyze", examples=["Find my ideal customer."])


class ComparePromptsRequest(BaseModel):
    original_prompt: str = Field(..., description="Original raw prompt content")
    enhanced_prompt: str = Field(..., description="Enhanced optimized prompt content")


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
) -> EnhancePromptResponse:
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required. Send X-Current-User header.")

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
            style_attributes = style_profile.attributes

        # 1. Run prompt enhancement (~5s)
        enhance_res = await enhancement_service.enhance_prompt(
            session=session,
            role=payload.role,
            mode=payload.mode,
            prompt=payload.prompt,
            variables=payload.variables,
            style_attributes=style_attributes,
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
            title=f"{payload.role} - {payload.mode}",
            tool_recommendations=None,
        )
        await session.commit()

        # 3. Schedule background analysis & DB update
        background_tasks.add_task(
            _process_background_analysis,
            prompt_id=str(prompt_record.id),
            original_prompt=payload.prompt,
            enhanced_prompt=enhanced_text,
            role=payload.role,
            mode=payload.mode,
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
    "/analyze",
    response_model=dict[str, Any],
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
    prompt: str = Field(..., description="Prompt text to analyze for tool recommendation")
    mode: Optional[str] = Field(default=None, description="Task mode")
    role: Optional[str] = Field(default=None, description="User role")


@router.post(
    "/tools/recommend",
    response_model=ToolRecommendationSummary,
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


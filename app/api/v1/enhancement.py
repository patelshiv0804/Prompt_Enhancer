from __future__ import annotations

import logging
from typing import Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
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
)
from app.api.v1.exceptions import map_service_error
from app.services.prompt_enhancement_service import PromptEnhancementService
from app.services.prompt_analysis_service import PromptAnalysisService
from app.services.prompt_comparison_service import PromptComparisonService
from app.services.prompt_persistence_service import PromptPersistenceService

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
    version_number: int = Field(..., description="Version sequence number", examples=[1])


class EnhancePromptData(BaseModel):
    original_prompt: str
    enhanced_prompt: str
    analysis: EnhanceAnalysisSummary
    comparison: EnhanceComparisonSummary
    template: EnhanceTemplateSummary
    version: EnhanceVersionSummary


class EnhancePromptResponse(BaseModel):
    success: bool
    message: str
    data: EnhancePromptData


@router.post(
    "/enhance",
    response_model=EnhancePromptResponse,
    summary="Enhance Prompt End-to-End",
    description="Orchestrates template search, quality analysis, prompt enhancement, differential comparison, and saves the prompt with its version history.",
)
async def enhance_prompt(
    payload: EnhancePromptRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Optional[str] = Depends(get_current_user),
    enhancement_service: PromptEnhancementService = Depends(get_prompt_enhancement_service),
    analysis_service: PromptAnalysisService = Depends(get_prompt_analysis_service),
    comparison_service: PromptComparisonService = Depends(get_prompt_comparison_service),
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

        # 1. Run prompt enhancement
        enhance_res = await enhancement_service.enhance_prompt(
            session=session,
            role=payload.role,
            mode=payload.mode,
            prompt=payload.prompt,
            variables=payload.variables,
            style_attributes=style_attributes,
        )
        enhanced_text = enhance_res["enhanced_prompt"]

        # 2. Analyze original prompt
        orig_analysis = await analysis_service.analyze(payload.prompt)

        # 3. Analyze enhanced prompt
        enh_analysis = await analysis_service.analyze(enhanced_text)

        # 4. Compare prompts
        comparison = await comparison_service.compare(payload.prompt, enhanced_text)

        # 5. Persist to database in a single transaction
        grade_after = comparison["summary"]["grade_improvement"].split(" to ")[-1]
        prompt_record = await persistence_service.create_prompt_with_version(
            session=session,
            user_id=str(profile.id),
            original_prompt=payload.prompt,
            enhanced_prompt=enhanced_text,
            template_id=enhance_res["template_id"],
            total_score=comparison["summary"]["after_score"],
            grade=grade_after,
            title=f"{payload.role} - {payload.mode}",
        )
        await session.commit()

        # Build paginated/normalized data
        data = EnhancePromptData(
            original_prompt=payload.prompt,
            enhanced_prompt=enhanced_text,
            analysis=EnhanceAnalysisSummary(
                overall_score=orig_analysis["overall_score"],
                grade=orig_analysis["grade"],
            ),
            comparison=EnhanceComparisonSummary(
                before_score=int(comparison["summary"]["before_score"] * 10),
                after_score=int(comparison["summary"]["after_score"] * 10),
                grade_before=comparison["summary"]["grade_improvement"].split(" to ")[0],
                grade_after=grade_after,
                improvements=comparison["improvements"],
            ),
            template=EnhanceTemplateSummary(
                id=enhance_res["template_id"],
                title=enhance_res["template_title"],
                similarity=enhance_res["similarity_score"],
            ),
            version=EnhanceVersionSummary(
                version_number=1,
            ),
        )
        return EnhancePromptResponse(
            success=True,
            message="Prompt enhanced successfully",
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

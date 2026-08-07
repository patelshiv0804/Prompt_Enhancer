from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import PromptGrade
from .prompt_version import PromptVersionSummary
from .template import TemplateSummary
from .ai_model import AIModelSummary


class PromptBase(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    original_prompt: str = Field(..., min_length=1)
    template_id: Optional[UUID] = None
    ai_model_id: Optional[UUID] = None
    current_version_id: Optional[UUID] = None


class PromptCreate(PromptBase):
    original_prompt: str = Field(..., min_length=1)


class PromptUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    original_prompt: Optional[str] = Field(default=None, min_length=1)
    template_id: Optional[UUID] = None
    ai_model_id: Optional[UUID] = None
    current_version_id: Optional[UUID] = None
    old_analysis: Optional[dict] = None
    new_analysis: Optional[dict] = None
    grade: Optional[PromptGrade] = None
    tool_recommendations: Optional[dict] = None


class PromptSummary(BaseModel):
    id: UUID
    title: Optional[str] = None
    original_prompt: Optional[str] = None
    template_id: Optional[UUID] = None
    ai_model_id: Optional[UUID] = None
    current_version_id: Optional[UUID] = None
    old_analysis: Optional[dict] = None
    new_analysis: Optional[dict] = None
    grade: Optional[str] = None
    tool_recommendations: Optional[dict] = None
    template: Optional[TemplateSummary] = None
    ai_model: Optional[AIModelSummary] = None
    current_version: Optional[PromptVersionSummary] = None
    created_at: datetime
    updated_at: datetime


class PromptRead(PromptSummary):
    original_prompt: str


class PromptDetailResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    original_prompt: str
    template: Optional[TemplateSummary] = None
    ai_model: Optional[AIModelSummary] = None
    current_version: Optional[PromptVersionSummary] = None
    version_count: int = Field(default=0, ge=0)
    old_analysis: Optional[dict] = None
    new_analysis: Optional[dict] = None
    grade: Optional[str] = None
    analysis: Optional[dict] = None
    tool_recommendations: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class RegeneratePromptRequest(BaseModel):
    feedback: Optional[str] = Field(default=None, description="Natural language feedback to refine the prompt")


class RegenerateAnalysisSummary(BaseModel):
    overall_score: int
    grade: str


class RegeneratePromptData(BaseModel):
    prompt_id: UUID
    version_number: int
    enhanced_prompt: str
    analysis: RegenerateAnalysisSummary


class RegeneratePromptResponse(BaseModel):
    success: bool
    message: str
    data: RegeneratePromptData

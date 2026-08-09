from __future__ import annotations

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import VersionType


class PromptVersionBase(BaseModel):
    version_number: int = Field(..., ge=1)
    version_type: Optional[str] = None
    content: str = Field(..., min_length=1)
    change_summary: Optional[str] = Field(default=None, max_length=1000)


class PromptVersionCreate(PromptVersionBase):
    version_number: int = Field(..., ge=1)
    content: str = Field(..., min_length=1)


class PromptVersionRead(PromptVersionBase):
    id: UUID
    prompt_id: UUID
    created_at: datetime
    updated_at: datetime
    # Per-version scores (nullable for legacy versions created before this feature)
    old_analysis: Optional[dict[str, Any]] = None
    new_analysis: Optional[dict[str, Any]] = None
    tool_recommendations: Optional[dict[str, Any]] = None
    template_id: Optional[UUID] = None


class PromptVersionSummary(BaseModel):
    id: UUID
    version_number: int
    version_type: Optional[str] = None
    content: Optional[str] = None
    change_summary: Optional[str] = None
    created_at: datetime
    # Per-version scores (nullable for legacy versions)
    old_analysis: Optional[dict[str, Any]] = None
    new_analysis: Optional[dict[str, Any]] = None
    tool_recommendations: Optional[dict[str, Any]] = None
    template_id: Optional[UUID] = None


class PromptVersionRestoreRequest(BaseModel):
    version_id: UUID


# ── Re-enhance response schemas ──────────────────────────────────────────────

class ReenhanceAnalysisSummary(BaseModel):
    overall_score: int
    grade: str


class ReenhanceVersionData(BaseModel):
    prompt_id: UUID
    version_id: UUID
    version_number: int
    enhanced_prompt: str
    template_id: Optional[str] = None
    old_analysis: Optional[dict[str, Any]] = None
    new_analysis: Optional[dict[str, Any]] = None
    tool_recommendations: Optional[dict[str, Any]] = None


class ReenhanceVersionResponse(BaseModel):
    success: bool
    message: str
    data: ReenhanceVersionData

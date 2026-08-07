from __future__ import annotations

from datetime import datetime
from typing import Optional
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


class PromptVersionSummary(BaseModel):
    id: UUID
    version_number: int
    version_type: Optional[str] = None
    content: Optional[str] = None
    change_summary: Optional[str] = None
    created_at: datetime


class PromptVersionRestoreRequest(BaseModel):
    version_id: UUID

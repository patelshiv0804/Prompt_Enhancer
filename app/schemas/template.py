from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .enums import TemplateMode


class TemplateBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    body: str = Field(..., min_length=1)
    mode: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=100)
    ai_model_id: Optional[UUID] = None
    tags: Optional[List[str]] = Field(default_factory=list)


class TemplateCreate(TemplateBase):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    ai_model_id: Optional[UUID] = None


class TemplateUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    body: Optional[str] = Field(default=None, min_length=1)
    mode: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=100)
    ai_model_id: Optional[UUID] = None
    tags: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    is_approved: Optional[bool] = None
    use_count: Optional[int] = Field(default=None, ge=0)


class TemplateSummary(BaseModel):
    id: UUID
    title: str
    category: Optional[str] = None
    role: Optional[str] = None
    mode: Optional[str] = None
    is_featured: bool
    is_approved: bool
    user_id: Optional[UUID] = None
    is_custom: bool = False

    @model_validator(mode="before")
    @classmethod
    def set_is_custom(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("is_custom"):
                data["is_custom"] = data.get("user_id") is not None
        elif hasattr(data, "user_id"):
            pass
        return data


class TemplateRead(TemplateSummary):
    description: Optional[str] = None
    body: str
    ai_model_id: UUID
    tags: List[str] = Field(default_factory=list)
    use_count: int
    created_at: datetime
    updated_at: datetime


class TemplateResponse(TemplateSummary):
    description: Optional[str] = None
    body: Optional[str] = None
    ai_model_id: UUID
    tags: List[str] = Field(default_factory=list)
    use_count: int
    created_at: datetime
    updated_at: datetime


class TemplateListItem(TemplateSummary):
    """Card metadata for the templates library.

    Deliberately excludes the prompt ``body`` (the proprietary "recipe") for
    public templates browsing, which must never reach the client uninvited.
    """

    description: Optional[str] = None
    ai_model_id: UUID
    tags: List[str] = Field(default_factory=list)
    use_count: int
    created_at: datetime
    updated_at: datetime


class TemplateSearchResponse(BaseModel):
    items: list[TemplateSummary]
    total: int
    page: int
    page_size: int

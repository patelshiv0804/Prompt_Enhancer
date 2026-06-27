from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import ModelProvider


class AIModelBase(BaseModel):
    provider: ModelProvider = Field(...)
    model_name: str = Field(..., max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = Field(default=True)
    supports_analysis: Optional[bool] = Field(default=True)
    supports_optimization: Optional[bool] = Field(default=True)


class AIModelCreate(AIModelBase):
    provider: ModelProvider = Field(...)
    model_name: str = Field(..., max_length=150)


class AIModelUpdate(BaseModel):
    provider: Optional[ModelProvider] = None
    model_name: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None
    supports_analysis: Optional[bool] = None
    supports_optimization: Optional[bool] = None


class AIModelSummary(BaseModel):
    id: UUID
    provider: ModelProvider
    model_name: str
    is_active: bool


class AIModelRead(AIModelSummary):
    description: Optional[str] = None
    supports_analysis: bool
    supports_optimization: bool
    created_at: datetime
    updated_at: datetime

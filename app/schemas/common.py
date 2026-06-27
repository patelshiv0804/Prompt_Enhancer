from __future__ import annotations

from datetime import datetime
from typing import Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

T = TypeVar("T")


class TimestampResponse(BaseModel):
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    success: bool = Field(default=False)
    message: str
    errors: Optional[dict[str, str]] = None


class APIResponse(GenericModel, Generic[T]):
    success: bool = Field(default=True)
    message: str
    data: Optional[T] = None


class PaginatedResponse(GenericModel, Generic[T]):
    success: bool = Field(default=True)
    message: str
    data: list[T]
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)


class PageResponse(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)

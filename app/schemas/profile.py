from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ProfileBase(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    is_active: Optional[bool] = Field(default=True)
    

class ProfileCreate(ProfileBase):
    email: EmailStr = Field(..., max_length=255)


class ProfileUpdate(BaseModel):
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    is_active: Optional[bool] = None


class ProfileSummary(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool


class ProfileRead(ProfileSummary):
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

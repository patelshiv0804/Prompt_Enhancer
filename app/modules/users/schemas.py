"""
Users module — Pydantic schemas for profile API request/response.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Profile Schemas ──────────────────────────────────────

class ProfileResponse(BaseModel):
    """Full profile response returned to the client."""
    id: UUID
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    plan: str
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """Fields that can be updated on the profile (used with multipart form)."""
    display_name: Optional[str] = Field(None, max_length=100)
    # avatar_url is set from the uploaded file, not from JSON body


class PlanResponse(BaseModel):
    """Subscription plan details."""
    plan: str
    limits: dict

    model_config = {"from_attributes": True}


class OnboardingUpdate(BaseModel):
    """Mark onboarding as complete."""
    onboarding_completed: bool = True


# ── Stats & Activity Schemas ─────────────────────────────

class StatsResponse(BaseModel):
    """User dashboard statistics."""
    total_prompts: int = 0
    total_templates: int = 0
    total_chains: int = 0
    total_optimizations: int = 0
    plan: str
    member_since: datetime


class ActivityItem(BaseModel):
    """Single activity entry."""
    action: str
    description: str
    timestamp: datetime


class ActivityResponse(BaseModel):
    """Recent activity summary."""
    activities: list[ActivityItem] = []
    total_count: int = 0

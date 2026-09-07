"""
Users module — FastAPI router for profile management endpoints (Module A).
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session as get_db
from app.core.security import get_current_user_id
from app.schemas.user import (
    OnboardingUpdate,
    ProfileResponse,
    StatsResponse,
)
from app.services.user_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Profile Management"])


# ── P01: Get current user profile ────────────────────────
@router.get(
    "/me",
    response_model=ProfileResponse,
    summary="Get current user profile",
)
async def get_profile(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the logged-in user's profile information."""
    service = ProfileService(db)
    return await service.get_profile(user_id)


# ── P02: Update display name / avatar ────────────────────
@router.patch(
    "/me",
    response_model=ProfileResponse,
    summary="Update display name or avatar",
)
async def update_profile(
    display_name: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Update profile information.
    Accepts multipart form data for avatar file upload.
    """
    service = ProfileService(db)
    return await service.update_profile(
        user_id=user_id,
        display_name=display_name,
        role=role,
        avatar_file=avatar,
    )


# ── P06: Mark onboarding complete ────────────────────────
@router.patch(
    "/onboarding",
    response_model=ProfileResponse,
    summary="Mark onboarding complete",
)
async def update_onboarding(
    body: OnboardingUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's onboarding completion status."""
    service = ProfileService(db)
    return await service.update_onboarding(user_id, body.onboarding_completed)


# ── P07: User dashboard statistics ───────────────────────
@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get dashboard statistics",
)
async def get_stats(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get user dashboard statistics (prompts, templates, chains, etc.)."""
    service = ProfileService(db)
    return await service.get_stats(user_id)

"""
Users module — FastAPI router for profile management endpoints (Module A).
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session as get_db
from app.core.security import get_current_user_id
from app.schemas.auth import MessageResponse, OTPRequest, OTPVerify
from app.services.auth_service import AuthService
from app.schemas.user import (
    ActivityResponse,
    OnboardingUpdate,
    PlanResponse,
    ProfileResponse,
    StatsResponse,
)
from app.services.user_service import ProfileService
from app.utils.email_service import send_otp_email
from app.schemas.prompt import PromptRead

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
    if avatar and avatar.filename:
        allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"}
        if avatar.content_type and avatar.content_type.lower() not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only JPEG, PNG, WebP, GIF, and SVG images are allowed.",
            )
        contents = await avatar.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds maximum allowed limit of 5MB.",
            )
        await avatar.seek(0)

    service = ProfileService(db)
    return await service.update_profile(
        user_id=user_id,
        display_name=display_name,
        role=role,
        avatar_file=avatar,
    )



# ── P03: Soft delete account ─────────────────────────────
@router.delete(
    "/me",
    response_model=ProfileResponse,
    summary="Soft delete account",
)
async def delete_profile(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate account without permanently deleting data.
    The account can be restored via the restore endpoint.
    """
    service = ProfileService(db)
    return await service.soft_delete(user_id)


# ── P04: Restore deleted account (Step 1: Request OTP) ───
@router.post(
    "/restore",
    response_model=MessageResponse,
    summary="Request OTP to restore deleted account",
)
async def request_restore(
    body: OTPRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Send an OTP to the user's email for account restoration.
    The email must exist in the database.
    """
    auth_service = AuthService(db)
    otp = await auth_service.request_restore_otp(body.email)

    # Send OTP via email in background
    background_tasks.add_task(send_otp_email, body.email, otp)

    return MessageResponse(message="OTP sent to your email address")


# ── P04: Restore deleted account (Step 2: Verify OTP) ────
@router.post(
    "/restore/verify",
    response_model=ProfileResponse,
    summary="Verify OTP and restore account",
)
async def verify_restore(
    body: OTPVerify,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the OTP and restore the soft-deleted account.
    """
    # Verify OTP first
    AuthService.verify_otp(body.email, body.otp)

    # Restore the profile
    service = ProfileService(db)
    return await service.restore_account(body.email)


# ── P05: Get current subscription plan ───────────────────
@router.get(
    "/plan",
    response_model=PlanResponse,
    summary="Get current subscription plan",
)
async def get_plan(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's current subscription plan with usage limits."""
    service = ProfileService(db)
    return await service.get_plan(user_id)


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


# ── P08: Recent activity summary ─────────────────────────
@router.get(
    "/activity",
    response_model=ActivityResponse,
    summary="Get recent activity",
)
async def get_activity(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's recent activity summary."""
    service = ProfileService(db)
    return await service.get_activity(user_id)


# ── P09: Get current user prompts ────────────────────────
@router.get(
    "/prompts",
    response_model=List[PromptRead],
    summary="Get current user prompts",
)
async def get_user_prompts(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch all prompts created by the logged-in user."""
    service = ProfileService(db)
    return await service.get_user_prompts(user_id)

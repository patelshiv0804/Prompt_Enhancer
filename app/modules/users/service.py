"""
Users module — Business logic for profile management (Module A).
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.constants import ALLOWED_AVATAR_EXTENSIONS, MAX_AVATAR_FILE_SIZE
from app.core.exceptions import (
    AccountDeletedException,
    NotFoundException,
    ValidationException,
)
from app.core.logger import logger
from app.modules.users.models import Profile
from app.modules.users.repository import ProfileRepository, SettingsRepository
from app.modules.users.schemas import (
    ActivityItem,
    ActivityResponse,
    PlanResponse,
    StatsResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

# ── Plan limits mapping ──────────────────────────────────
PLAN_LIMITS = {
    "free": {
        "prompts_per_day": 10,
        "templates": 5,
        "chains": 3,
        "models": ["chatgpt"],
        "history_days": 7,
    },
    "pro": {
        "prompts_per_day": 100,
        "templates": 50,
        "chains": 20,
        "models": ["chatgpt", "gpt-4", "claude-sonnet-4.5", "gemini-pro"],
        "history_days": 90,
    },
    "team": {
        "prompts_per_day": 500,
        "templates": 200,
        "chains": 100,
        "models": ["chatgpt", "gpt-4", "gpt-5", "claude-sonnet-4.5", "claude-opus-4", "gemini-pro"],
        "history_days": 365,
    },
    "enterprise": {
        "prompts_per_day": -1,  # unlimited
        "templates": -1,
        "chains": -1,
        "models": ["all"],
        "history_days": -1,
    },
}


class ProfileService:
    """Business logic for profile management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.settings_repo = SettingsRepository(db)

    # ── P01: Get current user profile ────────────────────
    async def get_profile(self, user_id: UUID) -> Profile:
        """Fetch profile. Raises if not found or deleted."""
        profile = await self.profile_repo.get_by_id(user_id)
        if not profile:
            raise NotFoundException("Profile")
        if profile.is_deleted:
            raise AccountDeletedException()
        return profile

    # ── Registration helper ──────────────────────────────
    async def create_profile(
        self,
        user_id: UUID,
        email: str,
        display_name: Optional[str] = None,
    ) -> Profile:
        """Create profile + default settings (called during registration)."""
        profile = await self.profile_repo.create(
            user_id=user_id,
            email=email,
            display_name=display_name,
        )
        await self.settings_repo.create_defaults(user_id=user_id)
        logger.info(f"Profile + settings created for user {user_id}")
        return profile

    # ── P02: Update display name / avatar ────────────────
    async def update_profile(
        self,
        user_id: UUID,
        display_name: Optional[str] = None,
        avatar_file: Optional[UploadFile] = None,
    ) -> Profile:
        """Update profile with optional avatar file upload."""
        profile = await self.get_profile(user_id)

        update_data = {}

        if display_name is not None:
            update_data["display_name"] = display_name

        if avatar_file:
            avatar_url = await self._save_avatar(user_id, avatar_file)
            update_data["avatar_url"] = avatar_url

        if not update_data:
            return profile

        updated = await self.profile_repo.update(user_id, **update_data)
        logger.info(f"Profile updated for user {user_id}: {list(update_data.keys())}")
        return updated

    # ── P03: Soft delete account ─────────────────────────
    async def soft_delete(self, user_id: UUID) -> Profile:
        """Soft delete the user's account."""
        profile = await self.get_profile(user_id)
        deleted = await self.profile_repo.soft_delete(user_id)
        logger.info(f"Profile soft-deleted for user {user_id}")
        return deleted

    # ── P04: Restore deleted account ─────────────────────
    async def restore_account(self, email: str) -> Profile:
        """Restore a soft-deleted account after OTP verification."""
        profile = await self.profile_repo.get_by_email(email)
        if not profile:
            raise NotFoundException("Profile")
        if not profile.is_deleted:
            raise ValidationException("Account is not deleted")

        restored = await self.profile_repo.restore(profile.id)
        logger.info(f"Profile restored for user {profile.id}")
        return restored

    # ── P05: Get subscription plan ───────────────────────
    async def get_plan(self, user_id: UUID) -> PlanResponse:
        """Get user's current subscription plan with limits."""
        profile = await self.get_profile(user_id)
        limits = PLAN_LIMITS.get(profile.plan, PLAN_LIMITS["free"])
        return PlanResponse(plan=profile.plan, limits=limits)

    # ── P06: Mark onboarding complete ────────────────────
    async def update_onboarding(
        self, user_id: UUID, completed: bool
    ) -> Profile:
        """Update the onboarding completion status."""
        profile = await self.get_profile(user_id)
        updated = await self.profile_repo.update(
            user_id, onboarding_completed=completed
        )
        logger.info(f"Onboarding updated for user {user_id}: {completed}")
        return updated

    # ── P07: Dashboard stats ─────────────────────────────
    async def get_stats(self, user_id: UUID) -> StatsResponse:
        """
        Get user dashboard statistics.
        In Phase 2, this will aggregate from prompts, templates, chains tables.
        For now, returns placeholder counts.
        """
        profile = await self.get_profile(user_id)
        return StatsResponse(
            total_prompts=0,
            total_templates=0,
            total_chains=0,
            total_optimizations=0,
            plan=profile.plan,
            member_since=profile.created_at,
        )

    # ── P08: Recent activity ─────────────────────────────
    async def get_activity(self, user_id: UUID) -> ActivityResponse:
        """
        Get recent user activity.
        In Phase 2, this will query an activity_log table.
        For now, returns the account creation event.
        """
        profile = await self.get_profile(user_id)
        activities = [
            ActivityItem(
                action="account_created",
                description="Account was created",
                timestamp=profile.created_at,
            )
        ]

        if profile.onboarding_completed:
            activities.append(
                ActivityItem(
                    action="onboarding_completed",
                    description="Onboarding was completed",
                    timestamp=profile.updated_at,
                )
            )

        return ActivityResponse(
            activities=activities,
            total_count=len(activities),
        )

    # ── Avatar upload helper ─────────────────────────────
    async def _save_avatar(self, user_id: UUID, file: UploadFile) -> str:
        """Validate and save avatar file. Returns the file URL path."""
        # Validate extension
        ext = Path(file.filename).suffix.lower() if file.filename else ""
        if ext not in ALLOWED_AVATAR_EXTENSIONS:
            raise ValidationException(
                f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_AVATAR_EXTENSIONS)}"
            )

        # Validate file size
        content = await file.read()
        if len(content) > MAX_AVATAR_FILE_SIZE:
            raise ValidationException(
                f"File too large. Maximum size: {MAX_AVATAR_FILE_SIZE // (1024 * 1024)} MB"
            )

        # Save file
        upload_dir = Path(settings.UPLOAD_DIR) / "avatars"
        upload_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{user_id}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = upload_dir / filename

        with open(file_path, "wb") as f:
            f.write(content)

        avatar_url = f"/uploads/avatars/{filename}"
        logger.info(f"Avatar saved: {avatar_url}")
        return avatar_url

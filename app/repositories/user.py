"""
Users module — Repository layer for profile CRUD operations.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, UserSettings


class ProfileRepository:
    """Database operations for the profiles table."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[Profile]:
        """Fetch profile by user ID."""
        result = await self.db.execute(
            select(Profile).where(Profile.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[Profile]:
        """Fetch profile by email."""
        result = await self.db.execute(
            select(Profile).where(Profile.email == email)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        email: str,
        display_name: Optional[str] = None,
    ) -> Profile:
        """Create a new profile."""
        profile = Profile(
            id=user_id,
            email=email,
            display_name=display_name,
        )
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def update(
        self,
        user_id: UUID,
        **kwargs,
    ) -> Optional[Profile]:
        """Update profile fields dynamically."""
        profile = await self.get_by_id(user_id)
        if not profile:
            return None

        for key, value in kwargs.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)

        profile.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def soft_delete(self, user_id: UUID) -> Optional[Profile]:
        """Soft delete — set deleted_at timestamp."""
        profile = await self.get_by_id(user_id)
        if not profile:
            return None

        profile.deleted_at = datetime.now(timezone.utc)
        profile.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def restore(self, user_id: UUID) -> Optional[Profile]:
        """Restore a soft-deleted profile — set deleted_at to None."""
        profile = await self.get_by_id(user_id)
        if not profile:
            return None

        profile.deleted_at = None
        profile.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile


class SettingsRepository:
    """Database operations for the user_settings table."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: UUID) -> Optional[UserSettings]:
        """Fetch settings for a user."""
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_defaults(self, user_id: UUID) -> UserSettings:
        """Create default settings for a new user."""
        settings = UserSettings(user_id=user_id)
        self.db.add(settings)
        await self.db.flush()
        await self.db.refresh(settings)
        return settings

    async def update(self, user_id: UUID, **kwargs) -> Optional[UserSettings]:
        """Update settings fields dynamically."""
        settings = await self.get_by_user_id(user_id)
        if not settings:
            return None

        for key, value in kwargs.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)

        settings.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(settings)
        return settings

    async def reset_to_defaults(self, user_id: UUID) -> Optional[UserSettings]:
        """Reset settings to factory defaults."""
        from app.core.constants import DEFAULT_SETTINGS

        settings = await self.get_by_user_id(user_id)
        if not settings:
            return None

        for key, value in DEFAULT_SETTINGS.items():
            setattr(settings, key, value)

        settings.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(settings)
        return settings

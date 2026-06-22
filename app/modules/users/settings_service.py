"""
Settings service — Business logic for user settings (Module B).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.logger import logger
from app.modules.users.models import UserSettings
from app.modules.users.repository import SettingsRepository


class SettingsService:
    """Business logic for user settings management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SettingsRepository(db)

    async def _get_or_raise(self, user_id: UUID) -> UserSettings:
        """Get settings or raise 404."""
        settings = await self.repo.get_by_user_id(user_id)
        if not settings:
            raise NotFoundException("User settings")
        return settings

    # ── S01: Get user settings ───────────────────────────
    async def get_settings(self, user_id: UUID) -> UserSettings:
        """Fetch all user settings."""
        return await self._get_or_raise(user_id)

    # ── S02: Update settings (bulk) ──────────────────────
    async def update_settings(self, user_id: UUID, **kwargs) -> UserSettings:
        """Update multiple settings at once."""
        await self._get_or_raise(user_id)
        # Filter out None values
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            return await self._get_or_raise(user_id)

        updated = await self.repo.update(user_id, **updates)
        logger.info(f"Settings updated for user {user_id}: {list(updates.keys())}")
        return updated

    # ── S03: Reset settings to defaults ──────────────────
    async def reset_settings(self, user_id: UUID) -> UserSettings:
        """Reset all settings to factory defaults."""
        await self._get_or_raise(user_id)
        reset = await self.repo.reset_to_defaults(user_id)
        logger.info(f"Settings reset to defaults for user {user_id}")
        return reset

    # ── S04: Update theme ────────────────────────────────
    async def update_theme(self, user_id: UUID, theme: str) -> UserSettings:
        """Change the UI theme."""
        return await self.update_settings(user_id, theme=theme)

    # ── S05: Change default AI model ─────────────────────
    async def update_default_model(self, user_id: UUID, model: str) -> UserSettings:
        """Change the default AI model."""
        return await self.update_settings(user_id, default_model=model)

    # ── S06: Change default prompt mode ──────────────────
    async def update_default_mode(self, user_id: UUID, mode: str) -> UserSettings:
        """Change the default prompt mode."""
        return await self.update_settings(user_id, default_mode=mode)

    # ── S07: Toggle intent detection ─────────────────────
    async def toggle_intent_detection(
        self, user_id: UUID, enabled: bool
    ) -> UserSettings:
        """Enable or disable automatic intent detection."""
        return await self.update_settings(user_id, auto_detect_intent=enabled)

    # ── S08: Toggle diff view ────────────────────────────
    async def toggle_diff_view(
        self, user_id: UUID, enabled: bool
    ) -> UserSettings:
        """Enable or disable diff view between original and optimized prompts."""
        return await self.update_settings(user_id, show_diff_by_default=enabled)

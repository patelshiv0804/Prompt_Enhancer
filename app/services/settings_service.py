from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user import SettingsRepository
from app.db.models import UserSettings

class SettingsService:
    def __init__(self, db: AsyncSession):
        self.repository = SettingsRepository(db)

    async def get_settings(self, user_id: UUID) -> UserSettings:
        settings = await self.repository.get_by_user_id(user_id)
        if not settings:
            settings = await self.repository.create_defaults(user_id)
        return settings

    async def update_settings(self, user_id: UUID, **kwargs) -> UserSettings:
        settings = await self.repository.update(user_id, **kwargs)
        if not settings:
            # Create default first
            await self.repository.create_defaults(user_id)
            settings = await self.repository.update(user_id, **kwargs)
        return settings

    async def reset_settings(self, user_id: UUID) -> UserSettings:
        return await self.repository.reset_to_defaults(user_id)

    async def update_theme(self, user_id: UUID, theme: str) -> UserSettings:
        return await self.update_settings(user_id, theme=theme)

    async def update_default_model(self, user_id: UUID, default_model: str) -> UserSettings:
        return await self.update_settings(user_id, default_model=default_model)

    async def update_default_mode(self, user_id: UUID, default_mode: str) -> UserSettings:
        return await self.update_settings(user_id, default_mode=default_mode)

    async def toggle_intent_detection(self, user_id: UUID, enabled: bool) -> UserSettings:
        return await self.update_settings(user_id, auto_detect_intent=enabled)

    async def toggle_diff_view(self, user_id: UUID, enabled: bool) -> UserSettings:
        return await self.update_settings(user_id, show_diff_by_default=enabled)

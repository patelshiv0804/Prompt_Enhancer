from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile
from app.repositories.profile import ProfileRepository
from app.schemas.profile import ProfileCreate
from app.services.exceptions import EntityNotFoundError


class ProfileService:
    def __init__(self, profile_repository: ProfileRepository) -> None:
        self.profile_repository = profile_repository

    async def create_profile(self, session: AsyncSession, payload: ProfileCreate) -> Profile:
        profile = Profile(**payload.model_dump(exclude_none=True))
        return await self.profile_repository.create(session, profile)

    async def list_profiles(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None,
    ) -> list[Profile]:
        return await self.profile_repository.list_profiles(
            session=session,
            limit=limit,
            offset=offset,
            is_active=is_active,
        )

    async def get_profile(self, session: AsyncSession, profile_id: str) -> Profile:
        profile = await self.profile_repository.get_by_id(session, profile_id)
        if profile is None:
            raise EntityNotFoundError("Profile not found.")
        return profile

    async def update_profile(self, session: AsyncSession, profile_id: str, values: dict) -> Profile:
        profile = await self.get_profile(session, profile_id)
        return await self.profile_repository.update(session, profile, values)

    async def get_current_profile(self, session: AsyncSession, profile_id: str) -> Profile:
        return await self.get_profile(session, profile_id)

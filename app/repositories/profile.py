from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.db.models import Profile
from .base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    def __init__(self) -> None:
        super().__init__(Profile)

    async def get_by_email(self, session: AsyncSession, email: str) -> Optional[Profile]:
        statement = select(Profile).where(Profile.email == email)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def deactivate(self, session: AsyncSession, profile: Profile) -> Profile:
        profile.is_active = False
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile

    async def list_profiles(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None,
    ) -> list[Profile]:
        statement = select(Profile)
        if is_active is not None:
            statement = statement.where(Profile.is_active == is_active)
        statement = statement.limit(limit).offset(offset)
        result = await session.execute(statement)
        return result.scalars().all()

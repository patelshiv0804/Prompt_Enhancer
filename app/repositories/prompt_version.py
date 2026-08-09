from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import PromptVersion
from .base import BaseRepository


class PromptVersionRepository(BaseRepository[PromptVersion]):
    def __init__(self) -> None:
        super().__init__(PromptVersion)

    async def get_versions_by_prompt(
        self,
        session: AsyncSession,
        prompt_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromptVersion]:
        statement = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.version_number.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(statement)
        return result.scalars().all()

    async def get_latest_version(
        self,
        session: AsyncSession,
        prompt_id: str,
    ) -> Optional[PromptVersion]:
        statement = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.version_number.desc())
            .limit(1)
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def count_versions(self, session: AsyncSession, prompt_id: str) -> int:
        statement = select(func.count()).select_from(PromptVersion).where(PromptVersion.prompt_id == prompt_id)
        result = await session.execute(statement)
        return result.scalar_one()

    async def delete_version(self, session: AsyncSession, version: PromptVersion) -> None:
        await super().delete(session, version)

    async def get_by_id(
        self,
        session: AsyncSession,
        id: str,
        include_prompt: bool = False,
    ) -> Optional[PromptVersion]:
        statement = select(PromptVersion).where(PromptVersion.id == id)
        if include_prompt:
            statement = statement.options(selectinload(PromptVersion.prompt))
        result = await session.execute(statement)
        return result.scalar_one_or_none()

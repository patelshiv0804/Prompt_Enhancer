from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Prompt
from .base import BaseRepository


class PromptRepository(BaseRepository[Prompt]):
    def __init__(self) -> None:
        super().__init__(Prompt)

    async def get_by_id(
        self,
        session: AsyncSession,
        id: str,
        include_template: bool = False,
        include_ai_model: bool = False,
        include_versions: bool = False,
    ) -> Optional[Prompt]:
        statement = select(Prompt).where(Prompt.id == id)
        if include_template:
            statement = statement.options(selectinload(Prompt.template))
        if include_ai_model:
            statement = statement.options(selectinload(Prompt.ai_model))
        if include_versions:
            statement = statement.options(selectinload(Prompt.versions))
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def list_prompts(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        ai_model_id: Optional[str] = None,
    ) -> list[Prompt]:
        statement = select(Prompt)
        if user_id is not None:
            statement = statement.where(Prompt.user_id == user_id)
        if template_id is not None:
            statement = statement.where(Prompt.template_id == template_id)
        if ai_model_id is not None:
            statement = statement.where(Prompt.ai_model_id == ai_model_id)
        statement = statement.limit(limit).offset(offset)
        result = await session.execute(statement)
        return result.scalars().all()

    async def get_prompts_by_user(
        self,
        session: AsyncSession,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Prompt]:
        return await self.list_prompts(session, user_id=user_id, limit=limit, offset=offset)

    async def get_prompts_by_template(
        self,
        session: AsyncSession,
        template_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Prompt]:
        return await self.list_prompts(session, template_id=template_id, limit=limit, offset=offset)

    async def get_prompts_by_model(
        self,
        session: AsyncSession,
        ai_model_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Prompt]:
        return await self.list_prompts(session, ai_model_id=ai_model_id, limit=limit, offset=offset)

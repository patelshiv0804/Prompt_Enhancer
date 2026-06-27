from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AIModel, Template
from .base import BaseRepository


class TemplateRepository(BaseRepository[Template]):
    def __init__(self) -> None:
        super().__init__(Template)

    async def get_by_id(
        self,
        session: AsyncSession,
        id: str,
        include_ai_model: bool = False,
    ) -> Optional[Template]:
        statement = select(Template).where(Template.id == id)
        if include_ai_model:
            statement = statement.options(selectinload(Template.ai_model))
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        mode: Optional[str] = None,
        category: Optional[str] = None,
        ai_model_id: Optional[str] = None,
        is_approved: Optional[bool] = None,
        only_active_models: bool = False,
    ) -> list[Template]:
        statement = select(Template)
        if mode is not None:
            statement = statement.where(Template.mode == mode)
        if category is not None:
            statement = statement.where(Template.category == category)
        if ai_model_id is not None:
            statement = statement.where(Template.ai_model_id == ai_model_id)
        if is_approved is not None:
            statement = statement.where(Template.is_approved == is_approved)
        if only_active_models:
            statement = statement.join(Template.ai_model).where(AIModel.is_active == True)
        statement = statement.limit(limit).offset(offset)
        result = await session.execute(statement)
        return result.scalars().all()

    async def delete(self, session: AsyncSession, instance: Template) -> None:
        await super().delete(session, instance)

    async def filter_by_ai_model(
        self,
        session: AsyncSession,
        ai_model_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Template]:
        statement = select(Template).where(Template.ai_model_id == ai_model_id).limit(limit).offset(offset)
        result = await session.execute(statement)
        return result.scalars().all()

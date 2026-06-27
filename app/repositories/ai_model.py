from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIModel
from .base import BaseRepository


class AIModelRepository(BaseRepository[AIModel]):
    def __init__(self) -> None:
        super().__init__(AIModel)

    async def get_by_provider(self, session: AsyncSession, provider: str) -> Optional[AIModel]:
        statement = select(AIModel).where(AIModel.provider == provider)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def activate(self, session: AsyncSession, model: AIModel) -> AIModel:
        model.is_active = True
        session.add(model)
        await session.commit()
        await session.refresh(model)
        return model

    async def deactivate(self, session: AsyncSession, model: AIModel) -> AIModel:
        model.is_active = False
        session.add(model)
        await session.commit()
        await session.refresh(model)
        return model

    async def list_active_models(
        self,
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AIModel]:
        statement = select(AIModel).where(AIModel.is_active == True).limit(limit).offset(offset)
        result = await session.execute(statement)
        return result.scalars().all()

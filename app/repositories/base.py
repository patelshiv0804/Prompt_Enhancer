from __future__ import annotations

from typing import Generic, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get_by_id(self, session: AsyncSession, id: str) -> Optional[ModelType]:
        statement = select(self.model).where(self.model.id == id)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def get_all(self, session: AsyncSession, limit: int = 100, offset: int = 0) -> list[ModelType]:
        statement = select(self.model).limit(limit).offset(offset)
        result = await session.execute(statement)
        return result.scalars().all()

    async def exists(self, session: AsyncSession, id: str) -> bool:
        statement = select(self.model.id).where(self.model.id == id)
        result = await session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def create(self, session: AsyncSession, instance: ModelType) -> ModelType:
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    async def update(self, session: AsyncSession, instance: ModelType, values: dict) -> ModelType:
        for field, value in values.items():
            setattr(instance, field, value)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    async def delete(self, session: AsyncSession, instance: ModelType) -> None:
        await session.delete(instance)
        await session.commit()

    async def count(self, session: AsyncSession) -> int:
        statement = select(func.count()).select_from(self.model)
        result = await session.execute(statement)
        return result.scalar_one()

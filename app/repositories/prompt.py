from __future__ import annotations

from typing import Optional, Any

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
        from app.core.config import settings
        from uuid import UUID
        p_id = UUID(id) if isinstance(id, str) else id
        statement = select(Prompt).where(Prompt.id == p_id)
        statement = statement.options(selectinload(Prompt.current_version))
        if settings.enable_soft_delete:
            statement = statement.where(Prompt.deleted_at == None)
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
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> list[Prompt]:
        from app.core.config import settings
        statement = (
            select(Prompt)
            .options(
                selectinload(Prompt.template),
                selectinload(Prompt.ai_model),
                selectinload(Prompt.current_version),
            )
        )
        if settings.enable_soft_delete:
            statement = statement.where(Prompt.deleted_at == None)
        if user_id is not None:
            from uuid import UUID
            try:
                uid = UUID(user_id) if isinstance(user_id, str) else user_id
                statement = statement.where(Prompt.user_id == uid)
            except ValueError:
                pass
        if template_id is not None:
            from uuid import UUID
            try:
                tid = UUID(template_id) if isinstance(template_id, str) else template_id
                statement = statement.where(Prompt.template_id == tid)
            except ValueError:
                pass
        if ai_model_id is not None:
            from uuid import UUID
            try:
                mid = UUID(ai_model_id) if isinstance(ai_model_id, str) else ai_model_id
                statement = statement.where(Prompt.ai_model_id == mid)
            except ValueError:
                pass

        # Apply sorting
        if sort_by:
            col = getattr(Prompt, sort_by, None)
            if col is not None:
                if sort_order == "desc":
                    statement = statement.order_by(col.desc())
                else:
                    statement = statement.order_by(col.asc())
        else:
            statement = statement.order_by(Prompt.created_at.desc())

        statement = statement.limit(limit).offset(offset)
        result = await session.execute(statement)
        return result.scalars().all()

    async def count_prompts(
        self,
        session: AsyncSession,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        ai_model_id: Optional[str] = None,
    ) -> int:
        from sqlalchemy import func
        from app.core.config import settings
        statement = select(func.count(Prompt.id))
        if settings.enable_soft_delete:
            statement = statement.where(Prompt.deleted_at == None)
        if user_id is not None:
            from uuid import UUID
            try:
                uid = UUID(user_id) if isinstance(user_id, str) else user_id
                statement = statement.where(Prompt.user_id == uid)
            except ValueError:
                pass
        if template_id is not None:
            from uuid import UUID
            try:
                tid = UUID(template_id) if isinstance(template_id, str) else template_id
                statement = statement.where(Prompt.template_id == tid)
            except ValueError:
                pass
        if ai_model_id is not None:
            from uuid import UUID
            try:
                mid = UUID(ai_model_id) if isinstance(ai_model_id, str) else ai_model_id
                statement = statement.where(Prompt.ai_model_id == mid)
            except ValueError:
                pass
        result = await session.execute(statement)
        return result.scalar() or 0

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

    async def search_prompts_with_vector(
        self,
        session: AsyncSession,
        vector: list[float],
        limit: int = 10,
        role: Optional[str] = None,
        mode: Optional[str] = None,
        template_id: Optional[str] = None,
        user_id: Optional[str] = None,
        date_from: Optional[Any] = None,
        date_to: Optional[Any] = None,
        include_versions: bool = False,
    ) -> list[tuple[Prompt, float]]:
        from sqlalchemy import func
        from app.db.models import Template
        from app.core.config import settings

        distance_col = Prompt.embedding.cosine_distance(vector).label("distance")
        statement = select(Prompt, distance_col).where(Prompt.embedding != None)
        if include_versions:
            statement = statement.options(selectinload(Prompt.versions))

        # Soft Delete Filter
        if settings.enable_soft_delete:
            statement = statement.where(Prompt.deleted_at == None)

        if user_id is not None:
            statement = statement.where(Prompt.user_id == user_id)
        if template_id is not None:
            statement = statement.where(Prompt.template_id == template_id)
        if date_from is not None:
            statement = statement.where(Prompt.created_at >= date_from)
        if date_to is not None:
            statement = statement.where(Prompt.created_at <= date_to)

        if role is not None or mode is not None:
            statement = statement.join(Prompt.template)
            if role is not None:
                statement = statement.where(func.lower(Template.role) == func.lower(role))
            if mode is not None:
                statement = statement.where(func.lower(Template.mode) == func.lower(mode))

        statement = statement.order_by(Prompt.embedding.cosine_distance(vector))
        statement = statement.limit(limit)

        result = await session.execute(statement)
        return [(r[0], 1.0 - r[1] if r[1] is not None else 0.0) for r in result.all()]

    async def find_duplicates(
        self,
        session: AsyncSession,
        vector: list[float],
        threshold: float,
        limit: int = 1,
    ) -> list[tuple[Prompt, float]]:
        res = await self.search_prompts_with_vector(session, vector, limit=limit)
        return [r for r in res if r[1] >= threshold]

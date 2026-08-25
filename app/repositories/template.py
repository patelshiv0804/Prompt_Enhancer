from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import redis_client
from app.core.config import settings
from app.db.models import AIModel, Template
from .base import BaseRepository


async def invalidate_role_mode_cache(*roles: str) -> None:
    """Drop the cached distinct role/mode lists.

    Call this after approving, editing, or removing a template so the new
    role/mode becomes visible immediately instead of waiting out
    ``redis_ttl_roles_modes``. Pass the affected role(s) to also clear their
    role-scoped mode lists. Safe to call when Redis is disabled.
    """
    keys = [
        redis_client.make_key(redis_client.NS_ROLES),
        redis_client.make_key(redis_client.NS_MODES),
    ]
    keys.extend(
        redis_client.make_key(redis_client.NS_ROLE_MODES, role.strip().lower())
        for role in roles
        if role and role.strip()
    )
    await redis_client.delete(*keys)


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
        role: Optional[str] = None,
        ai_model_id: Optional[str] = None,
        is_approved: Optional[bool] = None,
        is_featured: Optional[bool] = None,
        only_active_models: bool = False,
    ) -> list[Template]:
        statement = select(Template)
        if mode is not None:
            statement = statement.where(Template.mode == mode)
        if category is not None:
            statement = statement.where(Template.category == category)
        if role is not None:
            from sqlalchemy import func
            statement = statement.where(func.lower(Template.role) == func.lower(role))
        if ai_model_id is not None:
            statement = statement.where(Template.ai_model_id == ai_model_id)
        if is_approved is not None:
            statement = statement.where(Template.is_approved == is_approved)
        if is_featured is not None:
            statement = statement.where(Template.is_featured == is_featured)
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

    async def search_templates_with_vector(
        self,
        session: AsyncSession,
        vector: list[float],
        role: Optional[str] = None,
        mode: Optional[str] = None,
        is_approved: Optional[bool] = None,
        limit: int = 100,
    ) -> list[tuple[Template, float]]:
        from sqlalchemy import func
        distance_col = Template.embedding.cosine_distance(vector).label("distance")
        statement = select(Template, distance_col)
        if is_approved is not None:
            statement = statement.where(Template.is_approved == is_approved)
        if role is not None:
            statement = statement.where(func.lower(Template.role) == func.lower(role))
        if mode is not None:
            statement = statement.where(func.lower(Template.mode) == func.lower(mode))
            
        statement = statement.order_by(Template.embedding.cosine_distance(vector))
        statement = statement.limit(limit)
        result = await session.execute(statement)
        rows = result.all()
        return [(row[0], 1.0 - float(row[1])) for row in rows if row[1] is not None]

    # ── Distinct role / mode lists ────────────────────────────────────────
    # These three run on every /enhance request but describe near-static
    # reference data: the lists only change when a template is approved,
    # edited, or removed. Caching them removes three Neon round-trips from
    # every enhancement, and unlike prompt-keyed caches this one is shared by
    # every user, so it effectively always hits.
    #
    # A Redis miss — including Redis being unavailable — falls straight
    # through to the original query. Call invalidate_role_mode_cache() after
    # changing templates rather than waiting out the TTL.

    async def get_distinct_roles(self, session: AsyncSession) -> list[str]:
        key = redis_client.make_key(redis_client.NS_ROLES)
        cached = await redis_client.get_json(key)
        if isinstance(cached, list):
            return cached

        statement = select(Template.role).distinct().where(Template.is_approved == True)
        result = await session.execute(statement)
        roles = [r for r in result.scalars().all() if r]
        await redis_client.set_json(key, roles, ttl=settings.redis_ttl_roles_modes)
        return roles

    async def get_distinct_modes(self, session: AsyncSession) -> list[str]:
        key = redis_client.make_key(redis_client.NS_MODES)
        cached = await redis_client.get_json(key)
        if isinstance(cached, list):
            return cached

        statement = select(Template.mode).distinct().where(Template.is_approved == True)
        result = await session.execute(statement)
        modes = [m for m in result.scalars().all() if m]
        await redis_client.set_json(key, modes, ttl=settings.redis_ttl_roles_modes)
        return modes

    async def get_distinct_modes_for_role(self, session: AsyncSession, role: str) -> list[str]:
        # Keyed on the lowercased role because the query is case-insensitive —
        # "Marketer" and "marketer" must resolve to the same entry.
        key = redis_client.make_key(redis_client.NS_ROLE_MODES, (role or "").strip().lower())
        cached = await redis_client.get_json(key)
        if isinstance(cached, list):
            return cached

        from sqlalchemy import func
        statement = (
            select(Template.mode)
            .distinct()
            .where(Template.is_approved == True)
            .where(func.lower(Template.role) == func.lower(role))
        )
        result = await session.execute(statement)
        modes = [m for m in result.scalars().all() if m]
        await redis_client.set_json(key, modes, ttl=settings.redis_ttl_roles_modes)
        return modes

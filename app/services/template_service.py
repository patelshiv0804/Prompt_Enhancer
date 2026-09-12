from __future__ import annotations

import logging
from typing import Any, List, Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIModel, Template
from app.repositories.template import TemplateRepository, invalidate_role_mode_cache
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import TemplateNotFoundError

logger = logging.getLogger("promptiq.template_service")


def _build_embedding_text(
    role: Optional[str],
    mode: Optional[str],
    category: Optional[str],
    title: Optional[str],
    description: Optional[str],
    tags: Optional[List[str]],
) -> str:
    tags_str = ", ".join(tags) if tags else "None"
    return (
        f"Role:\n{role or 'N/A'}\n\n"
        f"Mode:\n{mode or 'N/A'}\n\n"
        f"Category:\n{category or 'N/A'}\n\n"
        f"Title:\n{title or 'N/A'}\n\n"
        f"Description:\n{description or 'N/A'}\n\n"
        f"Tags:\n{tags_str}"
    )


class TemplateService:
    def __init__(
        self,
        repository: TemplateRepository,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service or EmbeddingService()

    async def create_template(
        self,
        session: AsyncSession,
        template_data: TemplateCreate,
        user_id: Optional[UUID] = None,
    ) -> Template:
        data = template_data.model_dump(exclude_none=True)

        # Resolve AI model if not provided
        if not data.get("ai_model_id"):
            result = await session.execute(
                select(AIModel.id).where(AIModel.is_active == True).limit(1)
            )
            model_id = result.scalar_one_or_none()
            if not model_id:
                fallback_res = await session.execute(select(AIModel.id).limit(1))
                model_id = fallback_res.scalar_one_or_none()
            data["ai_model_id"] = model_id

        if user_id is not None:
            data["user_id"] = user_id
            data["is_approved"] = True
            data["is_featured"] = False

        # Generate embedding vector
        embedding_text = _build_embedding_text(
            role=data.get("role"),
            mode=data.get("mode"),
            category=data.get("category"),
            title=data.get("title"),
            description=data.get("description"),
            tags=data.get("tags") or [],
        )
        try:
            vector = await self.embedding_service.generate_for_prompt_async(embedding_text)
            data["embedding"] = vector
        except Exception as exc:
            logger.warning("Could not generate vector embedding for template: %s", exc)

        template = Template(**data)
        created = await self.repository.create(session, template)

        if created.role:
            await invalidate_role_mode_cache(created.role)

        return created

    async def get_template(
        self,
        session: AsyncSession,
        template_id: Union[str, UUID],
    ) -> Template:
        template = await self.repository.get_by_id(session, template_id)
        if template is None:
            raise TemplateNotFoundError("Template not found.")
        return template

    async def get_template_for_user(
        self,
        session: AsyncSession,
        template_id: Union[str, UUID],
        user_id: Optional[UUID] = None,
    ) -> Template:
        template = await self.repository.get_by_id_and_user(
            session=session,
            id=template_id,
            user_id=user_id,
        )
        if template is None:
            raise TemplateNotFoundError("Template not found.")
        return template

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
        user_id: Optional[UUID] = None,
        mine: bool = False,
    ) -> list[Template]:
        return await self.repository.list_templates(
            session=session,
            limit=limit,
            offset=offset,
            mode=mode,
            category=category,
            role=role,
            ai_model_id=ai_model_id,
            is_approved=is_approved,
            is_featured=is_featured,
            only_active_models=only_active_models,
            user_id=user_id,
            mine=mine,
        )

    async def update_template(
        self,
        session: AsyncSession,
        template_id: Union[str, UUID],
        values: dict,
    ) -> Template:
        template = await self.get_template(session, template_id)
        return await self.repository.update(session, template, values)

    async def update_template_for_user(
        self,
        session: AsyncSession,
        template_id: Union[str, UUID],
        user_id: UUID,
        values: dict,
    ) -> Template:
        template = await self.repository.get_by_id(session, template_id)
        if template is None or template.user_id != user_id:
            raise TemplateNotFoundError("Template not found.")

        # Re-compute embedding if metadata changed
        if any(k in values for k in ("role", "mode", "category", "title", "description", "tags")):
            new_role = values.get("role", template.role)
            new_mode = values.get("mode", template.mode)
            new_cat = values.get("category", template.category)
            new_title = values.get("title", template.title)
            new_desc = values.get("description", template.description)
            new_tags = values.get("tags", template.tags)
            text = _build_embedding_text(new_role, new_mode, new_cat, new_title, new_desc, new_tags)
            try:
                values["embedding"] = await self.embedding_service.generate_for_prompt_async(text)
            except Exception as exc:
                logger.warning("Could not regenerate embedding during update: %s", exc)

        updated = await self.repository.update(session, template, values)
        if updated.role:
            await invalidate_role_mode_cache(updated.role)
        return updated

    async def delete_template(
        self,
        session: AsyncSession,
        template_id: Union[str, UUID],
    ) -> None:
        template = await self.get_template(session, template_id)
        await self.repository.delete(session, template)

    async def delete_template_for_user(
        self,
        session: AsyncSession,
        template_id: Union[str, UUID],
        user_id: UUID,
    ) -> None:
        template = await self.repository.get_by_id(session, template_id)
        if template is None or template.user_id != user_id:
            raise TemplateNotFoundError("Template not found.")

        role_to_clear = template.role
        await self.repository.delete(session, template)
        if role_to_clear:
            await invalidate_role_mode_cache(role_to_clear)

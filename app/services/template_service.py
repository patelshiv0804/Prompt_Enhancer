from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template
from app.repositories.template import TemplateRepository
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.services.exceptions import TemplateNotFoundError


class TemplateService:
    def __init__(self, repository: TemplateRepository) -> None:
        self.repository = repository

    async def create_template(self, session: AsyncSession, template_data: TemplateCreate) -> Template:
        template = Template(**template_data.model_dump(exclude_none=True))
        return await self.repository.create(session, template)

    async def get_template(self, session: AsyncSession, template_id: str) -> Template:
        template = await self.repository.get_by_id(session, template_id)
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
        )

    async def update_template(self, session: AsyncSession, template_id: str, values: dict) -> Template:
        template = await self.get_template(session, template_id)
        return await self.repository.update(session, template, values)

    async def delete_template(self, session: AsyncSession, template_id: str) -> None:
        template = await self.get_template(session, template_id)
        await self.repository.delete(session, template)

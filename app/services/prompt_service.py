from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt
from app.repositories.prompt import PromptRepository
from app.schemas.prompt import PromptCreate, PromptUpdate
from app.services.exceptions import PromptNotFoundError


class PromptService:
    def __init__(self, repository: PromptRepository) -> None:
        self.repository = repository

    async def create_prompt(self, session: AsyncSession, user_id: str, prompt_data: PromptCreate) -> Prompt:
        payload = prompt_data.model_dump(exclude_none=True)
        prompt = Prompt(user_id=user_id, **payload)
        return await self.repository.create(session, prompt)

    async def get_prompt(
        self,
        session: AsyncSession,
        prompt_id: str,
        include_template: bool = False,
        include_ai_model: bool = False,
        include_versions: bool = False,
    ) -> Prompt:
        prompt = await self.repository.get_by_id(
            session,
            prompt_id,
            include_template=include_template,
            include_ai_model=include_ai_model,
            include_versions=include_versions,
        )
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")
        return prompt

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
        return await self.repository.list_prompts(
            session=session,
            limit=limit,
            offset=offset,
            user_id=user_id,
            template_id=template_id,
            ai_model_id=ai_model_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def count_prompts(
        self,
        session: AsyncSession,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        ai_model_id: Optional[str] = None,
    ) -> int:
        return await self.repository.count_prompts(
            session=session,
            user_id=user_id,
            template_id=template_id,
            ai_model_id=ai_model_id,
        )

    async def update_prompt(self, session: AsyncSession, prompt_id: str, values: dict) -> Prompt:
        prompt = await self.get_prompt(session, prompt_id)
        return await self.repository.update(session, prompt, values)

    async def delete_prompt(self, session: AsyncSession, prompt_id: str) -> None:
        prompt = await self.get_prompt(session, prompt_id)
        # Vault deletion is permanent. PostgreSQL cascades the delete to the
        # prompt's versions through prompt_versions.prompt_id.
        await self.repository.delete(session, prompt)

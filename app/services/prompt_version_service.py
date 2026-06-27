from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt, PromptVersion
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.services.exceptions import PromptPersistenceError, VersionNotFoundError

logger = logging.getLogger("promptiq.prompt_version")


class PromptVersionService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        prompt_version_repository: PromptVersionRepository,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.prompt_version_repository = prompt_version_repository

    async def create_version(
        self,
        session: AsyncSession,
        prompt: Prompt,
        content: str,
        version_type: str,
    ) -> PromptVersion:
        version_number = 1
        existing_versions = await self.prompt_version_repository.get_versions_by_prompt(
            session=session,
            prompt_id=str(prompt.id),
            limit=1,
            offset=0,
        )
        if existing_versions:
            version_number = existing_versions[0].version_number + 1

        version = PromptVersion(
            prompt_id=prompt.id,
            version_number=version_number,
            version_type=version_type,
            content=content,
        )
        try:
            await self.prompt_version_repository.create(session, version)
            prompt.current_version_id = version.id
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()
        except Exception as exc:
            logger.exception("Failed to create prompt version")
            raise PromptPersistenceError("Failed to create prompt version.") from exc

        logger.info("Created prompt version id=%s version_number=%s", version.id, version.version_number)
        return version

    async def create_version_for_prompt(
        self,
        session: AsyncSession,
        prompt_id: str,
        content: str,
        version_type: str,
    ) -> PromptVersion:
        prompt = await self.get_prompt(session, prompt_id)
        return await self.create_version(session, prompt, content, version_type)

    async def list_versions(
        self,
        session: AsyncSession,
        prompt_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromptVersion]:
        if prompt_id:
            return await self.prompt_version_repository.get_versions_by_prompt(
                session=session,
                prompt_id=prompt_id,
                limit=limit,
                offset=offset,
            )

        return await self.prompt_version_repository.get_all(session, limit=limit, offset=offset)

    async def get_version(self, session: AsyncSession, version_id: str) -> PromptVersion:
        version = await self.prompt_version_repository.get_by_id(session, version_id, include_prompt=True)
        if version is None:
            raise VersionNotFoundError("Prompt version not found.")
        return version

    async def get_prompt(self, session: AsyncSession, prompt_id: str) -> Prompt:
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")
        return prompt

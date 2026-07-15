from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PromptVersion
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.services.exceptions import PromptNotFoundError, VersionNotFoundError

logger = logging.getLogger("promptiq.prompt_history")


class PromptHistoryService:
    """
    PromptHistoryService retrieves version history, active version,
    and specific versions of prompts.
    """

    def __init__(
        self,
        prompt_repository: PromptRepository,
        prompt_version_repository: PromptVersionRepository,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.prompt_version_repository = prompt_version_repository

    async def get_history(
        self,
        session: AsyncSession,
        prompt_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromptVersion]:
        logger.info("Retrieving version history for prompt_id=%s", prompt_id)
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        return await self.prompt_version_repository.get_versions_by_prompt(
            session=session,
            prompt_id=prompt_id,
            limit=limit,
            offset=offset,
        )

    async def get_active_version(
        self,
        session: AsyncSession,
        prompt_id: str,
    ) -> PromptVersion:
        logger.info("Retrieving active version for prompt_id=%s", prompt_id)
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        if prompt.current_version_id is None:
            raise VersionNotFoundError("Prompt has no active version.")

        version = await self.prompt_version_repository.get_by_id(session, str(prompt.current_version_id))
        if version is None:
            raise VersionNotFoundError("Active version reference not found in database.")
        return version

    async def get_specific_version(
        self,
        session: AsyncSession,
        prompt_id: str,
        version_number: int,
    ) -> PromptVersion:
        logger.info("Retrieving version_number=%d for prompt_id=%s", version_number, prompt_id)
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        # Find matching version sequence
        versions = await self.prompt_version_repository.get_versions_by_prompt(
            session=session,
            prompt_id=prompt_id,
            limit=100,
        )
        for v in versions:
            if v.version_number == version_number:
                return v

        raise VersionNotFoundError(f"Version number {version_number} not found for prompt.")

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.services.exceptions import (
    ActiveVersionDeletionError,
    PromptNotFoundError,
    VersionNotFoundError,
    VersionRestoreError,
)
from app.services.prompt_embedding_service import PromptEmbeddingService

logger = logging.getLogger("promptiq.prompt_restore")


class PromptRestoreService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        prompt_version_repository: PromptVersionRepository,
        prompt_embedding_service: PromptEmbeddingService,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.prompt_version_repository = prompt_version_repository
        self.prompt_embedding_service = prompt_embedding_service

    async def restore_version(
        self,
        session: AsyncSession,
        prompt_id: str,
        version_id: str,
    ) -> dict:
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        version = await self.prompt_version_repository.get_by_id(session, version_id)
        if version is None or str(version.prompt_id) != prompt_id:
            raise VersionNotFoundError("Version not found for prompt.")

        if prompt.current_version_id is not None and str(prompt.current_version_id) == version_id:
            logger.info("Prompt id=%s is already at version_id=%s, returning idempotently", prompt_id, version_id)
            return {
                "prompt_id": prompt_id,
                "restored_version_id": version_id,
            }

        try:
            prompt.current_version_id = version.id
            await self.prompt_repository.update(session, prompt, {})
            await self.prompt_embedding_service.update_prompt_embedding(session, prompt_id)
            await session.flush()
        except Exception as exc:
            logger.exception("Failed to restore prompt version")
            raise VersionRestoreError("Failed to restore prompt version.") from exc

        logger.info("Restored prompt id=%s to version_id=%s", prompt_id, version_id)
        return {
            "prompt_id": prompt_id,
            "restored_version_id": version_id,
            "current_version_id": str(prompt.current_version_id),
        }

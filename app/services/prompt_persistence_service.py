from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt
from app.repositories.prompt import PromptRepository
from app.services.embedding_service import EmbeddingService
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.services.prompt_version_service import PromptVersionService
from app.services.exceptions import PromptPersistenceError

logger = logging.getLogger("promptiq.prompt_persistence")


class PromptPersistenceService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        prompt_version_service: PromptVersionService,
        prompt_embedding_service: PromptEmbeddingService,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.prompt_version_service = prompt_version_service
        self.prompt_embedding_service = prompt_embedding_service

    async def create_prompt_with_version(
        self,
        session: AsyncSession,
        prompt: Prompt,
        content: str,
        version_type: str,
    ) -> Prompt:
        try:
            prompt = await self.prompt_repository.create(session, prompt)
            await self.prompt_version_service.create_version(session, prompt, content, version_type)
            await self.prompt_embedding_service.update_prompt_embedding(session, str(prompt.id))
            await session.flush()
        except Exception as exc:
            logger.exception("Failed to persist prompt with version")
            raise PromptPersistenceError("Failed to persist prompt with version.") from exc

        logger.info("Persisted prompt id=%s with new version", prompt.id)
        return prompt

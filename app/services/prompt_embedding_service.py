from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PromptVersion
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import EmbeddingGenerationError, PromptNotFoundError

logger = logging.getLogger("promptiq.prompt_embedding")


class PromptEmbeddingService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        prompt_version_repository: PromptVersionRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.prompt_version_repository = prompt_version_repository
        self.embedding_service = embedding_service

    async def update_prompt_embedding(self, session: AsyncSession, prompt_id: str):
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        if prompt.current_version_id is None:
            raise EmbeddingGenerationError("Prompt has no active version.")

        version = await self.prompt_version_repository.get_by_id(session, str(prompt.current_version_id))
        if version is None:
            raise EmbeddingGenerationError("Active prompt version not found.")

        try:
            embedding = self.embedding_service.generate_for_prompt(version.content)
            prompt.embedding = embedding
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()
        except Exception as exc:
            logger.exception("Failed to generate prompt embedding")
            raise EmbeddingGenerationError("Failed to generate prompt embedding.") from exc

        logger.info("Updated prompt embedding for prompt_id=%s", prompt_id)
        return prompt

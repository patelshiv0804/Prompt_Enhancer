from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import EmbeddingGenerationException, PromptNotFoundError

logger = logging.getLogger("promptiq.prompt_embedding")


class PromptEmbeddingService:
    """
    PromptEmbeddingService builds the unified semantic source text and generates
    the 384-dimensional embedding vector to store in prompts.embedding.
    """

    def __init__(
        self,
        prompt_repository: PromptRepository,
        prompt_version_repository: PromptVersionRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.prompt_version_repository = prompt_version_repository
        self.embedding_service = embedding_service

    async def update_prompt_embedding(self, session: AsyncSession, prompt_id: str) -> None:
        logger.info("Generating prompt embedding for prompt_id=%s", prompt_id)
        prompt = await self.prompt_repository.get_by_id(session, prompt_id, include_template=True)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        if prompt.current_version_id is None:
            raise EmbeddingGenerationException("Prompt has no active version.")

        version = await self.prompt_version_repository.get_by_id(session, str(prompt.current_version_id))
        if version is None:
            raise EmbeddingGenerationException("Active prompt version not found in database.")

        try:
            # Build unified semantic representation
            original = prompt.original_prompt or ""
            enhanced = version.content or ""
            role = prompt.template.role if (prompt.template and prompt.template.role) else "N/A"
            mode = prompt.template.mode if (prompt.template and prompt.template.mode) else "N/A"
            title = prompt.template.title if (prompt.template and prompt.template.title) else "N/A"

            embedding_source = f"{original} {enhanced} {role} {mode} {title}"
            logger.debug("Generating embedding from text: '%s'", embedding_source)

            # Generate 384-dimensional embedding
            embedding = await self.embedding_service.generate_for_prompt_async(embedding_source)
            
            # Save directly to prompts.embedding
            prompt.embedding = embedding
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()
            logger.info("Successfully updated prompt embedding for prompt_id=%s", prompt_id)
        except Exception as exc:
            logger.exception("Embedding generation failed")
            raise EmbeddingGenerationException("Failed to generate prompt embedding.") from exc

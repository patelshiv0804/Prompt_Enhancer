from __future__ import annotations

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt
from app.repositories.prompt import PromptRepository
from app.services.prompt_version_service import PromptVersionService
from app.services.prompt_embedding_service import PromptEmbeddingService
from app.services.exceptions import (
    PromptPersistenceException,
    DatabaseTransactionException,
    PromptNotFoundError,
)

logger = logging.getLogger("promptiq.prompt_persistence")


class PromptPersistenceService:
    """
    PromptPersistenceService manages transaction blocks for creating, updating,
    and committing prompt and version records synchronously.
    """

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
        user_id: str,
        original_prompt: str,
        enhanced_prompt: str,
        template_id: Optional[str] = None,
        ai_model_id: Optional[str] = None,
        title: Optional[str] = None,
        total_score: Optional[float] = None,
        grade: Optional[str] = None,
    ) -> Prompt:
        logger.info("Creating new prompt in database")
        try:
            # We wrap everything in a transaction rollback catch block
            prompt = Prompt(
                user_id=user_id,
                original_prompt=original_prompt,
                template_id=template_id,
                ai_model_id=ai_model_id,
                title=title,
                total_score=total_score,
                grade=grade,
            )
            prompt_id = prompt.id
            prompt = await self.prompt_repository.create(session, prompt)
            await session.flush()

            # Create Version 1
            await self.prompt_version_service.create_version(
                session=session,
                prompt=prompt,
                content=enhanced_prompt,
                version_type="initial",
            )

            # Generate and save prompt embedding
            await self.prompt_embedding_service.update_prompt_embedding(session, str(prompt_id))
            await session.flush()

            logger.info("Successfully created prompt id=%s and version 1", prompt_id)
            return prompt
        except Exception as exc:
            logger.exception("Failed to persist prompt with version. Rolling back transaction.")
            await session.rollback()
            raise DatabaseTransactionException("Failed to create prompt and version in transaction.") from exc

    async def update_prompt_with_new_version(
        self,
        session: AsyncSession,
        prompt_id: str,
        new_enhanced_prompt: str,
        change_summary: Optional[str] = None,
    ) -> Prompt:
        logger.info("Updating prompt_id=%s with new version", prompt_id)
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        try:
            # Create new sequential version
            await self.prompt_version_service.create_version(
                session=session,
                prompt=prompt,
                content=new_enhanced_prompt,
                version_type="enhancement",
                change_summary=change_summary,
            )

            # Generate new embedding
            await self.prompt_embedding_service.update_prompt_embedding(session, prompt_id)
            await session.flush()

            logger.info("Successfully added new version to prompt_id=%s", prompt_id)
            return prompt
        except Exception as exc:
            logger.exception("Failed to update prompt version. Rolling back transaction.")
            await session.rollback()
            raise DatabaseTransactionException("Failed to update prompt version in transaction.") from exc

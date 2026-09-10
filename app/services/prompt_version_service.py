from __future__ import annotations

import logging
import re
from typing import Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Prompt, PromptVersion
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.services.exceptions import (
    PromptVersionException,
    PromptNotFoundError,
    VersionNotFoundError,
    VersionDeleteException,
    PromptRestoreException,
)
from app.services.prompt_embedding_service import PromptEmbeddingService

logger = logging.getLogger("promptiq.prompt_version")


def _to_uuid(val: Any) -> Optional[UUID]:
    if not val:
        return None
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return None


class PromptVersionService:
    """
    PromptVersionService manages prompt versions, sequence verification,
    version restoration, and deletion constraints.
    """

    def __init__(
        self,
        prompt_repository: PromptRepository,
        prompt_version_repository: PromptVersionRepository,
        prompt_embedding_service: Optional[PromptEmbeddingService] = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.prompt_version_repository = prompt_version_repository
        self.prompt_embedding_service = prompt_embedding_service

    async def create_version(
        self,
        session: AsyncSession,
        prompt: Prompt,
        content: str,
        version_type: str,
        change_summary: Optional[str] = None,
        old_analysis: Optional[dict] = None,
        new_analysis: Optional[dict] = None,
        tool_recommendations: Optional[dict] = None,
        template_id: Optional[str] = None,
    ) -> PromptVersion:
        logger.info("Creating version for prompt_id=%s", prompt.id)
        content = self._clean_version_content(content)
        if not content:
            raise PromptVersionException("Version content cannot be empty.")

        # Determine next sequential version number
        version_number = 1
        latest_version = await self.prompt_version_repository.get_latest_version(
            session=session,
            prompt_id=str(prompt.id),
        )
        if latest_version:
            # Validate sequential number and prevent duplicates/skips
            version_number = latest_version.version_number + 1

        version = PromptVersion(
            prompt_id=prompt.id,
            version_number=version_number,
            version_type=version_type,
            content=content,
            change_summary=change_summary,
            old_analysis=old_analysis,
            new_analysis=new_analysis,
            tool_recommendations=tool_recommendations,
            template_id=_to_uuid(template_id),
        )

        version_id = version.id
        version_num = version.version_number

        try:
            version = await self.prompt_version_repository.create(session, version)
            await session.flush()

            # Update current_version_id on the prompt model
            prompt.current_version_id = version_id
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()
        except Exception as exc:
            logger.exception("Failed to persist prompt version")
            raise PromptVersionException("Failed to persist prompt version.") from exc

        logger.info("Successfully created version %d (ID: %s)", version_num, version_id)
        return version

    @staticmethod
    def _clean_version_content(content: str) -> str:
        """Persist prompt text, not Markdown control characters from an LLM response."""
        cleaned = content.strip()
        # Preserve the words while removing inline formatting tokens such as
        # **Important** and `example`, which otherwise appear as raw symbols in
        # history views and search results.
        cleaned = re.sub(r"\\([*_`#-])", r"\1", cleaned)
        cleaned = re.sub(r"(?<!\*)\*\*([^*]+?)\*\*(?!\*)", r"\1", cleaned)
        cleaned = re.sub(r"(?<!_)__([^_]+?)__(?!_)", r"\1", cleaned)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\1", cleaned)
        cleaned = re.sub(r"(?<!_)_([^_\n]+?)_(?!_)", r"\1", cleaned)
        cleaned = re.sub(r"(?m)^\s*#{1,6}\s*", "", cleaned)
        cleaned = re.sub(r"(?m)^\s*(?:---+|___+)\s*$", "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


    async def restore_version(
        self,
        session: AsyncSession,
        prompt_id: str,
        version_id: str,
    ) -> PromptVersion:
        logger.info("Restoring prompt_id=%s to version_id=%s", prompt_id, version_id)
        if not self.prompt_embedding_service:
            raise PromptRestoreException("PromptEmbeddingService dependency is missing.")

        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        version = await self.prompt_version_repository.get_by_id(session, version_id)
        if version is None or str(version.prompt_id) != prompt_id:
            raise VersionNotFoundError("Version not found for this prompt.")

        # If already active version, return it idempotently without error
        if prompt.current_version_id is not None and str(prompt.current_version_id) == version_id:
            logger.info("Version ID %s is already active for prompt_id=%s, returning idempotently.", version_id, prompt_id)
            return version

        try:
            # Shift the active version reference without duplicating records
            prompt.current_version_id = version.id
            await self.prompt_repository.update(session, prompt, {})
            await session.flush()

            # Regenerate prompt embedding from the restored version content
            await self.prompt_embedding_service.update_prompt_embedding(session, prompt_id)
            await session.flush()
        except Exception as exc:
            logger.exception("Failed to restore prompt version")
            raise PromptRestoreException("Failed to restore prompt version.") from exc

        logger.info("Successfully restored active version reference to ID: %s", version_id)
        return version

    async def list_versions(
        self,
        session: AsyncSession,
        prompt_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PromptVersion]:
        prompt = await self.prompt_repository.get_by_id(session, prompt_id)
        if prompt is None:
            raise PromptNotFoundError("Prompt not found.")

        # Optional version limit enforcement
        max_limit = settings.max_version_history if hasattr(settings, "max_version_history") else limit
        final_limit = min(limit, max_limit) if max_limit is not None else limit

        return await self.prompt_version_repository.get_versions_by_prompt(
            session=session,
            prompt_id=prompt_id,
            limit=final_limit,
            offset=offset,
        )

    async def delete_version(self, session: AsyncSession, version_id: str) -> None:
        logger.info("Attempting to delete version_id=%s", version_id)
        version = await self.prompt_version_repository.get_by_id(session, version_id, include_prompt=True)
        if version is None:
            raise VersionNotFoundError("Prompt version not found.")

        prompt = version.prompt
        if prompt and prompt.current_version_id == version.id:
            raise VersionDeleteException("Cannot delete the active version of a prompt.")

        try:
            await self.prompt_version_repository.delete(session, version)
            await session.flush()
            logger.info("Successfully deleted version_id=%s", version_id)
        except Exception as exc:
            logger.exception("Deletion failed for version_id=%s", version_id)
            raise PromptVersionException("Failed to delete prompt version.") from exc

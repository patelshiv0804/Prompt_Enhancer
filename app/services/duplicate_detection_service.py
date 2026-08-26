from __future__ import annotations

import logging
import time
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prompt import PromptRepository
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import (
    DuplicateDetectionException,
    EmbeddingGenerationException,
)

logger = logging.getLogger("promptiq.services.duplicate_detection")


class DuplicateDetectionService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.embedding_service = embedding_service or EmbeddingService()

    async def detect_duplicate(
        self,
        session: AsyncSession,
        prompt_text: str,
        threshold: Optional[float] = None,
    ) -> dict[str, Any]:
        logger.info("Running duplicate detection scan for prompt")
        from app.core.config import settings
        dup_threshold = threshold if threshold is not None else settings.duplicate_threshold

        start_time = time.perf_counter()
        try:
            vector = await self.embedding_service.generate_for_prompt_async(prompt_text)
        except Exception as exc:
            logger.exception("Failed to generate embedding for duplicate detection scan")
            raise EmbeddingGenerationException("Failed to generate prompt embedding.") from exc
        emb_time = time.perf_counter() - start_time

        db_start = time.perf_counter()
        try:
            duplicates = await self.prompt_repository.find_duplicates(
                session=session,
                vector=vector,
                threshold=dup_threshold,
                limit=1,
            )
        except Exception as exc:
            logger.exception("Database duplicate scan failed")
            raise DuplicateDetectionException("Database failure during duplicate detection lookup.") from exc
        db_time = time.perf_counter() - db_start

        logger.info(
            "Duplicate scan completed. Found duplicate: %s. EmbTime: %.4fs, DBTime: %.4fs",
            "YES" if duplicates else "NO",
            emb_time,
            db_time,
        )

        if duplicates:
            match, score = duplicates[0]
            return {
                "is_duplicate": True,
                "similarity": score,
                "duplicate_prompt": {
                    "id": str(match.id),
                    "original_prompt": match.original_prompt,
                    "title": match.title,
                },
            }

        return {
            "is_duplicate": False,
            "similarity": None,
            "duplicate_prompt": None,
        }

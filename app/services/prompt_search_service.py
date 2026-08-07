from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prompt import PromptRepository
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import (
    PromptSearchException,
    EmbeddingGenerationException,
)

logger = logging.getLogger("promptiq.services.prompt_search")


class PromptSearchService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.embedding_service = embedding_service or EmbeddingService()

    async def search(
        self,
        session: AsyncSession,
        prompt_text: str,
        limit: Optional[int] = None,
        role: Optional[str] = None,
        mode: Optional[str] = None,
        template_id: Optional[str] = None,
        user_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        logger.info("Performing semantic prompt search on query: '%s'", prompt_text)
        from app.core.config import settings
        search_limit = limit if limit is not None else settings.prompt_top_k

        start_time = time.perf_counter()
        try:
            vector = self.embedding_service.generate_for_prompt(prompt_text)
        except Exception as exc:
            logger.exception("Failed to generate embedding for semantic search query")
            raise EmbeddingGenerationException("Failed to generate prompt embedding.") from exc
        emb_time = time.perf_counter() - start_time

        db_start = time.perf_counter()
        try:
            results = await self.prompt_repository.search_prompts_with_vector(
                session=session,
                vector=vector,
                limit=search_limit,
                role=role,
                mode=mode,
                template_id=template_id,
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as exc:
            logger.exception("Database search execution failed")
            raise PromptSearchException("Database lookup failed during semantic search.") from exc
        db_time = time.perf_counter() - db_start

        logger.info(
            "Semantic prompt search completed. Results count: %d. EmbTime: %.4fs, DBTime: %.4fs",
            len(results),
            emb_time,
            db_time,
        )

        output = []
        for prompt, sim_score in results:
            output.append({
                "prompt_id": str(prompt.id),
                "title": prompt.title,
                "original_prompt": prompt.original_prompt,
                "similarity_score": sim_score,
                "old_analysis": prompt.old_analysis,
                "new_analysis": prompt.new_analysis,
                "grade": prompt.grade,
                "created_at": prompt.created_at,
            })
        return output

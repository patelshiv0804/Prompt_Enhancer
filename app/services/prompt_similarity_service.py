from __future__ import annotations

import logging
import numpy as np
import time
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prompt import PromptRepository
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import (
    SemanticSearchException,
    EmbeddingGenerationException,
)

logger = logging.getLogger("promptiq.services.prompt_similarity")


class PromptSimilarityService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.embedding_service = embedding_service or EmbeddingService()

    async def calculate_similarity(
        self,
        session: AsyncSession,
        prompt1: str,
        prompt2: str,
    ) -> float:
        logger.info("Calculating similarity between two raw prompts")
        try:
            emb1 = self.embedding_service.generate_for_prompt(prompt1)
            emb2 = self.embedding_service.generate_for_prompt(prompt2)
            u = np.array(emb1)
            v = np.array(emb2)
            # Dot product since embeddings are unit L2 normalized
            similarity = float(np.dot(u, v))
            return similarity
        except Exception as exc:
            logger.exception("Failed to calculate prompt similarity")
            raise SemanticSearchException("Failed to calculate prompt similarity.") from exc

    async def search_similar_prompts(
        self,
        session: AsyncSession,
        prompt_text: str,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        logger.info("Searching for prompts semantically similar to: '%s'", prompt_text)
        from app.core.config import settings
        search_limit = limit if limit is not None else settings.prompt_top_k

        start_time = time.perf_counter()
        try:
            query_vector = self.embedding_service.generate_for_prompt(prompt_text)
        except Exception as exc:
            logger.exception("Failed to generate query embedding for similar prompt search")
            raise EmbeddingGenerationException("Failed to generate query embedding.") from exc
        emb_time = time.perf_counter() - start_time

        db_start = time.perf_counter()
        try:
            results = await self.prompt_repository.search_prompts_with_vector(
                session=session,
                vector=query_vector,
                limit=search_limit,
            )
        except Exception as exc:
            logger.exception("Database search failed in PromptSimilarityService")
            raise SemanticSearchException("Database lookup failed during similar prompt search.") from exc
        db_time = time.perf_counter() - db_start

        logger.info(
            "Similar prompts search complete. Found %d matches. EmbTime: %.4fs, DBTime: %.4fs",
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
                "total_score": prompt.total_score,
                "grade": prompt.grade,
                "created_at": prompt.created_at,
            })
        return output

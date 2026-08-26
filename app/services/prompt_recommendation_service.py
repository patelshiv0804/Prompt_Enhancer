from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prompt import PromptRepository
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import (
    PromptRecommendationException,
    EmbeddingGenerationException,
)

logger = logging.getLogger("promptiq.services.prompt_recommendation")


class PromptRecommendationService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.embedding_service = embedding_service or EmbeddingService()

    async def recommend_prompts(
        self,
        session: AsyncSession,
        prompt_text: str,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        logger.info("Generating prompt recommendations for: '%s'", prompt_text)
        from app.core.config import settings
        rec_limit = limit if limit is not None else settings.prompt_top_k

        start_time = time.perf_counter()
        try:
            vector = await self.embedding_service.generate_for_prompt_async(prompt_text)
        except Exception as exc:
            logger.exception("Failed to generate embedding for recommendations")
            raise EmbeddingGenerationException("Failed to generate prompt embedding.") from exc
        emb_time = time.perf_counter() - start_time

        db_start = time.perf_counter()
        try:
            # Retrieve 5x candidates for ranking flexibility
            candidates = await self.prompt_repository.search_prompts_with_vector(
                session=session,
                vector=vector,
                limit=rec_limit * 5,
                include_versions=True,
            )
        except Exception as exc:
            logger.exception("Database candidate retrieval failed for recommendations")
            raise PromptRecommendationException("Database lookup failed during recommendation ranking.") from exc
        db_time = time.perf_counter() - db_start

        logger.info(
            "Candidate retrieval complete. Found %d candidates. EmbTime: %.4fs, DBTime: %.4fs",
            len(candidates),
            emb_time,
            db_time,
        )

        ranked_results = []
        now = datetime.now(timezone.utc)

        for prompt, sim_score in candidates:
            # 1. Similarity score (normalized: 0.0 - 1.0)
            s_score = max(0.0, min(1.0, sim_score))

            # 2. Reuse frequency score: length of version history (normalized: version_count / 10, max 1.0)
            version_count = len(prompt.versions) if prompt.versions else 1
            freq_score = min(float(version_count) / 10.0, 1.0)

            # 3. Recency score: 1 / (days_since_creation + 1)
            created_at = prompt.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            delta = now - created_at
            days = max(0, delta.days)
            recency_score = 1.0 / (float(days) + 1.0)

            # Combined Score Formula
            combined_score = 0.5 * s_score + 0.3 * freq_score + 0.2 * recency_score

            ranked_results.append({
                "prompt_id": str(prompt.id),
                "title": prompt.title,
                "original_prompt": prompt.original_prompt,
                "similarity_score": sim_score,
                "version_count": version_count,
                "created_at": prompt.created_at,
                "recommendation_score": combined_score,
            })

        # Sort by combined score descending
        ranked_results.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return ranked_results[:rec_limit]

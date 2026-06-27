from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Template
from app.repositories.template import TemplateRepository
from app.services.embedding_service import EmbeddingService
from app.services.exceptions import (
    EmbeddingGenerationError,
    InvalidTemplateModeError,
    NoTemplateMatchError,
    TemplateSearchError,
)
from app.services.template_ranking_service import TemplateRankingService

logger = logging.getLogger("promptiq.template_search")


class TemplateSearchService:
    def __init__(self, repository: TemplateRepository, ranking_service: TemplateRankingService) -> None:
        self.repository = repository
        self.ranking_service = ranking_service
        self.embedding_service = EmbeddingService()
        self.top_k = settings.top_k_results
        self.threshold = settings.similarity_threshold

    async def search_templates(
        self,
        session: AsyncSession,
        user_prompt: str,
        mode: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> list[dict]:
        if not mode.strip():
            raise InvalidTemplateModeError("Template mode must be provided.")

        top_k = top_k or self.top_k
        threshold = threshold or self.threshold

        logger.info("Template search started for mode=%s top_k=%d threshold=%s", mode, top_k, threshold)

        try:
            prompt_embedding = self.embedding_service.generate_for_prompt(user_prompt)
        except EmbeddingGenerationError as exc:
            raise TemplateSearchError("Failed to generate prompt embedding.") from exc

        templates = await self._fetch_candidate_templates(session, mode)
        if not templates:
            raise NoTemplateMatchError("No approved templates found for the requested mode.")

        similarity_scores = self._compute_similarity(session, prompt_embedding, templates)
        filtered = [t for t in templates if similarity_scores.get(str(t.id), 0.0) >= threshold]
        if not filtered:
            raise NoTemplateMatchError("No templates passed the similarity threshold.")

        ranked = self.ranking_service.rank(filtered, similarity_scores)
        result = self.ranking_service.build_result(ranked, similarity_scores)

        logger.info(
            "Template search completed. Returned %d templates. top_score=%s",
            len(result),
            max([item["similarity_score"] for item in result]) if result else 0.0,
        )
        return result[:top_k]

    async def _fetch_candidate_templates(self, session: AsyncSession, mode: str) -> list[Template]:
        return await self.repository.list_templates(
            session=session,
            mode=mode,
            is_approved=True,
            only_active_models=True,
            limit=1000,
            offset=0,
        )

    def _compute_similarity(self, prompt_embedding: list[float], templates: list[Template]) -> dict[str, float]:
        similarity_scores: dict[str, float] = {}
        for template in templates:
            if template.embedding is None:
                continue
            try:
                similarity = self._cosine_similarity(prompt_embedding, template.embedding)
            except ValueError:
                continue
            similarity_scores[str(template.id)] = similarity
        return similarity_scores

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            raise ValueError("Embedding dimensions must match.")
        numerator = sum(x * y for x, y in zip(a, b))
        denom_a = sum(x * x for x in a) ** 0.5
        denom_b = sum(y * y for y in b) ** 0.5
        if denom_a == 0 or denom_b == 0:
            return 0.0
        return numerator / (denom_a * denom_b)

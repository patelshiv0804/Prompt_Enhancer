from __future__ import annotations

import logging
from typing import Optional
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger("promptiq.mode_resolution")

class ModeResolutionService:
    def __init__(self, embedding_service: EmbeddingService) -> None:
        self.embedding_service = embedding_service

    async def resolve_mode(
        self,
        mode: str,
        distinct_modes: list[str],
    ) -> tuple[str, float]:
        logger.info("Resolving mode: %s", mode)
        if not distinct_modes:
            return mode, 1.0

        # Exact match check first (case insensitive)
        mode_lower = mode.strip().lower()
        for m in distinct_modes:
            if m.lower() == mode_lower:
                logger.info("Found exact match for mode: %s", m)
                return m, 1.0

        try:
            # Generate embedding for the input mode
            mode_emb = self.embedding_service.generate_for_prompt(mode)

            best_mode = distinct_modes[0]
            best_score = -1.0

            for candidate in distinct_modes:
                cand_emb = self.embedding_service.generate_for_prompt(candidate)
                # Compute cosine similarity (dot product of normalized embeddings)
                similarity = sum(x * y for x, y in zip(mode_emb, cand_emb))
                if similarity > best_score:
                    best_score = similarity
                    best_mode = candidate

            logger.info("Resolved mode semantically to: %s with score: %.4f", best_mode, best_score)
            return best_mode, best_score
        except Exception as exc:
            logger.exception("Semantic mode resolution failed, defaulting to raw input")
            return mode, 1.0

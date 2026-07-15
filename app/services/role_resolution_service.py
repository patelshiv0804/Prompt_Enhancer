from __future__ import annotations

import logging
from typing import Optional
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger("promptiq.role_resolution")

class RoleResolutionService:
    def __init__(self, embedding_service: EmbeddingService) -> None:
        self.embedding_service = embedding_service

    async def resolve_role(
        self,
        role: str,
        distinct_roles: list[str],
    ) -> tuple[str, float]:
        logger.info("Resolving role: %s", role)
        if not distinct_roles:
            return role, 1.0

        # Exact match check first (case insensitive)
        role_lower = role.strip().lower()
        for r in distinct_roles:
            if r.lower() == role_lower:
                logger.info("Found exact match for role: %s", r)
                return r, 1.0

        try:
            # Generate embedding for the input role
            role_emb = self.embedding_service.generate_for_prompt(role)

            best_role = distinct_roles[0]
            best_score = -1.0

            for candidate in distinct_roles:
                cand_emb = self.embedding_service.generate_for_prompt(candidate)
                # Compute cosine similarity (dot product of normalized embeddings)
                similarity = sum(x * y for x, y in zip(role_emb, cand_emb))
                if similarity > best_score:
                    best_score = similarity
                    best_role = candidate

            logger.info("Resolved role semantically to: %s with score: %.4f", best_role, best_score)
            return best_role, best_score
        except Exception as exc:
            logger.exception("Semantic role resolution failed, defaulting to raw input")
            return role, 1.0

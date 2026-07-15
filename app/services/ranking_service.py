from __future__ import annotations

import logging
from app.db.models import Template

logger = logging.getLogger("promptiq.ranking")


class RankingService:
    """
    Service responsible for scoring and ranking candidate templates.
    """

    def rank_candidates(
        self,
        candidates: list[tuple[Template, float]],
        target_role: str,
        target_mode: str,
    ) -> list[dict]:
        """
        Ranks candidate templates based on hierarchical criteria:
        1. Semantic Similarity (descending)
        2. Exact Mode Match (descending)
        3. is_featured (descending)
        4. use_count (descending)
        5. Exact Role Match (descending)

        Returns a list of ranked dicts, each holding the Template object and scoring components.
        """
        logger.info("Ranking %d candidate templates", len(candidates))
        decorated = []
        for template, similarity in candidates:
            # Check matches (case insensitive)
            exact_role_match = (
                template.role.strip().lower() == target_role.strip().lower()
                if template.role else False
            )
            exact_mode_match = (
                template.mode.strip().lower() == target_mode.strip().lower()
                if template.mode else False
            )

            decorated.append({
                "template": template,
                "similarity_score": similarity,
                "exact_mode_match": exact_mode_match,
                "is_featured": template.is_featured,
                "use_count": template.use_count,
                "exact_role_match": exact_role_match,
            })

        # Apply hierarchical sorting with reverse=True to sort elements descending
        ranked = sorted(
            decorated,
            key=lambda item: (
                item["similarity_score"],
                1 if item["exact_mode_match"] else 0,
                1 if item["is_featured"] else 0,
                item["use_count"],
                1 if item["exact_role_match"] else 0
            ),
            reverse=True
        )

        logger.info("Successfully ranked candidates. Top template ID: %s", 
                    ranked[0]["template"].id if ranked else None)
        return ranked

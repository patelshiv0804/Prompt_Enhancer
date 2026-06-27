from __future__ import annotations

import logging
from typing import Iterable

from app.db.models import Template

logger = logging.getLogger("promptiq.template_ranking")


class TemplateRankingService:
    def rank(self, templates: list[Template], similarity_scores: dict[str, float]) -> list[Template]:
        ranked = sorted(
            templates,
            key=lambda template: (
                similarity_scores.get(str(template.id), 0.0),
                template.is_approved,
                template.use_count,
                template.is_featured,
            ),
            reverse=True,
        )
        logger.info("Ranked %d templates", len(ranked))
        return ranked

    def build_result(self, templates: list[Template], similarity_scores: dict[str, float]) -> list[dict]:
        return [
            {
                "template_id": str(template.id),
                "title": template.title,
                "similarity_score": similarity_scores.get(str(template.id), 0.0),
                "is_featured": template.is_featured,
                "use_count": template.use_count,
            }
            for template in templates
        ]

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.template import TemplateRepository
from app.services.exceptions import NoTemplateMatchError
from app.services.template_search_service import TemplateSearchService
from app.services.template_ranking_service import TemplateRankingService

logger = logging.getLogger("promptiq.template_selection")


class TemplateSelectionService:
    def __init__(
        self,
        search_service: TemplateSearchService,
        repository: TemplateRepository,
    ) -> None:
        self.search_service = search_service
        self.repository = repository

    async def select_template(self, session: AsyncSession, user_prompt: str, mode: str, role: str | None = None) -> dict:
        logger.info("Selecting template for mode=%s role=%s", mode, role)
        templates = await self.search_service.search_templates(session, user_prompt, mode, role)
        if not templates:
            raise NoTemplateMatchError("No template matched the requested mode and prompt.")

        selected = templates[0]
        logger.info(
            "Selected template id=%s similarity_score=%s",
            selected["template_id"],
            selected["similarity_score"],
        )
        return selected

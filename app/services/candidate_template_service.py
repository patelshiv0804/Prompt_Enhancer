from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.template import TemplateRepository
from app.db.models import Template

logger = logging.getLogger("promptiq.candidate_template")

class CandidateTemplateService:
    def __init__(self, repository: TemplateRepository) -> None:
        self.repository = repository

    async def get_candidate_templates(
        self,
        session: AsyncSession,
        vector: list[float],
        role: str,
        mode: str,
        limit: int = 100,
    ) -> list[tuple[Template, float]]:
        logger.info("Retrieving candidate templates for resolved role=%s mode=%s", role, mode)
        return await self.repository.search_templates_with_vector(
            session=session,
            vector=vector,
            role=role,
            mode=mode,
            is_approved=True,
            limit=limit,
        )

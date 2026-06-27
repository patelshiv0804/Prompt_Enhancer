from __future__ import annotations

import logging

from app.services.exceptions import PromptOptimizationError
from app.services.llm.base import BaseLLMProvider
from app.services.template_selection_service import TemplateSelectionService
from app.services.llm.schemas import PromptOptimizationResult
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("promptiq.prompt_optimization")


class PromptOptimizationService:
    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        template_selection_service: TemplateSelectionService,
    ) -> None:
        self.llm_provider = llm_provider
        self.template_selection_service = template_selection_service

    async def optimize(self, session: AsyncSession, user_prompt: str, mode: str) -> PromptOptimizationResult:
        logger.info("Starting prompt optimization for mode=%s", mode)
        selected_template = await self.template_selection_service.select_template(session, user_prompt, mode)

        try:
            result = await self.llm_provider.optimize_prompt(
                prompt=user_prompt,
                template_id=selected_template["template_id"],
                mode=mode,
            )
        except Exception as exc:
            logger.exception("Prompt optimization failed")
            raise PromptOptimizationError("Prompt optimization failed.") from exc

        logger.info(
            "Prompt optimization complete template_id=%s score=%s",
            selected_template["template_id"],
            result.score,
        )
        return result

from __future__ import annotations

import logging

from app.services.exceptions import PromptAnalysisError
from app.services.llm.base import BaseLLMProvider
from app.services.llm.schemas import PromptAnalysisResult

logger = logging.getLogger("promptiq.prompt_analysis")


class PromptAnalysisService:
    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def analyze(self, prompt: str) -> PromptAnalysisResult:
        logger.info("Analyzing prompt")
        try:
            analysis = await self.llm_provider.analyze_prompt(prompt)
        except Exception as exc:
            logger.exception("Prompt analysis failed")
            raise PromptAnalysisError("Prompt analysis failed.") from exc

        logger.info(
            "Prompt analysis complete clarity=%s specificity=%s",
            analysis.clarity,
            analysis.specificity,
        )
        return analysis

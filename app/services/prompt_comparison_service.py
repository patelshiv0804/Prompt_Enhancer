from __future__ import annotations

import json
import logging
import time
from typing import Optional

from app.core.config import settings
from app.services.exceptions import PromptComparisonException
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import LLMTimeoutError

logger = logging.getLogger("promptiq.prompt_comparison")


class PromptComparisonService:
    """
    PromptComparisonService compares the original and enhanced prompts,
    generating comparison summaries, quality improvements, readabilities,
    and a percentage quality delta.
    """

    COMPARISON_PROMPT_TEMPLATE = (
        "Compare the following Original Prompt with the Enhanced Prompt:\n\n"
        "Original Prompt:\n"
        "\"{original_prompt}\"\n\n"
        "Enhanced Prompt:\n"
        "\"{enhanced_prompt}\"\n\n"
        "Identify the improvements and differences. Respond ONLY with a valid JSON object matching the following structure. Do not include markdown code block formatting or extra text:\n"
        "{{\n"
        "  \"differences\": \"<general summary of differences>\",\n"
        "  \"improvements\": [\"<improvement 1>\", \"<improvement 2>\"],\n"
        "  \"missing_issues_fixed\": [\"<issue fixed 1>\", \"<issue fixed 2>\"],\n"
        "  \"quality_delta\": <float representing estimated quality increase, e.g. 2.5>,\n"
        "  \"readability_improvement\": \"<explanation of readability improvements>\",\n"
        "  \"summary\": {{\n"
        "    \"before_score\": <float original score, e.g. 4.5>,\n"
        "    \"after_score\": <float enhanced score, e.g. 8.5>,\n"
        "    \"score_improvement\": <float delta, e.g. 4.0>,\n"
        "    \"grade_improvement\": \"<e.g. C to A>\",\n"
        "    \"estimated_quality_increase_pct\": <float, e.g. 88.5>,\n"
        "    \"confidence\": <float 0-1, e.g. 0.95>\n"
        "  }}\n"
        "}}\n"
    )

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def compare(self, original_prompt: str, enhanced_prompt: str) -> dict:
        logger.info("Initiating prompt comparison analysis")
        if not original_prompt.strip() or not enhanced_prompt.strip():
            raise PromptComparisonException("Original and enhanced prompts cannot be empty.")

        comparison_prompt = self.COMPARISON_PROMPT_TEMPLATE.format(
            original_prompt=original_prompt,
            enhanced_prompt=enhanced_prompt,
        )

        start_time = time.perf_counter()
        try:
            res = await self.llm_provider.generate(
                prompt=comparison_prompt,
                max_tokens=settings.mistral_max_tokens,
                temperature=settings.prompt_analysis_temperature,
            )
        except LLMTimeoutError as exc:
            logger.exception("LLM timeout during prompt comparison")
            raise PromptComparisonException("Mistral request timed out during prompt comparison.") from exc
        except Exception as exc:
            logger.exception("LLM failure during prompt comparison")
            raise PromptComparisonException("LLM provider failed to generate prompt comparison.") from exc

        duration = time.perf_counter() - start_time

        # Clean markdown code blocks from JSON text
        cleaned_json = self._clean_json(res.text)

        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM comparison response as JSON. Cleaned response: %s", cleaned_json)
            raise PromptComparisonException("LLM returned an invalid JSON response for prompt comparison.") from exc

        self._validate_comparison_data(data)

        logger.info(
            "Prompt comparison complete. Duration: %.4fs, quality delta: %s, confidence: %s",
            duration,
            data.get("quality_delta"),
            data.get("summary", {}).get("confidence"),
        )
        return data

    def _clean_json(self, text: str) -> str:
        text_clean = text.strip()
        if text_clean.startswith("```json"):
            text_clean = text_clean[7:]
        elif text_clean.startswith("```"):
            text_clean = text_clean[3:]
        if text_clean.endswith("```"):
            text_clean = text_clean[:-3]
        return text_clean.strip()

    def _validate_comparison_data(self, data: dict) -> None:
        required_keys = ["differences", "improvements", "missing_issues_fixed", "quality_delta", "readability_improvement", "summary"]
        for key in required_keys:
            if key not in data:
                raise PromptComparisonException(f"Missing required comparison key: '{key}'")

        summary = data["summary"]
        if not isinstance(summary, dict):
            raise PromptComparisonException("Comparison 'summary' must be a JSON dictionary.")

        required_summary_keys = [
            "before_score", "after_score", "score_improvement", 
            "grade_improvement", "estimated_quality_increase_pct", "confidence"
        ]
        for skey in required_summary_keys:
            if skey not in summary:
                raise PromptComparisonException(f"Missing summary metric: '{skey}'")

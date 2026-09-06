from __future__ import annotations

import json
import logging
import time
from typing import Optional, Any

from app.core.config import settings
from app.services.exceptions import (
    PromptAnalysisException,
    ScoringException,
    AnalysisTimeoutException,
)
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import LLMTimeoutError

logger = logging.getLogger("promptiq.prompt_analysis")


class PromptAnalysisService:
    """
    PromptAnalysisService uses the configured LLM provider to perform a detailed quality analysis
    across 6 key prompt engineering dimensions and returns structured scores,
    grades, and improvement suggestions.
    """

    ANALYSIS_PROMPT_TEMPLATE = (
        "Analyze the following user prompt for prompt engineering quality based on these criteria:\n"
        "1. Clarity: Is the task clearly defined? Is the user's intent obvious? Are action verbs specific?\n"
        "2. Context: Does the prompt provide background, domain/business context, purpose, or target problem?\n"
        "3. Role Definition: Does the prompt clearly define the AI's role (e.g. 'You are an SEO expert')?\n"
        "4. Output Format: Does the user specify formatting (e.g. Markdown, JSON, Table, bullet points, etc.)?\n"
        "5. Constraints: Are constraints (tone, audience, word count, length, style restrictions) defined?\n"
        "6. Examples: Are few-shot examples or sample format/style references provided?\n\n"
        "Respond ONLY with a valid JSON object matching the following structure. Do not include markdown code block formatting or extra text:\n"
        "{{\n"
        "  \"summary\": \"<summary text of overall prompt quality>\",\n"
        "  \"dimensions\": {{\n"
        "    \"clarity\": {{\n"
        "      \"score\": <integer 0-100>,\n"
        "      \"explanation\": \"<short explanation>\",\n"
        "      \"suggestions\": [\"<actionable suggestion 1>\", \"<actionable suggestion 2>\"]\n"
        "    }},\n"
        "    \"context\": {{\n"
        "      \"score\": <integer 0-100>,\n"
        "      \"explanation\": \"<short explanation>\",\n"
        "      \"suggestions\": [\"<actionable suggestion 1>\"]\n"
        "    }},\n"
        "    \"role_definition\": {{\n"
        "      \"score\": <integer 0-100>,\n"
        "      \"explanation\": \"<short explanation>\",\n"
        "      \"suggestions\": [\"<actionable suggestion 1>\"]\n"
        "    }},\n"
        "    \"output_format\": {{\n"
        "      \"score\": <integer 0-100>,\n"
        "      \"explanation\": \"<short explanation>\",\n"
        "      \"suggestions\": [\"<actionable suggestion 1>\"]\n"
        "    }},\n"
        "    \"constraints\": {{\n"
        "      \"score\": <integer 0-100>,\n"
        "      \"explanation\": \"<short explanation>\",\n"
        "      \"suggestions\": [\"<actionable suggestion 1>\"]\n"
        "    }},\n"
        "    \"examples\": {{\n"
        "      \"score\": <integer 0-100>,\n"
        "      \"explanation\": \"<short explanation>\",\n"
        "      \"suggestions\": [\"<actionable suggestion 1>\"]\n"
        "    }}\n"
        "  }}\n"
        "}}\n\n"
        "Prompt to analyze:\n"
        "\"{prompt}\""
    )

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def analyze(self, prompt: str) -> dict[str, Any]:
        logger.info("Initiating prompt quality analysis")
        if not prompt or not prompt.strip():
            raise PromptAnalysisException("Prompt content cannot be empty.")

        analysis_prompt = self.ANALYSIS_PROMPT_TEMPLATE.format(prompt=prompt)
        
        start_time = time.perf_counter()
        try:
            res = await self.llm_provider.generate(
                prompt=analysis_prompt,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.prompt_analysis_temperature,
            )
        except LLMTimeoutError as exc:
            logger.exception("LLM timeout during prompt analysis")
            raise AnalysisTimeoutException("LLM request timed out during prompt analysis.") from exc
        except Exception as exc:
            logger.exception("LLM failure during prompt analysis")
            raise PromptAnalysisException("LLM provider failed to generate prompt analysis.") from exc
        
        duration = time.perf_counter() - start_time

        # Clean markdown code blocks from JSON text
        cleaned_json = self._clean_json(res.text)

        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM analysis response as JSON. Cleaned response: %s", cleaned_json)
            raise PromptAnalysisException("LLM returned an invalid JSON response for prompt analysis.") from exc

        # Validate structured scoring fields
        self._validate_analysis_data(data)

        # Compute overall score and inject weights
        dims = data["dimensions"]
        clarity = int(dims["clarity"]["score"])
        context = int(dims["context"]["score"])
        role_def = int(dims["role_definition"]["score"])
        out_fmt = int(dims["output_format"]["score"])
        constraints = int(dims["constraints"]["score"])
        examples = int(dims["examples"]["score"])

        overall_score = round(
            clarity * 0.20 +
            context * 0.20 +
            role_def * 0.15 +
            out_fmt * 0.15 +
            constraints * 0.15 +
            examples * 0.15
        )

        dims["clarity"]["weight"] = 20
        dims["context"]["weight"] = 20
        dims["role_definition"]["weight"] = 15
        dims["output_format"]["weight"] = 15
        dims["constraints"]["weight"] = 15
        dims["examples"]["weight"] = 15

        # Compute Grade
        if overall_score >= 95:
            grade = "A+"
        elif overall_score >= 90:
            grade = "A"
        elif overall_score >= 85:
            grade = "B+"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 75:
            grade = "C+"
        elif overall_score >= 70:
            grade = "C"
        elif overall_score >= 60:
            grade = "D"
        else:
            grade = "F"

        final_result = {
            "overall_score": overall_score,
            "grade": grade,
            "summary": data.get("summary", ""),
            "dimensions": dims
        }

        logger.info(
            "Prompt analysis complete. Duration: %.4fs, prompt size: %d, overall score: %d, grade: %s",
            duration,
            len(prompt),
            overall_score,
            grade,
        )
        return final_result

    def _clean_json(self, text: str) -> str:
        text_clean = text.strip()
        if text_clean.startswith("```json"):
            text_clean = text_clean[7:]
        elif text_clean.startswith("```"):
            text_clean = text_clean[3:]
        if text_clean.endswith("```"):
            text_clean = text_clean[:-3]
        return text_clean.strip()

    def _validate_analysis_data(self, data: dict[str, Any]) -> None:
        if "dimensions" not in data:
            raise ScoringException("Missing required analysis key: 'dimensions'")
        
        required_dimensions = [
            "clarity", "context", "role_definition", "output_format", "constraints", "examples"
        ]
        dims = data["dimensions"]
        if not isinstance(dims, dict):
            raise ScoringException("Analysis 'dimensions' must be a JSON dictionary.")

        for dim in required_dimensions:
            if dim not in dims:
                raise ScoringException(f"Missing evaluation dimension: '{dim}'")
            d_obj = dims[dim]
            if not isinstance(d_obj, dict) or "score" not in d_obj or "explanation" not in d_obj or "suggestions" not in d_obj:
                raise ScoringException(f"Dimension '{dim}' is missing required keys (score, explanation, suggestions).")
            try:
                int(d_obj["score"])
            except (ValueError, TypeError):
                raise ScoringException(f"Score for dimension '{dim}' must be a valid integer.")

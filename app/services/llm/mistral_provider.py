from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.exceptions import (
    LLMError,
    LLMHealthError,
    LLMProviderError,
    LLMRequestError,
    LLMTimeoutError,
)
from app.services.llm.schemas import (
    GenerationResult,
    HealthCheckResult,
    PromptAnalysisResult,
    PromptOptimizationResult,
)

logger = logging.getLogger("promptiq.llm.mistral")


class MistralProvider(BaseLLMProvider):
    def __init__(self) -> None:
        if not settings.mistral_api_key:
            raise LLMProviderError("Mistral API key is required.")

        self.api_key = settings.mistral_api_key
        self.model = settings.mistral_model
        self.timeout = settings.mistral_timeout
        self.endpoint = f"https://api.mistral.ai/v1/models/{self.model}/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        timeout = httpx.Timeout(self.timeout, connect=self.timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(self.endpoint, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.ReadTimeout as exc:
                logger.exception("Mistral request timed out")
                raise LLMTimeoutError("Mistral request timed out.") from exc
            except httpx.HTTPStatusError as exc:
                logger.exception("Mistral request failed with status %s", exc.response.status_code)
                raise LLMRequestError("Mistral request failed.") from exc
            except Exception as exc:
                logger.exception("Mistral provider error")
                raise LLMProviderError("Unexpected Mistral provider error.") from exc

    async def analyze_prompt(self, prompt: str, **kwargs) -> PromptAnalysisResult:
        logger.info("Analyzing prompt with Mistral provider")
        payload = {
            "prompt": (
                "Analyze the following user prompt and score it for clarity, context, specificity, constraints, and output structure. "
                "Return strengths, weaknesses, recommendations, and a single letter grade.\n\nPrompt:\n" + prompt
            ),
            "max_tokens": 256,
            "temperature": 0.2,
        }
        data = await self._post(payload)
        text = self._parse_text(data)
        return self._parse_analysis(text)

    async def optimize_prompt(self, prompt: str, template_id: str, **kwargs) -> PromptOptimizationResult:
        logger.info("Optimizing prompt with Mistral provider using template_id=%s", template_id)
        payload = {
            "prompt": (
                "Generate an optimized version of the following user prompt by applying the selected template and improving clarity, context, specificity, constraints, and structure. "
                "Do not change the user intent. Include only the optimized prompt in the response.\n\nPrompt:\n"
                + prompt
                + "\n\nTemplate ID:\n"
                + template_id
            ),
            "max_tokens": 300,
            "temperature": 0.3,
        }
        data = await self._post(payload)
        text = self._parse_text(data)
        return PromptOptimizationResult(
            optimized_prompt=text.strip(),
            template_id=template_id,
            score=None,
            metadata={"provider": "mistral"},
        )

    async def generate(self, prompt: str, **kwargs) -> GenerationResult:
        logger.info("Generating text with Mistral provider")
        payload = {
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens", 256),
            "temperature": kwargs.get("temperature", 0.7),
        }
        data = await self._post(payload)
        text = self._parse_text(data)
        return GenerationResult(text=text.strip(), metadata={"provider": "mistral"})

    async def health_check(self) -> HealthCheckResult:
        logger.info("Performing Mistral health check")
        try:
            payload = {"prompt": "health check", "max_tokens": 1, "temperature": 0.0}
            await self._post(payload)
            return HealthCheckResult(healthy=True)
        except LLMError as exc:
            return HealthCheckResult(healthy=False, details=str(exc))

    def _parse_text(self, data: dict[str, Any]) -> str:
        if not isinstance(data, dict):
            raise LLMProviderError("Unexpected Mistral response format.")

        if "output" in data and isinstance(data["output"], str):
            return data["output"]
        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            first = data["choices"][0]
            if isinstance(first, dict) and "text" in first:
                return str(first["text"])

        raise LLMProviderError("Unable to parse Mistral response.")

    def _parse_analysis(self, text: str) -> PromptAnalysisResult:
        return PromptAnalysisResult(
            clarity=0.0,
            context=0.0,
            specificity=0.0,
            constraints=0.0,
            output_structure=0.0,
            strengths=text,
            weaknesses="",
            recommendations="",
            grade="B",
        )

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.services.llm.schemas import (
    GenerationResult,
    HealthCheckResult,
    PromptAnalysisResult,
    PromptOptimizationResult,
)


class BaseLLMProvider(ABC):
    @abstractmethod
    async def analyze_prompt(self, prompt: str, **kwargs) -> PromptAnalysisResult:
        raise NotImplementedError

    @abstractmethod
    async def optimize_prompt(
        self,
        prompt: str,
        template_id: str,
        **kwargs,
    ) -> PromptOptimizationResult:
        raise NotImplementedError

    async def optimize_prompt_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream the optimized prompt as text deltas.

        Providers that support token streaming override this. The default
        implementation signals non-support so callers can fall back to the
        blocking :meth:`optimize_prompt` path.
        """
        raise NotImplementedError("This LLM provider does not support streaming.")
        if False:  # pragma: no cover - makes this a coroutine generator
            yield ""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        raise NotImplementedError

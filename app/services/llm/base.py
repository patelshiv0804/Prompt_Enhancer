from __future__ import annotations

from abc import ABC, abstractmethod

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

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> GenerationResult:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        raise NotImplementedError

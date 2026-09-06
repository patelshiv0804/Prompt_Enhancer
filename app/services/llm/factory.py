from __future__ import annotations

from typing import Type

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mistral_provider import OpenAICompatibleProvider


class LLMFactory:
    _registry: dict[str, Type[BaseLLMProvider]] = {
        "groq": OpenAICompatibleProvider,
        "mistral": OpenAICompatibleProvider,
        "openai": OpenAICompatibleProvider,
        "openrouter": OpenAICompatibleProvider,
        "gemini": OpenAICompatibleProvider,
        "cerebras": OpenAICompatibleProvider,
        "local": OpenAICompatibleProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider: Type[BaseLLMProvider]) -> None:
        cls._registry[name.lower()] = provider

    @classmethod
    def get_provider(cls) -> BaseLLMProvider:
        provider_name = getattr(settings, "llm_provider", "groq").lower()
        provider_cls = cls._registry.get(provider_name, OpenAICompatibleProvider)
        return provider_cls()

from __future__ import annotations

from typing import Type

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mistral_provider import MistralProvider
from app.services.llm.exceptions import LLMProviderError


class LLMFactory:
    _registry: dict[str, Type[BaseLLMProvider]] = {
        "mistral": MistralProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider: Type[BaseLLMProvider]) -> None:
        cls._registry[name.lower()] = provider

    @classmethod
    def get_provider(cls) -> BaseLLMProvider:
        provider_name = getattr(settings, "llm_provider", "mistral").lower()
        provider_cls = cls._registry.get(provider_name)
        if provider_cls is None:
            raise LLMProviderError(f"LLM provider '{provider_name}' is not registered.")
        return provider_cls()

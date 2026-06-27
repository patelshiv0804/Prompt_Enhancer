from __future__ import annotations


class LLMError(Exception):
    pass


class LLMProviderError(LLMError):
    pass


class LLMRequestError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMHealthError(LLMError):
    pass

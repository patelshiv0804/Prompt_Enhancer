from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
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

logger = logging.getLogger("promptiq.llm.openai_compatible")


# ── Shared HTTP client ────────────────────────────────────────────────────
# A single process-wide httpx.AsyncClient is reused for every OpenAI-compatible
# call so
# the TLS handshake is paid once and warm keepalive connections are reused,
# instead of building (and tearing down) a fresh connection pool per request —
# which added 100-300ms per call and risked ephemeral-port/socket exhaustion
# under load. Created lazily on first use (inside the running event loop) and
# closed on application shutdown via close_shared_client().
_shared_client: httpx.AsyncClient | None = None
_client_lock: asyncio.Lock | None = None


def _get_client_lock() -> asyncio.Lock:
    # Created lazily so it always binds to the active event loop.
    global _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    return _client_lock


async def get_shared_client() -> httpx.AsyncClient:
    """Return the process-wide OpenAI-compatible HTTP client, creating it on first use."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        return _shared_client
    async with _get_client_lock():
        # Another coroutine may have created it while we waited for the lock.
        if _shared_client is not None and not _shared_client.is_closed:
            return _shared_client
        timeout = httpx.Timeout(
            settings.llm_timeout,
            connect=settings.llm_connect_timeout,
        )
        limits = httpx.Limits(
            max_connections=settings.httpx_max_connections,
            max_keepalive_connections=settings.httpx_max_keepalive_connections,
        )
        _shared_client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return _shared_client


async def close_shared_client() -> None:
    """Close the shared client on shutdown. Safe if it was never created."""
    global _shared_client
    client, _shared_client = _shared_client, None
    if client is not None and not client.is_closed:
        await client.aclose()


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(self) -> None:
        if not settings.llm_api_key:
            raise LLMProviderError("LLM API key is required.")

        self.provider_name = settings.llm_provider.strip().lower() or "openai-compatible"
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.endpoint = settings.llm_base_url.rstrip("/") + "/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = await get_shared_client()
        try:
            response = await client.post(self.endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.ReadTimeout as exc:
            logger.exception("%s request timed out", self.provider_name)
            raise LLMTimeoutError(f"{self.provider_name} request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            logger.exception(
                "%s request failed with status %s",
                self.provider_name,
                exc.response.status_code,
            )
            raise LLMRequestError(f"{self.provider_name} request failed.") from exc
        except Exception as exc:
            logger.exception("%s provider error", self.provider_name)
            raise LLMProviderError(f"Unexpected {self.provider_name} provider error.") from exc

    async def analyze_prompt(self, prompt: str, **kwargs) -> PromptAnalysisResult:
        logger.info("Analyzing prompt with %s provider", self.provider_name)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Analyze the following user prompt and score it for clarity, context, specificity, constraints, and output structure. "
                        "Return strengths, weaknesses, recommendations, and a single letter grade.\n\nPrompt:\n" + prompt
                    )
                }
            ],
            "max_tokens": 256,
            "temperature": 0.2,
        }
        data = await self._post(payload)
        text = self._parse_text(data)
        return self._parse_analysis(text)

    async def optimize_prompt(self, prompt: str, template_id: str, **kwargs) -> PromptOptimizationResult:
        logger.info("Optimizing prompt with %s provider using template_id=%s", self.provider_name, template_id)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        data = await self._post(payload)
        text = self._parse_text(data)
        choice = self._first_choice(data)
        return PromptOptimizationResult(
            optimized_prompt=text.strip(),
            template_id=template_id,
            score=None,
            metadata={
                "provider": self.provider_name,
                "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
                "usage": data.get("usage") if isinstance(data, dict) else None,
                "max_tokens": payload["max_tokens"],
            },
        )

    async def optimize_prompt_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream the optimized prompt token-by-token from the LLM provider.

        Yields text deltas as they arrive. OpenAI-compatible chat completions
        with ``stream=True`` emits Server-Sent Events in OpenAI's chunk format::

            data: {"choices":[{"delta":{"content":"Act"}}]}
            data: {"choices":[{"delta":{"content":" as"}}]}
            ...
            data: [DONE]

        Only the ``delta.content`` fragments are surfaced; framing lines and the
        terminal ``[DONE]`` sentinel are consumed internally.
        """
        logger.info("Streaming prompt optimization with %s provider", self.provider_name)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }
        client = await get_shared_client()
        try:
            async with client.stream(
                "POST", self.endpoint, json=payload, headers=self.headers
            ) as response:
                # Drain the body before raise_for_status so the error detail
                # is available (httpx won't read a streamed body on its own).
                if response.status_code >= 400:
                    await response.aread()
                    response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        # Ignore keep-alive/comment frames or partial lines.
                        continue
                    delta = self._extract_delta(chunk)
                    if delta:
                        yield delta
        except httpx.ReadTimeout as exc:
            logger.exception("%s streaming request timed out", self.provider_name)
            raise LLMTimeoutError(f"{self.provider_name} streaming request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            logger.exception(
                "%s streaming failed with status %s",
                self.provider_name,
                exc.response.status_code,
            )
            raise LLMRequestError(f"{self.provider_name} streaming request failed.") from exc
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("%s provider streaming error", self.provider_name)
            raise LLMProviderError(
                f"Unexpected {self.provider_name} provider streaming error."
            ) from exc

    def _extract_delta(self, chunk: dict[str, Any]) -> str:
        choice = self._first_choice(chunk)
        if isinstance(choice, dict):
            delta = choice.get("delta")
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str):
                    return content
        return ""

    async def generate(self, prompt: str, **kwargs) -> GenerationResult:
        logger.info("Generating text with %s provider", self.provider_name)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": kwargs.get("max_tokens", 256),
            "temperature": kwargs.get("temperature", 0.7),
        }
        data = await self._post(payload)
        text = self._parse_text(data)
        return GenerationResult(text=text.strip(), metadata={"provider": self.provider_name})

    async def health_check(self) -> HealthCheckResult:
        logger.info("Performing %s health check", self.provider_name)
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "health check"}
                ],
                "max_tokens": 1,
                "temperature": 0.0
            }
            await self._post(payload)
            return HealthCheckResult(healthy=True)
        except LLMError as exc:
            return HealthCheckResult(healthy=False, details=str(exc))

    def _parse_text(self, data: dict[str, Any]) -> str:
        if not isinstance(data, dict):
            raise LLMProviderError("Unexpected LLM response format.")

        first = self._first_choice(data)
        if isinstance(first, dict) and "message" in first and "content" in first["message"]:
            return str(first["message"]["content"])

        raise LLMProviderError("Unable to parse LLM response.")

    def _first_choice(self, data: dict[str, Any]) -> dict[str, Any] | None:
        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            first = data["choices"][0]
            if isinstance(first, dict):
                return first
        return None

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


MistralProvider = OpenAICompatibleProvider

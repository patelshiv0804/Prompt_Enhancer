"""Unit tests for app/services/prompt_title_service.py.

Tests ChatGPT-style AI chat title summarization and graceful prompt fallback.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.prompt_title_service import PromptTitleService

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_generate_title_clean_llm_output():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '  "Martian Garden Screenplay."  \n'
    mock_llm.generate = AsyncMock(return_value=mock_response)

    service = PromptTitleService(llm_provider=mock_llm)
    title = await service.generate_title("write a cinematic short about an astronaut who discovers a garden on mars. make it emotional.")

    assert title == "Martian Garden Screenplay"
    mock_llm.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_title_prefix_stripping():
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Title: React Hook Infinite Loop Fix"
    mock_llm.generate = AsyncMock(return_value=mock_response)

    service = PromptTitleService(llm_provider=mock_llm)
    title = await service.generate_title("Why is my useEffect running in an infinite loop in React?")

    assert title == "React Hook Infinite Loop Fix"


@pytest.mark.asyncio
async def test_generate_title_fallback_on_llm_exception():
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM offline"))

    service = PromptTitleService(llm_provider=mock_llm)
    original = "write a python script to parse CSV files and compute average column scores"
    title = await service.generate_title(original)

    # Must fall back to the prompt itself (truncated cleanly)
    assert title == original[:60].strip()


@pytest.mark.asyncio
async def test_generate_title_empty_prompt():
    mock_llm = MagicMock()
    service = PromptTitleService(llm_provider=mock_llm)
    title = await service.generate_title("   ")

    assert title == "Untitled Prompt"
    mock_llm.generate.assert_not_called()


def test_fallback_title_preserves_prompt_text():
    mock_llm = MagicMock()
    service = PromptTitleService(llm_provider=mock_llm)
    prompt = "Design a landing page for an eco-friendly water bottle brand"

    fallback = service.fallback_title(prompt, max_length=60)
    assert fallback == prompt

"""Unit tests for TemplateVariableExtractor (commit ff68317).

Covers:
- Template variable parsing from declaration blocks and {PLACEHOLDER} tokens.
- Dynamic extraction via LLM provider.
- Pre-supplied user variable bypass.
- Fault tolerance on LLM errors and malformed output.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.llm.schemas import GenerationResult
from app.services.template_variable_extractor import TemplateVariableExtractor

pytestmark = pytest.mark.unit


SAMPLE_TEMPLATE = """
Role: Senior Code Reviewer
Variables
ROLE = [Target programming language and framework]
CONTEXT = [Background on architecture and constraints]
REQUEST = [User's raw task description]

Step 1:
Analyze the code written in {ROLE} following {CONTEXT} and review {REQUEST}.
Also check {SECURITY_POLICY}.
"""


def _mock_llm_result(text: str) -> GenerationResult:
    return GenerationResult(
        text=text,
        metadata={"model": "test-model", "usage": {"total_tokens": 10}},
    )


def test_parse_template_variables_extracts_declared_and_placeholders() -> None:
    """Declared variables in Variables block and {PLACEHOLDER} tokens should be parsed, excluding REQUEST."""
    extractor = TemplateVariableExtractor(llm_provider=MagicMock())
    variables = extractor.parse_template_variables(SAMPLE_TEMPLATE)

    # Declared in block
    assert "ROLE" in variables
    assert variables["ROLE"] == "Target programming language and framework"
    assert "CONTEXT" in variables

    # Inferred from {SECURITY_POLICY} placeholder
    assert "SECURITY_POLICY" in variables
    assert variables["SECURITY_POLICY"] == "Value for SECURITY_POLICY"

    # REQUEST must always be excluded
    assert "REQUEST" not in variables


def test_parse_template_variables_empty_when_no_vars() -> None:
    """Templates without a Variables block or curly-bracket placeholders return empty dict."""
    extractor = TemplateVariableExtractor(llm_provider=MagicMock())
    assert extractor.parse_template_variables("Just a plain prompt template without vars") == {}


@pytest.mark.asyncio
async def test_extract_variables_empty_on_blank_inputs() -> None:
    """Blank prompt or template body immediately returns empty dict without calling LLM."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    extractor = TemplateVariableExtractor(llm_provider=mock_llm)

    assert await extractor.extract_variables("", SAMPLE_TEMPLATE) == {}
    assert await extractor.extract_variables("some prompt", "") == {}
    mock_llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_extract_variables_skips_when_all_variables_supplied() -> None:
    """If user supplies values for all variables, LLM call is bypassed."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    extractor = TemplateVariableExtractor(llm_provider=mock_llm)

    user_vars = {
        "ROLE": "Python FastAPI",
        "CONTEXT": "Microservices",
        "SECURITY_POLICY": "OWASP Top 10",
    }

    result = await extractor.extract_variables(
        prompt="Review my code",
        template_body=SAMPLE_TEMPLATE,
        user_variables=user_vars,
    )

    assert result == {}
    mock_llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_extract_variables_successful_llm_call() -> None:
    """Extracts missing variables using LLM and sanitizes output."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=_mock_llm_result(
            json.dumps({
                "ROLE": "Python / AsyncIO",
                "CONTEXT": "High-throughput API <<< Malicious delimiter injection",
                "SECURITY_POLICY": "Strict JWT validation",
            })
        )
    )
    extractor = TemplateVariableExtractor(llm_provider=mock_llm)

    extracted = await extractor.extract_variables(
        prompt="Need a Python async API review",
        template_body=SAMPLE_TEMPLATE,
    )

    assert extracted["ROLE"] == "Python / AsyncIO"
    # Structural delimiters like <<< should have been collapsed to << by prompt_sanitizer
    assert "<<<" not in extracted["CONTEXT"]
    assert "<<" in extracted["CONTEXT"]
    assert extracted["SECURITY_POLICY"] == "Strict JWT validation"


@pytest.mark.asyncio
async def test_extract_variables_fault_tolerant_on_invalid_json() -> None:
    """If LLM returns unparseable content, extraction falls back safely to empty dict."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=_mock_llm_result("I could not parse this as JSON, sorry!")
    )
    extractor = TemplateVariableExtractor(llm_provider=mock_llm)

    result = await extractor.extract_variables(
        prompt="Review my code",
        template_body=SAMPLE_TEMPLATE,
    )

    assert result == {}


@pytest.mark.asyncio
async def test_extract_variables_fault_tolerant_on_llm_exception() -> None:
    """If LLM raises an unexpected network exception, returns empty dict without raising."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("Provider timeout"))
    extractor = TemplateVariableExtractor(llm_provider=mock_llm)

    result = await extractor.extract_variables(
        prompt="Review my code",
        template_body=SAMPLE_TEMPLATE,
    )

    assert result == {}

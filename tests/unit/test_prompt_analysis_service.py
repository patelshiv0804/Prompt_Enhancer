"""Unit tests for app/services/prompt_analysis_service.py.

This is the scoring engine behind the analysis panel, and it is unit-testable
because its constructor takes only a ``BaseLLMProvider`` — so ``StubLLMProvider``
covers it with no database, no network and no ASGI app.

Two things are worth stating before reading the assertions:

* The stub's analysis payload is selected by the ``"role_definition"`` marker that
  ``ANALYSIS_PROMPT_TEMPLATE`` itself contains, so the wiring under test here is
  the same wiring the integration tier exercises.
* The six weights sum to exactly 1.00, so a *uniform* set of dimension scores maps
  to the same overall score. Every grade-band test below uses uniform scores for
  that reason — it makes the boundary an arithmetic fact rather than an artefact of
  float rounding.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import pytest

from app.services.exceptions import (
    AnalysisTimeoutException,
    PromptAnalysisException,
    ScoringException,
)
from app.services.llm.exceptions import LLMProviderError, LLMTimeoutError
from app.services.prompt_analysis_service import PromptAnalysisService
from tests.stubs.llm import (
    STUB_ANALYSIS_GRADE,
    STUB_ANALYSIS_OVERALL_SCORE,
    STUB_ANALYSIS_SCORES,
    StubLLMProvider,
)

pytestmark = pytest.mark.unit

DIMENSIONS = (
    "clarity",
    "context",
    "role_definition",
    "output_format",
    "constraints",
    "examples",
)
WEIGHTS = {
    "clarity": 20,
    "context": 20,
    "role_definition": 15,
    "output_format": 15,
    "constraints": 15,
    "examples": 15,
}

PROMPT = "write a launch email for a developer tool"


@pytest.fixture
def stub() -> StubLLMProvider:
    return StubLLMProvider()


@pytest.fixture
def service(stub: StubLLMProvider) -> PromptAnalysisService:
    return PromptAnalysisService(llm_provider=stub)


def dimension(score: Any) -> dict[str, Any]:
    return {"score": score, "explanation": "because", "suggestions": ["do a thing"]}


def payload(
    *, scores: Optional[dict[str, Any]] = None, summary: Optional[str] = "a summary"
) -> str:
    scores = scores or {name: 80 for name in DIMENSIONS}
    body: dict[str, Any] = {"dimensions": {n: dimension(s) for n, s in scores.items()}}
    if summary is not None:
        body["summary"] = summary
    return json.dumps(body)


def uniform(score: Any) -> str:
    return payload(scores={name: score for name in DIMENSIONS})


# ─────────────────────────────────────────────────────────────────────────────
# The happy path, against the shared stub payload
# ─────────────────────────────────────────────────────────────────────────────


async def test_analyze_scores_and_grades_the_stub_payload(
    service: PromptAnalysisService,
) -> None:
    """Also a drift guard on the stub: if the weights change, the constants in
    ``tests/stubs/llm.py`` stop matching and every integration assertion that
    quotes them fails here first, with a clear reason."""
    result = await service.analyze(PROMPT)

    assert result["overall_score"] == STUB_ANALYSIS_OVERALL_SCORE
    assert result["grade"] == STUB_ANALYSIS_GRADE
    assert result["summary"] == "Deterministic stub analysis."
    assert set(result["dimensions"]) == set(DIMENSIONS)


async def test_each_dimension_keeps_its_own_score(service: PromptAnalysisService) -> None:
    """The stub uses distinct per-dimension scores precisely so a value read from
    the wrong slot is detectable."""
    result = await service.analyze(PROMPT)

    assert {
        name: body["score"] for name, body in result["dimensions"].items()
    } == STUB_ANALYSIS_SCORES


async def test_weights_are_injected_into_every_dimension(
    service: PromptAnalysisService,
) -> None:
    """The frontend renders these, and the LLM is never asked for them."""
    result = await service.analyze(PROMPT)

    assert {name: body["weight"] for name, body in result["dimensions"].items()} == WEIGHTS
    assert sum(WEIGHTS.values()) == 100


async def test_explanations_and_suggestions_are_passed_through(
    service: PromptAnalysisService,
) -> None:
    result = await service.analyze(PROMPT)

    clarity = result["dimensions"]["clarity"]
    assert clarity["explanation"] == "Stub explanation for clarity."
    assert clarity["suggestions"] == ["Stub suggestion for clarity."]


async def test_the_prompt_under_analysis_is_embedded_in_the_llm_request(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    await service.analyze(PROMPT)

    (call,) = stub.calls_to("generate")
    assert PROMPT in call.prompt
    assert call.route == "analysis", "the stub's routing marker no longer matches"
    assert stub.unrouted_prompts == []


async def test_the_analysis_specific_generation_settings_are_forwarded(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """Analysis uses its own low temperature (0.2) rather than the provider
    default, because the reply has to be parseable JSON."""
    from app.core.config import settings

    await service.analyze(PROMPT)

    (call,) = stub.calls_to("generate")
    assert call.kwargs == {
        "max_tokens": settings.mistral_max_tokens,
        "temperature": settings.prompt_analysis_temperature,
    }
    assert settings.prompt_analysis_temperature <= 0.3


async def test_the_result_carries_exactly_four_top_level_keys(
    service: PromptAnalysisService,
) -> None:
    """``/api/v1/prompts/analyze`` returns this dict straight to the client, so its
    shape is the API contract."""
    result = await service.analyze(PROMPT)

    assert set(result) == {"overall_score", "grade", "summary", "dimensions"}


# ─────────────────────────────────────────────────────────────────────────────
# Weighting and grade bands
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("score", "grade"),
    [
        (100, "A+"),
        (95, "A+"),
        (94, "A"),
        (90, "A"),
        (89, "B+"),
        (85, "B+"),
        (84, "B"),
        (80, "B"),
        (79, "C+"),
        (75, "C+"),
        (74, "C"),
        (70, "C"),
        (69, "D"),
        (60, "D"),
        (59, "F"),
        (0, "F"),
    ],
)
async def test_grade_bands(
    service: PromptAnalysisService, stub: StubLLMProvider, score: int, grade: str
) -> None:
    """Uniform scores, so ``overall_score == score`` and the band is exercised
    directly at each edge."""
    stub.override_generate("analysis", uniform(score))

    result = await service.analyze(PROMPT)

    assert result["overall_score"] == score
    assert result["grade"] == grade


async def test_the_weighting_favours_clarity_and_context(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """20/20/15/15/15/15 — a perfect clarity score is worth more than a perfect
    examples score, and this proves the multipliers are not all equal."""
    high_clarity = {name: 0 for name in DIMENSIONS} | {"clarity": 100}
    high_examples = {name: 0 for name in DIMENSIONS} | {"examples": 100}

    stub.override_generate("analysis", payload(scores=high_clarity))
    clarity_only = await service.analyze(PROMPT)

    stub.override_generate("analysis", payload(scores=high_examples))
    examples_only = await service.analyze(PROMPT)

    assert clarity_only["overall_score"] == 20
    assert examples_only["overall_score"] == 15


async def test_scores_are_truncated_by_int_not_rounded(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """JSON has no integer type, so a model that emits ``89.9`` becomes ``89``.

    ``int(...)`` truncates. Documented rather than asserted as desirable: it costs
    at most one point and keeps the API's advertised integer contract.
    """
    stub.override_generate("analysis", uniform(89.9))

    result = await service.analyze(PROMPT)

    assert result["overall_score"] == 89
    assert result["grade"] == "B+"


async def test_a_numeric_string_score_is_accepted(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """``int("80")`` succeeds, so a model that quotes its numbers still works."""
    stub.override_generate("analysis", uniform("80"))

    assert (await service.analyze(PROMPT))["overall_score"] == 80


# ─────────────────────────────────────────────────────────────────────────────
# _clean_json — stripping the fences the model was told not to emit
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "wrapper",
    [
        "```json\n{body}\n```",
        "```\n{body}\n```",
        "```json{body}```",
        "\n\n  ```json\n{body}\n```  \n\n",
        "{body}",
        "  {body}  ",
    ],
    ids=["json-fence", "bare-fence", "no-newlines", "surrounded-by-blanks", "plain", "padded"],
)
async def test_markdown_fences_are_stripped(
    service: PromptAnalysisService, stub: StubLLMProvider, wrapper: str
) -> None:
    """The instruction block says "do not include markdown code block formatting",
    and models ignore it often enough that this is the normal path."""
    stub.override_generate("analysis", wrapper.format(body=uniform(80)))

    assert (await service.analyze(PROMPT))["overall_score"] == 80


def test_clean_json_only_strips_a_leading_fence(
    service: PromptAnalysisService,
) -> None:
    """A fence in the *middle* is left alone — the check is ``startswith``."""
    assert service._clean_json('{"a": "```json"}') == '{"a": "```json"}'


def test_clean_json_strips_json_before_bare_fence(
    service: PromptAnalysisService,
) -> None:
    """``elif`` ordering: ```` ```json ```` removes 7 chars, so the language tag
    does not survive as a stray ``json`` prefix."""
    assert service._clean_json('```json{"a": 1}```') == '{"a": 1}'


def test_clean_json_handles_a_trailing_fence_without_a_leading_one(
    service: PromptAnalysisService,
) -> None:
    assert service._clean_json('{"a": 1}```') == '{"a": 1}'


# ─────────────────────────────────────────────────────────────────────────────
# Input and LLM failure paths
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t", None], ids=["empty", "spaces", "newlines", "none"])
async def test_a_blank_prompt_is_rejected_before_the_llm_is_called(
    service: PromptAnalysisService, stub: StubLLMProvider, prompt: Any
) -> None:
    with pytest.raises(PromptAnalysisException, match="cannot be empty"):
        await service.analyze(prompt)

    assert stub.calls == [], "the guard must run before any token is spent"


async def test_an_llm_timeout_becomes_an_analysis_timeout(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """A distinct exception type because the route maps it to 504, not 500."""
    stub.fail("generate", LLMTimeoutError("mistral took too long"))

    with pytest.raises(AnalysisTimeoutException, match="timed out during prompt analysis"):
        await service.analyze(PROMPT)


@pytest.mark.parametrize(
    "error",
    [LLMProviderError("bad key"), RuntimeError("unexpected"), ValueError("nonsense")],
    ids=["provider-error", "runtime-error", "value-error"],
)
async def test_any_other_llm_failure_becomes_a_prompt_analysis_exception(
    service: PromptAnalysisService, stub: StubLLMProvider, error: Exception
) -> None:
    """``except Exception`` is broad on purpose — no provider failure should reach
    the route handler as an unclassified 500."""
    stub.fail("generate", error)

    with pytest.raises(PromptAnalysisException, match="failed to generate prompt analysis"):
        await service.analyze(PROMPT)


@pytest.mark.parametrize(
    "text",
    ["not json at all", "", "{", '{"dimensions": }', "```json\n```"],
    ids=["prose", "empty", "truncated", "invalid-value", "empty-fence"],
)
async def test_unparseable_json_becomes_a_prompt_analysis_exception(
    service: PromptAnalysisService, stub: StubLLMProvider, text: str
) -> None:
    stub.override_generate("analysis", text)

    with pytest.raises(PromptAnalysisException, match="invalid JSON response"):
        await service.analyze(PROMPT)


# ─────────────────────────────────────────────────────────────────────────────
# _validate_analysis_data
# ─────────────────────────────────────────────────────────────────────────────


async def test_a_missing_dimensions_key_is_a_scoring_exception(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """``ScoringException`` is *not* a subclass of ``PromptAnalysisException``
    (app/services/exceptions.py), so it leaves ``analyze`` as its own type and the
    route has to handle it separately. Pinned because that is easy to get wrong.
    """
    stub.override_generate("analysis", json.dumps({"summary": "no scores here"}))

    with pytest.raises(ScoringException, match="Missing required analysis key"):
        await service.analyze(PROMPT)


@pytest.mark.parametrize(
    "dimensions", [[], "text", 5, None], ids=["list", "string", "int", "null"]
)
async def test_non_dict_dimensions_is_a_scoring_exception(
    service: PromptAnalysisService, stub: StubLLMProvider, dimensions: Any
) -> None:
    stub.override_generate("analysis", json.dumps({"dimensions": dimensions}))

    with pytest.raises(ScoringException, match="must be a JSON dictionary"):
        await service.analyze(PROMPT)


@pytest.mark.parametrize("omitted", DIMENSIONS)
async def test_every_dimension_is_required(
    service: PromptAnalysisService, stub: StubLLMProvider, omitted: str
) -> None:
    scores = {name: 80 for name in DIMENSIONS if name != omitted}
    stub.override_generate("analysis", payload(scores=scores))

    with pytest.raises(ScoringException, match=f"Missing evaluation dimension: '{omitted}'"):
        await service.analyze(PROMPT)


@pytest.mark.parametrize("key", ["score", "explanation", "suggestions"])
async def test_every_dimension_needs_all_three_keys(
    service: PromptAnalysisService, stub: StubLLMProvider, key: str
) -> None:
    body = json.loads(payload())
    del body["dimensions"]["context"][key]
    stub.override_generate("analysis", json.dumps(body))

    with pytest.raises(ScoringException, match="missing required keys"):
        await service.analyze(PROMPT)


@pytest.mark.parametrize(
    "value", [80, "80", "  80  ", 80.0], ids=["int", "string", "padded-string", "float"]
)
async def test_coercible_scores_pass_validation(
    service: PromptAnalysisService, stub: StubLLMProvider, value: Any
) -> None:
    stub.override_generate("analysis", uniform(value))

    assert (await service.analyze(PROMPT))["overall_score"] == 80


@pytest.mark.parametrize(
    "value", ["high", None, "", [], {}], ids=["word", "null", "empty", "list", "dict"]
)
async def test_a_non_numeric_score_is_a_scoring_exception(
    service: PromptAnalysisService, stub: StubLLMProvider, value: Any
) -> None:
    stub.override_generate("analysis", uniform(value))

    with pytest.raises(ScoringException, match="must be a valid integer"):
        await service.analyze(PROMPT)


async def test_a_non_dict_dimension_body_is_a_scoring_exception(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """A model that answers ``"clarity": 80`` instead of an object."""
    body = json.loads(payload())
    body["dimensions"]["clarity"] = 80
    stub.override_generate("analysis", json.dumps(body))

    with pytest.raises(ScoringException, match="missing required keys"):
        await service.analyze(PROMPT)


async def test_extra_dimensions_are_ignored_not_rejected(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """Only the six known dimensions are scored; a seventh is carried through
    untouched rather than failing the request."""
    body = json.loads(payload())
    body["dimensions"]["creativity"] = dimension(10)
    stub.override_generate("analysis", json.dumps(body))

    result = await service.analyze(PROMPT)

    assert result["overall_score"] == 80
    assert "weight" not in result["dimensions"]["creativity"]


async def test_a_missing_summary_becomes_an_empty_string(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """``data.get("summary", "")`` — the frontend renders this field
    unconditionally, so ``None`` would show up as literal "None"."""
    stub.override_generate("analysis", payload(summary=None))

    assert (await service.analyze(PROMPT))["summary"] == ""


async def test_a_top_level_json_scalar_raises_a_type_error(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """Documented gap, pinning current behaviour.

    ``_validate_analysis_data`` starts with ``"dimensions" not in data`` and never
    checks that ``data`` is a mapping. A reply of bare ``5`` is valid JSON, so it
    gets past the decode step and then raises ``TypeError: argument of type 'int'
    is not iterable`` — an unclassified error that reaches the route as a 500
    rather than as the ``ScoringException`` every other malformed shape produces.

    A JSON *string* or *list* reply is handled correctly (membership works on
    both), so only scalars are affected. Invert this test if an isinstance guard
    is added.
    """
    stub.override_generate("analysis", "5")

    with pytest.raises(TypeError):
        await service.analyze(PROMPT)


async def test_a_top_level_json_list_is_a_scoring_exception(
    service: PromptAnalysisService, stub: StubLLMProvider
) -> None:
    """The counterpart to the test above: membership on a list works, so this
    shape is classified properly."""
    stub.override_generate("analysis", "[]")

    with pytest.raises(ScoringException, match="Missing required analysis key"):
        await service.analyze(PROMPT)

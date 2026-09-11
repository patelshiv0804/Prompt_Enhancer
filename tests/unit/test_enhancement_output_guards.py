"""Unit tests for the two pure guards in app/services/prompt_enhancement_service.py.

``enhance_prompt`` itself needs a database and is covered in the integration tier.
These two methods, though, are pure string functions and they decide whether an
enhancement succeeds or burns ``max_retries`` rounds of exponential backoff:

* :meth:`is_task_execution` — the detector. If it fires, the service discards the
  model's output and retries with strengthened instructions.
* :meth:`_clean_enhanced_output` — the sanitiser that runs first, stripping the
  preamble and code fences models add despite being told not to.

They are tested together because they compose: the sanitiser is what lets a reply
like "Here is the enhanced prompt: You are…" survive the detector.

The service is constructed with ``retrieval_service=None``; neither method touches
it, and passing None makes that explicit rather than dragging a stub along.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.prompt_enhancement_service import PromptEnhancementService
from tests.stubs.llm import DEFAULT_OPTIMIZED_PROMPT, StubLLMProvider

pytestmark = pytest.mark.unit

CONVERSATIONAL_HEADERS = (
    "here is",
    "sure, here",
    "the ideal customer",
    "i can help you",
    "i will write",
    "i will do",
    "the answer is",
    "here are",
)
DIRECTIVES = (
    "act as",
    "you are",
    "your task",
    "your role",
    "system prompt",
    "instructions:",
    "context:",
    "objective:",
)

ORIGINAL = "describe our ideal customer"


@pytest.fixture
def service() -> PromptEnhancementService:
    return PromptEnhancementService(
        llm_provider=StubLLMProvider(),
        retrieval_service=None,  # type: ignore[arg-type]
    )


# ─────────────────────────────────────────────────────────────────────────────
# is_task_execution — rule 1, conversational openers
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("header", CONVERSATIONAL_HEADERS)
def test_a_conversational_opener_is_task_execution(
    service: PromptEnhancementService, header: str
) -> None:
    """Every opener is checked, so adding one to the list without a test here is
    the only way this can silently regress."""
    assert service.is_task_execution(f"{header} the thing you asked for.", ORIGINAL) is True


@pytest.mark.parametrize("header", CONVERSATIONAL_HEADERS)
def test_the_opener_check_wins_over_the_directive_check(
    service: PromptEnhancementService, header: str
) -> None:
    """Rule 1 returns early, so directive keywords cannot rescue a reply that
    opens conversationally — the model narrating before the prompt is itself the
    signal."""
    text = f"{header} what you wanted.\nYou are an expert. Objective: do it."

    assert service.is_task_execution(text, ORIGINAL) is True


def test_the_opener_check_is_case_insensitive(service: PromptEnhancementService) -> None:
    assert service.is_task_execution("HERE IS your answer", ORIGINAL) is True
    assert service.is_task_execution("Here Is your answer", ORIGINAL) is True


def test_the_opener_check_ignores_leading_whitespace(
    service: PromptEnhancementService,
) -> None:
    """``text.strip()`` runs first, so a leading blank line does not smuggle a
    conversational reply past rule 1."""
    assert service.is_task_execution("\n\n  Here is the answer", ORIGINAL) is True


def test_an_opener_in_the_middle_does_not_trip_rule_one(
    service: PromptEnhancementService,
) -> None:
    """``startswith``, not a substring search — the phrase is legitimate inside a
    prompt ("You are told that here is the context…")."""
    text = "You are an editor. Note that here is where the draft begins."

    assert service.is_task_execution(text, ORIGINAL) is False


# ─────────────────────────────────────────────────────────────────────────────
# is_task_execution — rule 2, absence of directive language
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("directive", DIRECTIVES)
def test_any_single_directive_keyword_satisfies_rule_two(
    service: PromptEnhancementService, directive: str
) -> None:
    assert service.is_task_execution(f"Some framing. {directive} do the work.", ORIGINAL) is False


def test_text_with_no_directive_language_is_task_execution(
    service: PromptEnhancementService,
) -> None:
    """The stricter of the two rules: a reply that reads like an answer rather
    than an instruction is rejected even without a conversational opener."""
    text = "Our ideal customer is a mid-market SaaS operations lead in North America."

    assert service.is_task_execution(text, ORIGINAL) is True


def test_the_directive_check_is_case_insensitive(
    service: PromptEnhancementService,
) -> None:
    assert service.is_task_execution("ACT AS a senior editor.", ORIGINAL) is False


def test_a_directive_keyword_may_appear_anywhere(
    service: PromptEnhancementService,
) -> None:
    """A substring search, unlike rule 1 — so a prompt that reaches its role
    definition late still passes."""
    text = "Deliverable: a positioning brief.\n\nRole context: you are a strategist."

    assert service.is_task_execution(text, ORIGINAL) is False


@pytest.mark.parametrize("text", ["", "   ", "\n\n"], ids=["empty", "spaces", "newlines"])
def test_blank_output_is_task_execution(
    service: PromptEnhancementService, text: str
) -> None:
    """Empty text has no directives, so rule 2 rejects it. Convenient: the
    retry loop treats a model returning nothing the same as a model answering the
    question."""
    assert service.is_task_execution(text, ORIGINAL) is True


def test_the_original_prompt_argument_does_not_affect_the_verdict(
    service: PromptEnhancementService,
) -> None:
    """``original_prompt`` is accepted but never read.

    Pinned so the signature is not mistaken for a similarity check between the
    output and the request — the detector looks only at the output's shape.
    """
    text = "You are an expert. Objective: do the work."

    assert service.is_task_execution(text, ORIGINAL) is False
    assert service.is_task_execution(text, "") is False
    assert service.is_task_execution(text, text) is False


def test_the_stub_default_output_is_not_task_execution() -> None:
    """The invariant the whole integration tier rests on.

    ``DEFAULT_OPTIMIZED_PROMPT`` is what ``StubLLMProvider`` returns for every
    enhancement. If it ever tripped this detector, the blocking path would spend
    ``max_retries`` rounds of ``2 ** attempt`` backoff and then fail — every
    enhancement test would time out rather than fail with a useful message. So it
    is asserted here, at the cheapest tier.
    """
    service = PromptEnhancementService(
        llm_provider=StubLLMProvider(), retrieval_service=None  # type: ignore[arg-type]
    )

    assert service.is_task_execution(DEFAULT_OPTIMIZED_PROMPT, ORIGINAL) is False
    assert not DEFAULT_OPTIMIZED_PROMPT.lower().startswith(CONVERSATIONAL_HEADERS)
    assert any(d in DEFAULT_OPTIMIZED_PROMPT.lower() for d in DIRECTIVES)


# ─────────────────────────────────────────────────────────────────────────────
# _clean_enhanced_output — preamble markers
# ─────────────────────────────────────────────────────────────────────────────


def test_clean_output_returns_text_unchanged_when_there_is_nothing_to_strip(
    service: PromptEnhancementService,
) -> None:
    """The stub's output deliberately contains no marker and no fence, which is
    why integration tests can compare responses against it byte for byte."""
    assert service._clean_enhanced_output(DEFAULT_OPTIMIZED_PROMPT) == DEFAULT_OPTIMIZED_PROMPT


def test_surrounding_whitespace_is_always_stripped(
    service: PromptEnhancementService,
) -> None:
    assert service._clean_enhanced_output("\n\n  You are an expert.  \n\n") == "You are an expert."


@pytest.mark.parametrize(
    "marker",
    ["ENHANCED PROMPT:", "ENHANCED PROMPT", "Enhanced Prompt:", "enhanced prompt:", "Enhanced prompt:"],
    ids=["upper-colon", "upper-no-colon", "title-colon", "lower-colon", "sentence-colon"],
)
def test_a_leading_marker_is_removed(
    service: PromptEnhancementService, marker: str
) -> None:
    """The first three spellings match the explicit ``markers`` list; the last two
    are caught by the case-insensitive fallback in the ``for``/``else``."""
    assert service._clean_enhanced_output(f"{marker}\nYou are an expert.") == "You are an expert."


def test_everything_before_the_marker_is_discarded(
    service: PromptEnhancementService,
) -> None:
    """The whole point: models prepend an explanation, and the marker is where the
    actual deliverable starts."""
    text = "Certainly! I have rewritten it.\n\nENHANCED PROMPT:\nYou are an expert."

    assert service._clean_enhanced_output(text) == "You are an expert."


def test_only_the_first_marker_occurrence_is_cut(
    service: PromptEnhancementService,
) -> None:
    """``find`` plus ``break`` — a second marker inside the body is left in place
    rather than the last one winning."""
    text = "ENHANCED PROMPT: You are an expert.\nENHANCED PROMPT: a second copy."

    assert service._clean_enhanced_output(text) == (
        "You are an expert.\nENHANCED PROMPT: a second copy."
    )


def test_the_colonless_marker_is_matched_before_the_title_cased_one(
    service: PromptEnhancementService,
) -> None:
    """Marker order is ``["ENHANCED PROMPT:", "ENHANCED PROMPT", "Enhanced Prompt:"]``.

    So in a reply carrying both spellings, ``ENHANCED PROMPT`` (no colon) matches
    at index 0 and the ``Enhanced Prompt:`` further down is never reached — it
    stays in the body. Pinned because it is the kind of ordering that changes by
    accident when a marker is added to the list.
    """
    text = "ENHANCED PROMPT\nYou are an expert.\nEnhanced Prompt: leftover."

    assert service._clean_enhanced_output(text) == (
        "You are an expert.\nEnhanced Prompt: leftover."
    )


def test_the_case_insensitive_fallback_only_runs_when_no_exact_marker_matched(
    service: PromptEnhancementService,
) -> None:
    """``for``/``else``: because ``ENHANCED PROMPT`` matches, the lowercase
    occurrence earlier in the string is not used as the cut point."""
    text = "enhanced prompt: ignored preamble\nENHANCED PROMPT: You are an expert."

    assert service._clean_enhanced_output(text) == "You are an expert."


def test_a_marker_with_no_content_after_it_yields_an_empty_string(
    service: PromptEnhancementService,
) -> None:
    """Which rule 2 of ``is_task_execution`` then rejects, so the retry loop runs
    instead of an empty prompt being stored."""
    cleaned = service._clean_enhanced_output("ENHANCED PROMPT:")

    assert cleaned == ""
    assert service.is_task_execution(cleaned, ORIGINAL) is True


# ─────────────────────────────────────────────────────────────────────────────
# _clean_enhanced_output — markdown fences
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fence", ["```", "```text", "```markdown", "```json"], ids=["bare", "text", "markdown", "json"]
)
def test_a_wrapping_code_fence_is_removed(
    service: PromptEnhancementService, fence: str
) -> None:
    """The opening fence is dropped by cutting to the first newline, so any
    language tag goes with it."""
    text = f"{fence}\nYou are an expert.\n```"

    assert service._clean_enhanced_output(text) == "You are an expert."


def test_a_trailing_fence_without_an_opening_one_is_removed(
    service: PromptEnhancementService,
) -> None:
    assert service._clean_enhanced_output("You are an expert.\n```") == "You are an expert."


def test_a_single_line_fenced_response_keeps_its_opening_fence(
    service: PromptEnhancementService,
) -> None:
    """Documented quirk, pinning current behaviour.

    The opening fence is removed by finding the first newline; with no newline
    there is nothing to cut to, so the ``` prefix survives while the closing one
    is still stripped. A one-line fenced reply therefore reaches the user with a
    stray fence.

    Low impact — enhanced prompts are multi-line by construction — but it is the
    reason the guard reads ``if first_nl != -1``.
    """
    assert service._clean_enhanced_output("```You are an expert.```") == "```You are an expert."


def test_an_inner_fence_is_left_alone(service: PromptEnhancementService) -> None:
    """Only a fence at the very start or very end is touched, so a prompt that
    legitimately contains an example block keeps it."""
    text = "You are an expert.\n\nReturn:\n```json\n{}\n```\n\nObjective: comply."

    assert service._clean_enhanced_output(text) == text


def test_the_marker_is_stripped_before_the_fence(
    service: PromptEnhancementService,
) -> None:
    """Ordering matters: the marker cut runs first, which is what exposes the
    fence at index 0 so it can then be removed."""
    text = "ENHANCED PROMPT:\n```\nYou are an expert.\n```"

    assert service._clean_enhanced_output(text) == "You are an expert."


# ─────────────────────────────────────────────────────────────────────────────
# _clean_enhanced_output — defensive input handling
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    ["", None, 0, [], {}, 123, 4.5, True],
    ids=["empty", "none", "zero", "list", "dict", "int", "float", "bool"],
)
def test_falsy_and_non_string_input_becomes_an_empty_string(
    service: PromptEnhancementService, value: Any
) -> None:
    """``if not text or not isinstance(text, str)`` — a provider returning a
    non-string never raises here, it degrades to empty and is then caught by
    ``is_task_execution``."""
    assert service._clean_enhanced_output(value) == ""


def test_whitespace_only_input_becomes_an_empty_string(
    service: PromptEnhancementService,
) -> None:
    """Truthy, so it reaches the body and is emptied by the final ``strip``."""
    assert service._clean_enhanced_output("   \n\t  ") == ""


# ─────────────────────────────────────────────────────────────────────────────
# The two guards composed, as enhance_prompt uses them
# ─────────────────────────────────────────────────────────────────────────────


def test_cleaning_rescues_a_reply_the_detector_would_have_rejected(
    service: PromptEnhancementService,
) -> None:
    """The reason order matters in ``enhance_prompt``.

    Raw, this reply opens with "Here is" and rule 1 rejects it. Cleaned, the
    preamble is gone and the directive-shaped prompt underneath passes.
    """
    raw = "Here is the enhanced prompt:\n\nYou are an expert. Objective: comply."

    assert service.is_task_execution(raw, ORIGINAL) is True

    cleaned = service._clean_enhanced_output(raw)
    assert cleaned == "You are an expert. Objective: comply."
    assert service.is_task_execution(cleaned, ORIGINAL) is False


def test_cleaning_cannot_rescue_a_reply_that_answered_the_question(
    service: PromptEnhancementService,
) -> None:
    """No marker to cut at and no directive language, so it stays rejected and the
    retry loop is entitled to run."""
    raw = "Here is the answer: our ideal customer is a mid-market operations lead."

    cleaned = service._clean_enhanced_output(raw)
    assert cleaned == raw
    assert service.is_task_execution(cleaned, ORIGINAL) is True


def test_trailing_why_this_version_is_stronger_is_stripped(
    service: PromptEnhancementService,
) -> None:
    raw = (
        "ENHANCED PROMPT:\n"
        "You are an expert copywriter. Objective: write landing page.\n\n"
        "WHY THIS VERSION IS STRONGER:\n"
        "This version is stronger because it defines constraints."
    )
    cleaned = service._clean_enhanced_output(raw)
    assert cleaned == "You are an expert. Objective: write landing page."
    assert "WHY THIS VERSION IS STRONGER" not in cleaned


def test_trailing_why_this_version_is_stronger_with_markdown_headers(
    service: PromptEnhancementService,
) -> None:
    raw = (
        "You are an expert copywriter. Objective: write landing page.\n\n"
        "### WHY THIS VERSION IS STRONGER\n"
        "1. It is more specific."
    )
    cleaned = service._clean_enhanced_output(raw)
    assert cleaned == "You are an expert. Objective: write landing page."
    assert "WHY THIS VERSION IS STRONGER" not in cleaned


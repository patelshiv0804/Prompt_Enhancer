"""Unit tests for app/services/prompt_builder.py.

The builder is the last thing that shapes what the model sees, and its output is
compared byte-for-byte in the integration tier (the stub LLM echoes structure
back), so the section headers, their order and the separator all matter.
"""

from __future__ import annotations

import json

import pytest

from app.services.prompt_builder import _DEPTH_INSTRUCTIONS, PromptBuilder

pytestmark = pytest.mark.unit

SEPARATOR = "\n\n"


@pytest.fixture
def builder() -> PromptBuilder:
    return PromptBuilder()


def sections(prompt: str) -> list[str]:
    return prompt.split(SEPARATOR)


# ─────────────────────────────────────────────────────────────────────────────
# Structure
# ─────────────────────────────────────────────────────────────────────────────


def test_four_sections_in_a_fixed_order(builder: PromptBuilder) -> None:
    prompt = builder.build_final_prompt(
        role="creator", mode="general", rendered_template="TEMPLATE BODY"
    )

    headers = [section.splitlines()[0] for section in sections(prompt)]
    assert headers == [
        "=== SYSTEM INSTRUCTIONS ===",
        "=== TARGET PROFILE ===",
        "=== ENHANCEMENT DEPTH ===",
        "=== RETRIEVED ENHANCEMENT TEMPLATE ===",
    ]


def test_the_style_section_is_inserted_before_the_template(builder: PromptBuilder) -> None:
    prompt = builder.build_final_prompt(
        role="creator",
        mode="general",
        rendered_template="TEMPLATE BODY",
        style_attributes={"tone": "direct"},
    )

    headers = [section.splitlines()[0] for section in sections(prompt)]
    assert headers == [
        "=== SYSTEM INSTRUCTIONS ===",
        "=== TARGET PROFILE ===",
        "=== ENHANCEMENT DEPTH ===",
        "=== STYLE PROFILE ATTRIBUTES ===",
        "=== RETRIEVED ENHANCEMENT TEMPLATE ===",
    ]


@pytest.mark.parametrize("empty", [None, {}], ids=["none", "empty-dict"])
def test_no_style_section_when_there_are_no_attributes(
    builder: PromptBuilder, empty: dict | None
) -> None:
    """The check is truthiness, so an empty dict is treated as absent."""
    prompt = builder.build_final_prompt(
        role="creator",
        mode="general",
        rendered_template="TEMPLATE BODY",
        style_attributes=empty,
    )

    assert "STYLE PROFILE ATTRIBUTES" not in prompt
    assert len(sections(prompt)) == 4


def test_style_attributes_are_serialised_as_indented_json(builder: PromptBuilder) -> None:
    attributes = {"tone": "direct", "avoid": ["hype", "filler"]}

    prompt = builder.build_final_prompt(
        role="creator",
        mode="general",
        rendered_template="TEMPLATE BODY",
        style_attributes=attributes,
    )

    style_section = next(s for s in sections(prompt) if "STYLE PROFILE" in s)
    payload = style_section.split("\n", 1)[1]
    assert json.loads(payload) == attributes
    assert json.dumps(attributes, indent=2) in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Content of each section
# ─────────────────────────────────────────────────────────────────────────────


def test_the_default_system_instructions_are_used_when_none_are_given(
    builder: PromptBuilder,
) -> None:
    prompt = builder.build_final_prompt(
        role="creator", mode="general", rendered_template="TEMPLATE BODY"
    )

    assert PromptBuilder.DEFAULT_SYSTEM_INSTRUCTIONS in prompt


def test_custom_system_instructions_replace_the_default(builder: PromptBuilder) -> None:
    """The retry path passes a strengthened block here after a task-execution slip."""
    prompt = builder.build_final_prompt(
        role="creator",
        mode="general",
        rendered_template="TEMPLATE BODY",
        system_instructions="  STRICTER RULES  ",
    )

    assert "STRICTER RULES" in prompt
    assert PromptBuilder.DEFAULT_SYSTEM_INSTRUCTIONS not in prompt
    assert prompt.startswith("=== SYSTEM INSTRUCTIONS ===\nSTRICTER RULES\n\n")


def test_an_empty_system_instructions_string_falls_back_to_the_default(
    builder: PromptBuilder,
) -> None:
    """``system_instructions or DEFAULT`` — an empty string is not an override."""
    prompt = builder.build_final_prompt(
        role="creator", mode="general", rendered_template="B", system_instructions=""
    )

    assert PromptBuilder.DEFAULT_SYSTEM_INSTRUCTIONS in prompt


def test_the_default_instructions_forbid_answering_the_request() -> None:
    """This wording is the only thing preventing the model from doing the task.

    ``PromptEnhancementService.is_task_execution`` is the detector; these
    instructions are the prevention. Both must stay aligned.
    """
    text = PromptBuilder.DEFAULT_SYSTEM_INSTRUCTIONS

    assert "NEVER answer" in text
    assert "Output ONLY the final enhanced prompt" in text


def test_role_and_mode_are_stripped_into_the_target_profile(
    builder: PromptBuilder,
) -> None:
    prompt = builder.build_final_prompt(
        role="  marketer  ", mode="  marketing  ", rendered_template="B"
    )

    assert "=== TARGET PROFILE ===\nRole: marketer\nMode: marketing" in prompt


def test_the_rendered_template_is_stripped(builder: PromptBuilder) -> None:
    prompt = builder.build_final_prompt(
        role="creator", mode="general", rendered_template="\n\n  BODY  \n\n"
    )

    assert prompt.endswith("=== RETRIEVED ENHANCEMENT TEMPLATE ===\nBODY")


def test_role_and_mode_must_not_be_none(builder: PromptBuilder) -> None:
    """A documented precondition, not a nicety.

    ``PromptEnhancementService.enhance_prompt`` types ``role``/``mode`` as
    ``Optional[str]`` and forwards them unchanged. ``.strip()`` on ``None`` raises
    ``AttributeError``, which the retry loop does not catch — so whatever calls
    the enhancement service is responsible for supplying both.
    """
    with pytest.raises(AttributeError):
        builder.build_final_prompt(role=None, mode="general", rendered_template="B")  # type: ignore[arg-type]

    with pytest.raises(AttributeError):
        builder.build_final_prompt(role="creator", mode=None, rendered_template="B")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# Enhancement depth
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("level", sorted(_DEPTH_INSTRUCTIONS))
def test_each_known_level_injects_its_own_directive(
    builder: PromptBuilder, level: str
) -> None:
    prompt = builder.build_final_prompt(
        role="creator", mode="general", rendered_template="B", enhancement_level=level
    )

    assert _DEPTH_INSTRUCTIONS[level] in prompt


def test_standard_is_the_default_level(builder: PromptBuilder) -> None:
    prompt = builder.build_final_prompt(
        role="creator", mode="general", rendered_template="B"
    )

    assert _DEPTH_INSTRUCTIONS["standard"] in prompt


@pytest.mark.parametrize("level", ["", "STANDARD", "extreme", "none"])
def test_an_unknown_level_silently_falls_back_to_standard(
    builder: PromptBuilder, level: str
) -> None:
    """No validation happens here, so an unrecognised level is not an error —
    including the plausible-looking uppercase spelling."""
    prompt = builder.build_final_prompt(
        role="creator", mode="general", rendered_template="B", enhancement_level=level
    )

    assert _DEPTH_INSTRUCTIONS["standard"] in prompt


def test_the_three_depth_levels_are_distinct(builder: PromptBuilder) -> None:
    """If two levels produced the same directive, the feature would be inert."""
    assert len(set(_DEPTH_INSTRUCTIONS.values())) == 3
    assert set(_DEPTH_INSTRUCTIONS) == {"minimal", "standard", "deep"}


# ─────────────────────────────────────────────────────────────────────────────
# Determinism — the property the whole test suite leans on
# ─────────────────────────────────────────────────────────────────────────────


def test_identical_inputs_produce_identical_output(builder: PromptBuilder) -> None:
    kwargs = {
        "role": "creator",
        "mode": "general",
        "rendered_template": "BODY",
        "style_attributes": {"tone": "direct", "avoid": ["hype"]},
        "enhancement_level": "deep",
    }

    assert builder.build_final_prompt(**kwargs) == builder.build_final_prompt(**kwargs)


def test_the_builder_holds_no_per_call_state() -> None:
    """It is constructed once per service instance and reused across requests."""
    shared = PromptBuilder()
    first = shared.build_final_prompt(role="a", mode="b", rendered_template="C")
    shared.build_final_prompt(
        role="x", mode="y", rendered_template="Z", style_attributes={"k": "v"}
    )

    assert shared.build_final_prompt(role="a", mode="b", rendered_template="C") == first


# ─────────────────────────────────────────────────────────────────────────────
# Target Model Directives (Multi-Model Prompt Engineering)
# ─────────────────────────────────────────────────────────────────────────────


def test_target_model_deepseek_directive_injected(builder: PromptBuilder) -> None:
    msgs = builder.build_messages(
        role="developer",
        mode="backend",
        rendered_template="API Spec",
        target_model="DeepSeek",
    )
    assert "DEEPSEEK-R1" in msgs["system"]
    assert "<context>" in msgs["system"]
    assert "think step by step" in msgs["system"]


def test_target_model_perplexity_directive_injected(builder: PromptBuilder) -> None:
    msgs = builder.build_messages(
        role="researcher",
        mode="academic",
        rendered_template="Literature Review",
        target_model="Perplexity",
    )
    assert "PERPLEXITY AI" in msgs["system"]
    assert "Search Directives" in msgs["system"]


def test_target_model_higgsfield_directive_injected(builder: PromptBuilder) -> None:
    msgs = builder.build_messages(
        role="creator",
        mode="cinematic",
        rendered_template="Astronaut on Mars",
        target_model="Higgsfield",
    )
    assert "HIGGSFIELD AI" in msgs["system"]
    assert "4-Layer Cinematic Video Direction Architecture" in msgs["system"]


def test_target_model_none_injects_no_directive(builder: PromptBuilder) -> None:
    msgs_none = builder.build_messages(
        role="marketer",
        mode="strategy",
        rendered_template="Campaign",
        target_model="None",
    )
    assert "TARGET AI MODEL RULES" not in msgs_none["system"]

    msgs_null = builder.build_messages(
        role="marketer",
        mode="strategy",
        rendered_template="Campaign",
        target_model=None,
    )
    assert "TARGET AI MODEL RULES" not in msgs_null["system"]


def test_adaptive_messages_with_target_model(builder: PromptBuilder) -> None:
    msgs = builder.build_adaptive_messages(
        raw_prompt="Camera dolly in on Mars base",
        target_model="Higgsfield",
    )
    assert "HIGGSFIELD AI" in msgs["system"]
    assert "4-Layer Cinematic Video Direction Architecture" in msgs["system"]
    assert "Camera dolly in on Mars base" in msgs["user"]


def test_builder_strips_why_this_version_is_stronger_from_template(builder: PromptBuilder) -> None:
    template_with_aux = (
        "STEP 4 — Output the enhanced prompt\n"
        "Present the result in this structure:\n"
        "ENHANCED PROMPT (the complete prompt)\n"
        "WHY THIS VERSION IS STRONGER (2-3 sentences naming the failure this avoids)\n"
        "Do not generate the actual creative piece."
    )
    msgs = builder.build_messages(
        role="writer",
        mode="creative",
        rendered_template=template_with_aux,
    )
    assert "WHY THIS VERSION IS STRONGER" not in msgs["user"]
    assert "WHY THIS VERSION IS STRONGER" in builder.DEFAULT_SYSTEM_INSTRUCTIONS
    assert "ENHANCED PROMPT (the complete prompt)" in msgs["user"]


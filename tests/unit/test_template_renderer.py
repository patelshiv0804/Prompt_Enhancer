"""Unit tests for app/services/template_renderer.py.

The renderer is the last step before user text is handed to the LLM, so its
failure modes are user-visible: an unresolved placeholder aborts an enhancement
request. Two of the tests below pin behaviour that looks like a defect; each says
so explicitly rather than quietly encoding it as correct.
"""

from __future__ import annotations

import pytest

from app.services.exceptions import TemplateRenderException
from app.services.template_renderer import TemplateRenderer

pytestmark = pytest.mark.unit


@pytest.fixture
def renderer() -> TemplateRenderer:
    return TemplateRenderer()


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST — the one required variable
# ─────────────────────────────────────────────────────────────────────────────


def test_request_is_filled_from_the_user_prompt(renderer: TemplateRenderer) -> None:
    result = renderer.render(
        template_body="Task: {REQUEST}", user_prompt="write a haiku about testing"
    )

    assert result == "Task: write a haiku about testing"


def test_an_explicit_request_variable_wins_over_the_user_prompt(
    renderer: TemplateRenderer,
) -> None:
    result = renderer.render(
        template_body="Task: {REQUEST}",
        user_prompt="from the prompt",
        variables={"REQUEST": "from the variables"},
    )

    assert result == "Task: from the variables"


@pytest.mark.parametrize("key", ["request", "Request", "  request  ", "REQUEST "])
def test_variable_keys_are_normalised(renderer: TemplateRenderer, key: str) -> None:
    """Keys are upper-cased and stripped, so callers can pass any casing."""
    result = renderer.render(
        template_body="Task: {REQUEST}", user_prompt="", variables={key: "supplied"}
    )

    assert result == "Task: supplied"


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t "])
def test_a_blank_prompt_with_no_request_variable_is_rejected(
    renderer: TemplateRenderer, prompt: str
) -> None:
    with pytest.raises(TemplateRenderException, match="REQUEST is missing or empty"):
        renderer.render(template_body="Task: {REQUEST}", user_prompt=prompt)


def test_the_blank_prompt_check_runs_before_the_body_is_scanned(
    renderer: TemplateRenderer,
) -> None:
    """A body with no placeholders at all still requires a non-blank prompt.

    Ordering, not an accident: the guard sits above the placeholder scan. Pinned
    because a caller reasonably expects a template that never mentions
    ``{REQUEST}`` to render regardless of the prompt.
    """
    with pytest.raises(TemplateRenderException, match="REQUEST is missing or empty"):
        renderer.render(template_body="A body with no placeholders.", user_prompt="")


def test_a_whitespace_only_request_variable_is_accepted(
    renderer: TemplateRenderer,
) -> None:
    """The emptiness check only guards ``user_prompt``; a supplied variable is
    trusted as-is."""
    result = renderer.render(
        template_body="[{REQUEST}]", user_prompt="", variables={"REQUEST": "   "}
    )

    assert result == "[   ]"


# ─────────────────────────────────────────────────────────────────────────────
# Optional variables and their fallbacks
# ─────────────────────────────────────────────────────────────────────────────


def test_language_defaults_to_english(renderer: TemplateRenderer) -> None:
    result = renderer.render(
        template_body="Respond in {LANGUAGE}. Task: {REQUEST}", user_prompt="hello"
    )

    assert result == "Respond in English. Task: hello"


def test_a_supplied_language_overrides_the_default(renderer: TemplateRenderer) -> None:
    result = renderer.render(
        template_body="Respond in {LANGUAGE}.",
        user_prompt="hello",
        variables={"LANGUAGE": "Hindi"},
    )

    assert result == "Respond in Hindi."


def test_any_other_unknown_placeholder_becomes_not_applicable(
    renderer: TemplateRenderer,
) -> None:
    result = renderer.render(
        template_body="Audience: {AUDIENCE}. Tone: {TONE_OF_VOICE}.",
        user_prompt="hello",
    )

    assert result == "Audience: N/A. Tone: N/A."


def test_placeholders_may_contain_digits_and_underscores(
    renderer: TemplateRenderer,
) -> None:
    result = renderer.render(
        template_body="{EXAMPLE_1} then {EXAMPLE_2}",
        user_prompt="hello",
        variables={"EXAMPLE_1": "first", "EXAMPLE_2": "second"},
    )

    assert result == "first then second"


def test_every_occurrence_of_a_placeholder_is_replaced(
    renderer: TemplateRenderer,
) -> None:
    result = renderer.render(template_body="{REQUEST}/{REQUEST}", user_prompt="x")

    assert result == "x/x"


def test_lowercase_placeholders_are_left_untouched(renderer: TemplateRenderer) -> None:
    """The scan is ``[A-Z_0-9]+``, so ``{role}`` is neither substituted nor
    reported as unresolved — it reaches the LLM verbatim.

    This is why ``tests/factories.make_template`` uses ``{{role}}``-style bodies:
    they pass straight through the renderer.
    """
    result = renderer.render(
        template_body="You are a {role}. Task: {REQUEST}",
        user_prompt="hello",
        variables={"role": "editor"},
    )

    assert result == "You are a {role}. Task: hello"


def test_unrelated_braces_survive(renderer: TemplateRenderer) -> None:
    result = renderer.render(
        template_body='Return JSON like {"key": "value"}. Task: {REQUEST}',
        user_prompt="hello",
    )

    assert result == 'Return JSON like {"key": "value"}. Task: hello'


# ─────────────────────────────────────────────────────────────────────────────
# The leftover-placeholder guard
# ─────────────────────────────────────────────────────────────────────────────


def test_a_placeholder_inside_the_users_own_prompt_aborts_the_render(
    renderer: TemplateRenderer,
) -> None:
    """KNOWN DEFECT — pinning current behaviour.

    Substitution happens first, then the whole rendered body is re-scanned for
    ``{UPPERCASE}`` patterns. Any such token in the *user's* text is therefore
    read as an unresolved template variable, and the request fails. A user asking
    "explain the {TODO} macro" cannot be served.

    The scan should run against the template body's own unresolved placeholders,
    not against substituted content. Invert this test if that is fixed.
    """
    with pytest.raises(TemplateRenderException, match="Unresolved placeholders"):
        renderer.render(
            template_body="Task: {REQUEST}",
            user_prompt="explain the {TODO} macro",
        )


def test_the_same_hazard_applies_to_supplied_variable_values(
    renderer: TemplateRenderer,
) -> None:
    """Same root cause as above, reached through ``variables`` instead."""
    with pytest.raises(TemplateRenderException, match="Unresolved placeholders"):
        renderer.render(
            template_body="Audience: {AUDIENCE}",
            user_prompt="hello",
            variables={"AUDIENCE": "people who write {CODE}"},
        )


def test_the_exception_names_the_unresolved_placeholders(
    renderer: TemplateRenderer,
) -> None:
    with pytest.raises(TemplateRenderException) as exc_info:
        renderer.render(template_body="{REQUEST}", user_prompt="a {FIRST} and a {SECOND}")

    message = str(exc_info.value)
    assert "FIRST" in message
    assert "SECOND" in message


def test_variables_none_is_equivalent_to_an_empty_mapping(
    renderer: TemplateRenderer,
) -> None:
    assert renderer.render("{REQUEST}", "x", None) == renderer.render("{REQUEST}", "x", {})


def test_the_caller_s_variables_dict_is_not_mutated(renderer: TemplateRenderer) -> None:
    """``enhance_prompt`` passes the request's variables straight through and
    reuses them across retry attempts."""
    variables = {"AUDIENCE": "engineers"}

    renderer.render(template_body="{AUDIENCE} {REQUEST}", user_prompt="x", variables=variables)

    assert variables == {"AUDIENCE": "engineers"}

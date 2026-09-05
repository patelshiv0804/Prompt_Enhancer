"""Integration tests for ``app/api/v1/enhancement.py``.

The deterministic route through this module is to pass an explicit
``template_id``. That bypasses semantic template retrieval and pins the test to
rows it created itself rather than to whatever the cloned corpus happens to
contain today.

Two route-shape details matter enough to encode directly.

**Blocking enhancement persists immediately and analyzes later.** The initial
response returns with ``analysis=None`` and schedules deep analysis in the
background.

**Streaming enhancement front-loads only the failures that deserve a real HTTP
status.** Once the event stream starts, validation and LLM/persistence problems
surface as SSE ``error`` frames instead of 4xx/5xx responses.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt, PromptVersion
from tests import factories
from tests.stubs.llm import (
    DEFAULT_OPTIMIZED_PROMPT,
    STUB_ANALYSIS_GRADE,
    STUB_ANALYSIS_OVERALL_SCORE,
    STUB_CLASSIFICATION_LEVEL,
    STUB_CLASSIFICATION_REASON,
    STUB_COMPARISON_GRADE_AFTER,
    STUB_COMPARISON_GRADE_BEFORE,
    StubLLMProvider,
)

pytestmark = pytest.mark.integration

ENHANCE = "/api/v1/enhance"
STREAM = "/api/v1/enhance/stream"
ANALYZE = "/api/v1/analyze"
COMPARE = "/api/v1/compare"
TOOLS = "/api/v1/tools/recommend"

GENERIC_400 = "An error occurred while processing your request. Please try again."
GENERIC_500 = "An internal server error occurred while processing your prompt."

# ``PromptClassificationService.classify`` short-circuits on three free static
# guards before it ever calls the LLM: ``len < 60`` → minimal, ``len > 800`` →
# deep, and any ``_DEEP_KEYWORDS`` hit → deep. This prompt clears all three, so
# classification actually reaches the stubbed provider and
# ``STUB_CLASSIFICATION_LEVEL`` is a meaningful expectation. Any test asserting
# the stub's level must use it — the short default prompt below resolves to
# ``minimal`` without the LLM being consulted at all.
CLASSIFIER_REACHING_PROMPT = (
    "Rewrite the announcement copy for our new mobile onboarding screen so that "
    "it reads warmly and mentions the free trial up front."
)


def enhance_payload(prompt: str = "Help me improve this launch plan.", **overrides: Any) -> dict[str, Any]:
    body = {
        "prompt": prompt,
        "role": "writer",
        "mode": "concise",
    }
    body.update(overrides)
    return body


async def collect_sse(response) -> list[tuple[str, dict[str, Any]]]:
    chunks: list[str] = []
    async for text in response.aiter_text():
        chunks.append(text)
    raw = "".join(chunks)

    events: list[tuple[str, dict[str, Any]]] = []
    for frame in raw.strip().split("\n\n"):
        if not frame.strip():
            continue
        event = None
        data = None
        for line in frame.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if event is not None and data is not None:
            events.append((event, data))
    return events


# ─────────────────────────────────────────────────────────────────────────────
# POST /enhance
# ─────────────────────────────────────────────────────────────────────────────


async def test_blocking_enhancement_returns_the_expected_envelope_and_persists_prompt(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    template = await factories.create_template(
        db_session,
        role="writer",
        mode="concise",
        title="Launch Template",
    )
    # House rule 4: the enhancement commits, which expires every loaded
    # instance — ``template.id`` after the request is a sync lazy read.
    template_id = template.id
    await db_session.commit()

    response = await authed_client.post(
        ENHANCE,
        json=enhance_payload(
            prompt="Improve this launch prompt.",
            template_id=str(template_id),
        ),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == (
        "Prompt enhanced successfully. Detailed quality analysis is processing in background."
    )
    data = body["data"]
    assert data["original_prompt"] == "Improve this launch prompt."
    assert data["enhanced_prompt"] == DEFAULT_OPTIMIZED_PROMPT
    assert data["analysis"] is None
    assert data["comparison"] is None
    assert data["tool_recommendations"] is None
    assert data["template"] == {
        "id": str(template_id),
        "title": "Launch Template",
        "similarity": 1.0,
    }
    prompt_id = UUID(data["version"]["prompt_id"])
    assert data["version"]["version_number"] == 1

    db_session.expire_all()
    stored_prompt = await db_session.scalar(select(Prompt).where(Prompt.id == prompt_id))
    stored_version = await db_session.scalar(
        select(PromptVersion).where(PromptVersion.prompt_id == prompt_id)
    )
    assert stored_prompt is not None
    assert stored_prompt.user_id == account.id
    assert stored_prompt.template_id == template_id
    assert stored_prompt.original_prompt == "Improve this launch prompt."
    assert stored_version is not None
    assert stored_version.content == DEFAULT_OPTIMIZED_PROMPT
    assert stored_version.version_number == 1


async def test_manual_enhancement_level_wins_over_classifier(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    template = await factories.create_template(db_session)
    await db_session.commit()

    body = (
        await authed_client.post(
            ENHANCE,
            json=enhance_payload(
                template_id=str(template.id),
                enhancement_level="deep",
            ),
        )
    ).json()

    assert body["data"]["detected_level"] == "deep"
    assert body["data"]["level_reason"] == "Manually set to deep."


async def test_invalid_manual_enhancement_level_falls_back_to_classifier(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    template = await factories.create_template(db_session)
    template_id = str(template.id)
    await db_session.commit()

    body = (
        await authed_client.post(
            ENHANCE,
            json=enhance_payload(
                prompt=CLASSIFIER_REACHING_PROMPT,
                template_id=template_id,
                enhancement_level="sideways",
            ),
        )
    ).json()

    assert body["data"]["detected_level"] == STUB_CLASSIFICATION_LEVEL
    assert body["data"]["level_reason"] == STUB_CLASSIFICATION_REASON


@pytest.mark.parametrize(
    ("prompt", "expected_level", "expected_reason", "case"),
    [
        (
            "Fix my copy.",
            "minimal",
            "Prompt is short and focused.",
            "under-60-chars",
        ),
        (
            "Rewrite the welcome email. " + ("Keep the wording friendly. " * 32),
            "deep",
            "Prompt is long and likely complex.",
            "over-800-chars",
        ),
    ],
)
async def test_the_classifier_static_guards_answer_without_calling_the_llm(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    prompt: str,
    expected_level: str,
    expected_reason: str,
    case: str,
) -> None:
    """The three free heuristics in ``classify`` decide most real requests.

    Pinned because they are invisible from the API surface yet fully determine
    ``detected_level`` for short and long prompts — the stubbed LLM is never
    consulted, so a test that expects the stub's answer here would be asserting
    a code path that never runs.
    """
    template = await factories.create_template(db_session)
    template_id = str(template.id)
    await db_session.commit()

    body = (
        await authed_client.post(
            ENHANCE,
            json=enhance_payload(prompt=prompt, template_id=template_id),
        )
    ).json()

    assert body["data"]["detected_level"] == expected_level, case
    assert body["data"]["level_reason"] == expected_reason, case


@pytest.mark.parametrize(
    "keyword",
    ["plan", "strategy", "architecture", "system", "comprehensive",
     "detailed", "step-by-step", "roadmap", "framework", "in-depth"],
)
async def test_a_deep_keyword_forces_deep_without_calling_the_llm(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    keyword: str,
) -> None:
    """Every ``_DEEP_KEYWORDS`` member escalates a mid-length prompt to deep.

    The match is a plain case-insensitive substring test, so this also documents
    that ``"planning"`` or ``"systemic"`` would trigger it just as ``"plan"``
    does.
    """
    template = await factories.create_template(db_session)
    template_id = str(template.id)
    await db_session.commit()

    prompt = f"Rewrite the onboarding copy and include a {keyword} for the reader to follow."
    assert 60 <= len(prompt) <= 800, prompt

    body = (
        await authed_client.post(
            ENHANCE,
            json=enhance_payload(prompt=prompt, template_id=template_id),
        )
    ).json()

    assert body["data"]["detected_level"] == "deep", keyword
    assert body["data"]["level_reason"] == "Prompt contains strategic or complex keywords."


async def test_owned_style_profile_can_be_applied(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    template = await factories.create_template(db_session)
    style = await factories.create_style_profile(
        db_session,
        account=account,
        attributes={"tone": "warm", "voice": "direct"},
    )
    await db_session.commit()

    response = await authed_client.post(
        ENHANCE,
        json=enhance_payload(
            template_id=str(template.id),
            apply_style=True,
            style_profile_id=str(style.id),
        ),
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["enhanced_prompt"] == DEFAULT_OPTIMIZED_PROMPT


async def test_other_users_style_profile_is_hidden_but_as_a_400_not_a_404(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """KNOWN DEFECT — the route's own ``HTTPException(404)`` is downgraded to 400.

    ``/enhance`` raises ``HTTPException(status_code=404, detail="Style profile
    not found.")`` for a profile that is missing, soft-deleted, or owned by
    another user — but that raise happens *inside* the handler's ``try``, and the
    blanket ``except Exception: raise map_service_error(exc)`` does not
    special-case ``HTTPException``. So the status and the detail message the
    route wrote are both discarded in favour of the generic 400.

    The confidentiality property still holds — an unowned profile is refused and
    nothing about it is disclosed — so this is a contract defect, not a leak.
    Its streaming sibling has ``except HTTPException: raise`` and does preserve
    the 404, which is what makes this an oversight rather than a design choice.
    """
    template = await factories.create_template(db_session)
    stranger = await factories.create_account(db_session)
    style = await factories.create_style_profile(db_session, account=stranger)
    template_id, style_id = str(template.id), str(style.id)
    await db_session.commit()

    unowned = await authed_client.post(
        ENHANCE,
        json=enhance_payload(
            template_id=template_id,
            apply_style=True,
            style_profile_id=style_id,
        ),
    )
    unknown = await authed_client.post(
        ENHANCE,
        json=enhance_payload(
            template_id=template_id,
            apply_style=True,
            style_profile_id=str(uuid4()),
        ),
    )

    assert unowned.status_code == 400
    assert unknown.status_code == 400
    assert unowned.json() == {"detail": GENERIC_400}
    assert unknown.json() == {"detail": GENERIC_400}


async def test_unknown_template_override_is_a_404(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.post(
        ENHANCE,
        json=enhance_payload(template_id=str(uuid4())),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Requested resource or matching template was not found."


async def test_blocking_enhancement_requires_authentication(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    template = await factories.create_template(db_session)
    await db_session.commit()

    response = await client.post(
        ENHANCE,
        json=enhance_payload(template_id=str(template.id)),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


# ─────────────────────────────────────────────────────────────────────────────
# POST /enhance/stream
# ─────────────────────────────────────────────────────────────────────────────


async def test_streaming_enhancement_emits_meta_tokens_and_done_and_persists_prompt(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    stub_llm: StubLLMProvider,
) -> None:
    template = await factories.create_template(
        db_session,
        role="writer",
        mode="concise",
        title="Streaming Template",
    )
    stub_llm.set_stream_chunks(["You are an expert assistant.", "\nObjective: stream this prompt."])
    template_id = template.id
    await db_session.commit()

    async with authed_client.stream(
        "POST",
        STREAM,
        json=enhance_payload(
            prompt=CLASSIFIER_REACHING_PROMPT,
            template_id=str(template_id),
        ),
    ) as response:
        events = await collect_sse(response)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [event for event, _data in events] == ["meta", "token", "token", "done"]

    meta = events[0][1]
    assert meta["template"] == {
        "id": str(template_id),
        "title": "Streaming Template",
        "similarity": 1.0,
    }
    assert meta["detected_level"] == STUB_CLASSIFICATION_LEVEL
    assert meta["level_reason"] == STUB_CLASSIFICATION_REASON

    done = events[-1][1]
    assert done["original_prompt"] == CLASSIFIER_REACHING_PROMPT
    assert done["enhanced_prompt"] == "You are an expert assistant.\nObjective: stream this prompt."
    prompt_id = UUID(done["version"]["prompt_id"])
    assert done["version"]["version_number"] == 1

    db_session.expire_all()
    stored_prompt = await db_session.scalar(select(Prompt).where(Prompt.id == prompt_id))
    assert stored_prompt is not None
    assert stored_prompt.original_prompt == CLASSIFIER_REACHING_PROMPT


async def test_streaming_unknown_template_fails_before_the_stream_starts(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.post(
        STREAM,
        json=enhance_payload(template_id=str(uuid4())),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Requested resource or matching template was not found."


async def test_streaming_empty_prompt_becomes_an_sse_error_frame(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    template = await factories.create_template(db_session)
    await db_session.commit()

    async with authed_client.stream(
        "POST",
        STREAM,
        json=enhance_payload(prompt="   ", template_id=str(template.id)),
    ) as response:
        events = await collect_sse(response)

    assert response.status_code == 200
    assert events == [("error", {"detail": "Prompt content cannot be empty."})]


async def test_streaming_requires_authentication(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    template = await factories.create_template(db_session)
    await db_session.commit()

    response = await client.post(
        STREAM,
        json=enhance_payload(template_id=str(template.id)),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


# ─────────────────────────────────────────────────────────────────────────────
# POST /analyze
# ─────────────────────────────────────────────────────────────────────────────


async def test_analyze_returns_the_stubbed_weighted_analysis(
    client: AsyncClient,
) -> None:
    response = await client.post(ANALYZE, json={"prompt": "Analyze this prompt please."})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_score"] == STUB_ANALYSIS_OVERALL_SCORE
    assert body["grade"] == STUB_ANALYSIS_GRADE
    assert body["summary"] == "Deterministic stub analysis."
    assert set(body["dimensions"]) == {
        "clarity",
        "context",
        "role_definition",
        "output_format",
        "constraints",
        "examples",
    }


async def test_analyze_empty_prompt_is_a_500(
    client: AsyncClient,
) -> None:
    response = await client.post(ANALYZE, json={"prompt": ""})

    assert response.status_code == 500
    assert response.json()["detail"] == GENERIC_500


# ─────────────────────────────────────────────────────────────────────────────
# POST /compare
# ─────────────────────────────────────────────────────────────────────────────


async def test_compare_returns_the_stubbed_comparison_payload(
    client: AsyncClient,
) -> None:
    response = await client.post(
        COMPARE,
        json={
            "original_prompt": "Write a launch note.",
            "enhanced_prompt": "You are a launch strategist. Write a structured launch note.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quality_delta"] == 4.0
    assert body["summary"]["grade_improvement"] == (
        f"{STUB_COMPARISON_GRADE_BEFORE} to {STUB_COMPARISON_GRADE_AFTER}"
    )
    assert body["improvements"] == ["Added an explicit role.", "Added output constraints."]


async def test_compare_empty_fields_are_a_500(
    client: AsyncClient,
) -> None:
    response = await client.post(
        COMPARE,
        json={"original_prompt": "", "enhanced_prompt": ""},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == GENERIC_500


# ─────────────────────────────────────────────────────────────────────────────
# POST /tools/recommend
# ─────────────────────────────────────────────────────────────────────────────


async def test_recommend_tools_returns_three_ranked_tools(
    client: AsyncClient,
) -> None:
    response = await client.post(
        TOOLS,
        json={"prompt": "Need help with coding a backend service.", "mode": "Coding"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"matched_task", "match_type", "match_confidence", "tools"}
    assert len(body["tools"]) == 3
    assert [tool["rank"] for tool in body["tools"]] == [1, 2, 3]
    assert all(tool["name"] for tool in body["tools"])


async def test_recommend_tools_request_validation_happens_in_fastapi(
    client: AsyncClient,
) -> None:
    response = await client.post(TOOLS, json={})

    assert response.status_code == 422

"""Integration tests for the semantic-search endpoint on ``/api/v1/prompts``.

This file covers ``POST /prompts/search`` — the prompt-intelligence route that
survives beside the vault itself.

**``POST /prompts/search`` forces the caller's own user id.** The route ignores
any client-supplied ``user_id`` and passes ``str(user_id)`` down into the vector
query, so search results stay inside the caller's own corpus.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests import factories

pytestmark = pytest.mark.integration

SEARCH = "/api/v1/prompts/search"

GENERIC_400 = "An error occurred while processing your request. Please try again."
GENERIC_500 = "An internal server error occurred while processing your prompt."


def search_payload(prompt: str = "optimize a postgres query", **overrides: Any) -> dict[str, Any]:
    body = {"prompt": prompt}
    body.update(overrides)
    return body


# ─────────────────────────────────────────────────────────────────────────────
# POST /prompts/search
# ─────────────────────────────────────────────────────────────────────────────


async def test_semantic_search_returns_the_expected_envelope_and_fields(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(
        db_session,
        account=account,
        title="Query Tuning",
        original_prompt="optimize a postgres query",
    )
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.post(SEARCH, json=search_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Semantic search complete."
    match = body["results"][0]
    assert match["prompt_id"] == prompt_id
    assert match["title"] == "Query Tuning"
    assert match["original_prompt"] == "optimize a postgres query"
    assert match["similarity_score"] == pytest.approx(1.0, abs=1e-6)
    assert set(match) >= {
        "prompt_id",
        "title",
        "original_prompt",
        "similarity_score",
        "old_analysis",
        "new_analysis",
        "grade",
        "created_at",
    }


async def test_semantic_search_is_scoped_to_the_callers_own_prompts(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    mine = await factories.create_prompt(
        db_session,
        account=account,
        title="Mine",
        original_prompt="shared search text",
    )
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(
        db_session,
        account=stranger,
        title="Theirs",
        original_prompt="shared search text",
    )
    await db_session.commit()

    body = (await authed_client.post(SEARCH, json=search_payload(prompt="shared search text"))).json()

    ids = [match["prompt_id"] for match in body["results"]]
    assert str(mine.id) in ids
    assert str(theirs.id) not in ids


async def test_client_supplied_user_id_cannot_widen_semantic_search(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    mine = await factories.create_prompt(
        db_session,
        account=account,
        original_prompt="same search text",
    )
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(
        db_session,
        account=stranger,
        original_prompt="same search text",
    )
    await db_session.commit()

    body = (
        await authed_client.post(
            SEARCH,
            json=search_payload(prompt="same search text", user_id=str(stranger.id)),
        )
    ).json()

    ids = [match["prompt_id"] for match in body["results"]]
    assert str(mine.id) in ids
    assert str(theirs.id) not in ids


async def test_semantic_search_honours_role_mode_template_and_date_filters(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    template = await factories.create_template(
        db_session,
        role="writer",
        mode="concise",
        title="Writer Template",
    )
    old_prompt = await factories.create_prompt(
        db_session,
        account=account,
        template_id=template.id,
        original_prompt="filter me out by date",
        created_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
    )
    wanted = await factories.create_prompt(
        db_session,
        account=account,
        template_id=template.id,
        title="Wanted",
        original_prompt="filter me in by date",
        created_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
    )
    wrong_role_template = await factories.create_template(
        db_session,
        role="developer",
        mode="concise",
    )
    wrong_role = await factories.create_prompt(
        db_session,
        account=account,
        template_id=wrong_role_template.id,
        original_prompt="filter me in by date",
        created_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
    )
    await db_session.commit()

    body = (
        await authed_client.post(
            SEARCH,
            json=search_payload(
                prompt="filter me in by date",
                role="writer",
                mode="concise",
                template_id=str(template.id),
                date_from="2024-01-15T00:00:00Z",
                date_to="2024-01-25T00:00:00Z",
            ),
        )
    ).json()

    ids = [match["prompt_id"] for match in body["results"]]
    assert str(wanted.id) in ids
    assert str(old_prompt.id) not in ids
    assert str(wrong_role.id) not in ids


async def test_semantic_search_limit_zero_returns_no_results(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    await factories.create_prompt(db_session, account=account, original_prompt="shared")
    await factories.create_prompt(db_session, account=account, original_prompt="shared")
    await db_session.commit()

    body = (await authed_client.post(SEARCH, json=search_payload(prompt="shared", limit=0))).json()

    assert body["results"] == []


async def test_semantic_search_negative_limit_is_a_generic_400(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.post(SEARCH, json=search_payload(limit=-5))

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


@pytest.mark.parametrize(
    ("body", "case"),
    [
        ({}, "missing-prompt"),
        ({"prompt": None}, "null-prompt"),
        ({"prompt": "ok", "template_id": "not-a-uuid"}, "bad-template-id"),
        ({"prompt": "ok", "date_from": "yesterday somehow"}, "bad-date-from"),
    ],
)
async def test_semantic_search_request_validation_errors(
    authed_client: AsyncClient,
    body: dict[str, Any],
    case: str,
) -> None:
    response = await authed_client.post(SEARCH, json=body)

    assert response.status_code == 422, case


async def test_semantic_search_empty_prompt_is_a_500_from_embedding_generation(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.post(SEARCH, json=search_payload(prompt="   "))

    assert response.status_code == 500
    assert response.json()["detail"] == GENERIC_500

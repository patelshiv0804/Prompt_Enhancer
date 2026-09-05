"""Integration tests for the prompt-intelligence endpoints on ``/api/v1/prompts``.

This file covers the three non-CRUD routes that sit beside the vault itself:
semantic search, duplicate detection, and recommendations.

One route is correctly scoped and two are not.

**``POST /prompts/search`` forces the caller's own user id.** The route ignores
any client-supplied ``user_id`` and passes ``str(user_id)`` down into the vector
query, so search results stay inside the caller's own corpus.

**``POST /prompts/duplicates`` and ``GET /prompts/recommendations`` do not.**
Their services search the whole prompts table, and the routes never pass a user
filter. A logged-in user can therefore learn that another user's prompt exists
and receive its text/title back. Those are asserted as defects so the tests fail
the moment the scoping lands.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests import factories

pytestmark = pytest.mark.integration

SEARCH = "/api/v1/prompts/search"
DUPLICATES = "/api/v1/prompts/duplicates"
RECOMMENDATIONS = "/api/v1/prompts/recommendations"

GENERIC_400 = "An error occurred while processing your request. Please try again."
GENERIC_500 = "An internal server error occurred while processing your prompt."


def search_payload(prompt: str = "optimize a postgres query", **overrides: Any) -> dict[str, Any]:
    body = {"prompt": prompt}
    body.update(overrides)
    return body


def duplicate_payload(prompt: str = "optimize a postgres query", **overrides: Any) -> dict[str, Any]:
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


# ─────────────────────────────────────────────────────────────────────────────
# POST /prompts/duplicates
# ─────────────────────────────────────────────────────────────────────────────


async def test_duplicate_detection_reports_a_duplicate_with_details(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(
        db_session,
        account=account,
        title="Duplicate Candidate",
        original_prompt="detect duplicate text",
    )
    await db_session.commit()

    response = await authed_client.post(DUPLICATES, json=duplicate_payload(prompt="detect duplicate text"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Possible duplicate detected."
    assert body["is_duplicate"] is True
    assert body["similarity"] == pytest.approx(1.0, abs=1e-6)
    assert body["duplicate_prompt"]["id"] == str(prompt.id)
    assert body["duplicate_prompt"]["title"] == "Duplicate Candidate"
    assert body["duplicate_prompt"]["original_prompt"] == "detect duplicate text"


async def test_duplicate_detection_reports_no_match_when_nothing_crosses_the_threshold(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    await factories.create_prompt(
        db_session,
        account=account,
        original_prompt="completely different words",
    )
    await db_session.commit()

    body = (
        await authed_client.post(
            DUPLICATES,
            json=duplicate_payload(prompt="another totally unrelated sentence", threshold=1.01),
        )
    ).json()

    assert body["message"] == "No duplicates detected."
    assert body["is_duplicate"] is False
    assert body["similarity"] is None
    assert body["duplicate_prompt"] is None


async def test_duplicate_detection_leaks_another_users_prompt(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """KNOWN DEFECT (SECURITY) — no user scoping reaches the duplicate scan."""
    secret = "board-only acquisition discussion"
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(
        db_session,
        account=stranger,
        title="Private Duplicate",
        original_prompt=secret,
    )
    await factories.create_prompt(
        db_session,
        account=account,
        title="My Query Prompt",
        original_prompt="something else entirely",
    )
    await db_session.commit()

    body = (await authed_client.post(DUPLICATES, json=duplicate_payload(prompt=secret))).json()

    assert body["is_duplicate"] is True
    assert body["duplicate_prompt"]["id"] == str(theirs.id)
    assert body["duplicate_prompt"]["title"] == "Private Duplicate"
    assert body["duplicate_prompt"]["original_prompt"] == secret


async def test_duplicate_detection_negative_threshold_treats_any_nearest_match_as_a_duplicate(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """KNOWN DEFECT — threshold is unvalidated, so negative means "always yes".

    Any negative threshold is below every possible cosine distance, so the
    nearest row in the corpus is always reported as a duplicate regardless of
    how unrelated it is. House rule 1 forbids asserting *which* row comes back:
    the scan is unscoped (defect #26) and the clone holds other prompts, so the
    winner may be cloned dev data rather than this test's own prompt. What is
    pinned is the invariant the defect produces — a duplicate is always claimed,
    and a concrete prompt is always attached.
    """
    await factories.create_prompt(
        db_session,
        account=account,
        original_prompt="not really the same",
    )
    await db_session.commit()

    body = (
        await authed_client.post(
            DUPLICATES,
            json=duplicate_payload(prompt="entirely different", threshold=-0.5),
        )
    ).json()

    assert body["is_duplicate"] is True
    assert body["duplicate_prompt"] is not None
    assert UUID(body["duplicate_prompt"]["id"])


@pytest.mark.parametrize(
    ("body", "case"),
    [
        ({}, "missing-prompt"),
        ({"prompt": None}, "null-prompt"),
        ({"prompt": "ok", "threshold": "high"}, "non-numeric-threshold"),
    ],
)
async def test_duplicate_detection_request_validation_errors(
    authed_client: AsyncClient,
    body: dict[str, Any],
    case: str,
) -> None:
    response = await authed_client.post(DUPLICATES, json=body)

    assert response.status_code == 422, case


async def test_duplicate_detection_empty_prompt_is_a_500_from_embedding_generation(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.post(DUPLICATES, json=duplicate_payload(prompt=""))

    assert response.status_code == 500
    assert response.json()["detail"] == GENERIC_500


# ─────────────────────────────────────────────────────────────────────────────
# GET /prompts/recommendations
# ─────────────────────────────────────────────────────────────────────────────


async def test_recommendations_return_ranked_matches_with_expected_fields(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(
        db_session,
        account=account,
        title="Recommended",
        original_prompt="recommend this text",
    )
    await factories.create_prompt_version(db_session, prompt=prompt, content="v1")
    await factories.create_prompt_version(db_session, prompt=prompt, content="v2")
    await db_session.commit()

    response = await authed_client.get(RECOMMENDATIONS, params={"prompt": "recommend this text", "limit": 1})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Recommendations generated."
    result = body["results"][0]
    assert result["prompt_id"] == str(prompt.id)
    assert result["title"] == "Recommended"
    assert result["original_prompt"] == "recommend this text"
    assert result["similarity_score"] == pytest.approx(1.0, abs=1e-6)
    assert result["version_count"] == 2
    assert isinstance(result["recommendation_score"], float)
    assert "created_at" in result


async def test_recommendations_are_sorted_by_combined_score_descending(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    older = await factories.create_prompt(
        db_session,
        account=account,
        title="Older",
        original_prompt="recommend by score",
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    await factories.create_prompt_version(db_session, prompt=older, content="v1")

    fresher = await factories.create_prompt(
        db_session,
        account=account,
        title="Fresher",
        original_prompt="recommend by score",
        created_at=datetime.now(timezone.utc),
    )
    await factories.create_prompt_version(db_session, prompt=fresher, content="v1")
    await factories.create_prompt_version(db_session, prompt=fresher, content="v2")
    await factories.create_prompt_version(db_session, prompt=fresher, content="v3")
    await db_session.commit()

    body = (await authed_client.get(RECOMMENDATIONS, params={"prompt": "recommend by score", "limit": 2})).json()

    assert [item["title"] for item in body["results"]] == ["Fresher", "Older"]


async def test_recommendations_limit_zero_returns_no_results(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    await factories.create_prompt(db_session, account=account, original_prompt="recommend me")
    await db_session.commit()

    body = (await authed_client.get(RECOMMENDATIONS, params={"prompt": "recommend me", "limit": 0})).json()

    assert body["results"] == []


async def test_recommendations_leak_another_users_prompt(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """KNOWN DEFECT (SECURITY) — no user scoping reaches recommendation search."""
    secret = "salary review notes for executive team"
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(
        db_session,
        account=stranger,
        title="Private Recommendation",
        original_prompt=secret,
    )
    await factories.create_prompt(
        db_session,
        account=account,
        title="My Prompt",
        original_prompt="different text",
    )
    await db_session.commit()

    body = (await authed_client.get(RECOMMENDATIONS, params={"prompt": secret, "limit": 5})).json()

    ids = [item["prompt_id"] for item in body["results"]]
    assert str(theirs.id) in ids
    leaked = next(item for item in body["results"] if item["prompt_id"] == str(theirs.id))
    assert leaked["title"] == "Private Recommendation"
    assert leaked["original_prompt"] == secret


async def test_recommendations_negative_limit_is_a_generic_400(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.get(RECOMMENDATIONS, params={"prompt": "recommend", "limit": -2})

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


@pytest.mark.parametrize(
    ("params", "case"),
    [
        ({}, "missing-prompt"),
        ({"prompt": 123}, "non-string-prompt"),
        ({"prompt": "x", "limit": "many"}, "non-integer-limit"),
    ],
)
async def test_recommendations_query_validation_errors(
    authed_client: AsyncClient,
    params: dict[str, Any],
    case: str,
) -> None:
    response = await authed_client.get(RECOMMENDATIONS, params=params)

    expected = 422 if case != "non-string-prompt" else 200
    assert response.status_code == expected, case


async def test_recommendations_empty_prompt_is_a_500_from_embedding_generation(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.get(RECOMMENDATIONS, params={"prompt": ""})

    assert response.status_code == 500
    assert response.json()["detail"] == GENERIC_500

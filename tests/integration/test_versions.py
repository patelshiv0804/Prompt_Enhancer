"""Integration tests for ``/api/v1/prompt-versions``.

This router is the history surface for a prompt: append a version, list the
history for one prompt, read one version by id, and restore a historical
version as the active one. Like ``/prompts``, ownership is deliberately hidden:
another user's prompt or version comes back as a 404 rather than a 403.

Two quirks matter enough to pin explicitly.

**The create schema asks for ``version_number``, but the route ignores it.**
``PromptVersionService.create_version`` always computes the next sequential
number from the database, so a caller can send ``999`` and still get version 2.
That mismatch is worth testing because it is observable client behaviour, not a
purely internal detail.

**The restore route's documented errors do not match what the code emits.**
The helper it uses raises ``ActiveVersionDeletionError`` and
``VersionRestoreError``, but ``map_service_error`` does not recognise either, so
those failures collapse into the generic 400 instead of the documented 409/500.
The tests below assert the API contract callers actually receive today.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt, PromptVersion
from app.main import create_app
from app.schemas.enums import VersionType
from tests import factories
from tests.stubs.embedding import hashed_embedding

pytestmark = pytest.mark.integration

VERSIONS = "/api/v1/prompt-versions/"
GENERIC_400 = "An error occurred while processing your request. Please try again."
NOT_FOUND_404 = "Requested resource or matching template was not found."


def payload(content: str = "A refined version of the prompt.", **overrides: Any) -> dict[str, Any]:
    body = {
        "version_number": 999,
        "version_type": "enhanced",
        "content": content,
    }
    body.update(overrides)
    return body


# ─────────────────────────────────────────────────────────────────────────────
# POST /prompt-versions/ — create
# ─────────────────────────────────────────────────────────────────────────────


async def test_creating_a_version_returns_it_in_the_envelope(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.post(VERSIONS, params={"prompt_id": prompt_id}, json=payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Prompt version created."
    assert body["data"]["prompt_id"] == prompt_id
    assert body["data"]["content"] == "A refined version of the prompt."
    assert body["data"]["version_type"] == "enhanced"
    assert UUID(body["data"]["id"])


async def test_create_returns_200_not_201(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    response = await authed_client.post(VERSIONS, params={"prompt_id": str(prompt.id)}, json=payload())

    assert response.status_code == 200, response.text


async def test_creating_a_version_persists_it_and_makes_it_current(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = prompt.id
    await db_session.commit()

    response = await authed_client.post(VERSIONS, params={"prompt_id": str(prompt_id)}, json=payload())

    version_id = UUID(response.json()["data"]["id"])
    db_session.expire_all()
    stored = await db_session.scalar(select(PromptVersion).where(PromptVersion.id == version_id))
    refreshed_prompt = await db_session.scalar(select(Prompt).where(Prompt.id == prompt_id))

    assert stored is not None
    assert stored.version_number == 1
    assert refreshed_prompt is not None
    assert refreshed_prompt.current_version_id == version_id


async def test_the_client_supplied_version_number_is_ignored_in_favour_of_the_next_sequence(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=prompt, version_number=1)
    prompt_id = str(prompt.id)
    await db_session.commit()

    body = (
        await authed_client.post(VERSIONS, params={"prompt_id": prompt_id}, json=payload(version_number=999))
    ).json()

    assert body["data"]["version_number"] == 2


async def test_markdown_control_tokens_are_removed_from_the_saved_content(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    noisy = "# Heading\n**Bold** and `code` with _italics_."
    body = (
        await authed_client.post(VERSIONS, params={"prompt_id": prompt_id}, json=payload(content=noisy))
    ).json()

    assert body["data"]["content"] == "Heading\nBold and code with italics."


async def test_omitting_version_type_defaults_to_draft(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    body = (
        await authed_client.post(
            VERSIONS,
            params={"prompt_id": str(prompt.id)},
            json=payload(version_type=None),
        )
    ).json()

    assert body["data"]["version_type"] == "draft"


async def test_creating_a_version_for_an_unknown_or_unowned_prompt_is_a_404(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger)
    theirs_id = str(theirs.id)
    await db_session.commit()

    unknown = await authed_client.post(VERSIONS, params={"prompt_id": str(uuid4())}, json=payload())
    unowned = await authed_client.post(VERSIONS, params={"prompt_id": theirs_id}, json=payload())

    assert unknown.status_code == 404
    assert unowned.status_code == 404
    assert unknown.json()["detail"] == NOT_FOUND_404


async def test_a_malformed_prompt_id_is_a_generic_400(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.post(VERSIONS, params={"prompt_id": "not-a-uuid"}, json=payload())

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


@pytest.mark.parametrize(
    ("body", "case"),
    [
        ({"version_type": "enhanced", "content": ""}, "empty-content"),
        ({"version_type": "enhanced"}, "missing-content"),
        ({"content": "ok"}, "missing-version-number"),
        ({"version_number": 0, "content": "ok"}, "version-number-below-one"),
    ],
)
async def test_create_request_body_validation_happens_before_the_handler(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
    body: dict[str, Any],
    case: str,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    response = await authed_client.post(VERSIONS, params={"prompt_id": str(prompt.id)}, json=body)

    assert response.status_code == 422, case


# ─────────────────────────────────────────────────────────────────────────────
# GET /prompt-versions/ — list
# ─────────────────────────────────────────────────────────────────────────────


async def test_listing_versions_requires_prompt_id(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.get(VERSIONS)

    assert response.status_code == 400
    assert response.json()["detail"] == "prompt_id is required."


async def test_listing_versions_returns_the_paginated_envelope(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    first = await factories.create_prompt_version(db_session, prompt=prompt, content="v1")
    second = await factories.create_prompt_version(db_session, prompt=prompt, content="v2")
    prompt_id, first_id, second_id = str(prompt.id), str(first.id), str(second.id)
    await db_session.commit()

    response = await authed_client.get(VERSIONS, params={"prompt_id": prompt_id})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Prompt versions retrieved."
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [item["id"] for item in body["data"]] == [first_id, second_id]


async def test_listing_versions_is_scoped_to_one_prompt(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    other = await factories.create_prompt(db_session, account=account)
    wanted = await factories.create_prompt_version(db_session, prompt=prompt, content="keep me")
    hidden = await factories.create_prompt_version(db_session, prompt=other, content="not this one")
    await db_session.commit()

    body = (await authed_client.get(VERSIONS, params={"prompt_id": str(prompt.id)})).json()

    ids = [item["id"] for item in body["data"]]
    assert str(wanted.id) in ids
    assert str(hidden.id) not in ids


async def test_versions_are_ordered_by_version_number_ascending(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=prompt, version_number=2, content="second")
    await factories.create_prompt_version(db_session, prompt=prompt, version_number=1, content="first", set_current=False)
    await db_session.commit()

    body = (await authed_client.get(VERSIONS, params={"prompt_id": str(prompt.id)})).json()

    assert [item["version_number"] for item in body["data"]] == [1, 2]


async def test_total_is_the_page_length_not_the_full_history_size(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """KNOWN DEFECT — the route reports ``len(page)`` as ``total``."""
    prompt = await factories.create_prompt(db_session, account=account)
    for index in range(3):
        await factories.create_prompt_version(db_session, prompt=prompt, content=f"v{index}")
    await db_session.commit()

    body = (
        await authed_client.get(VERSIONS, params={"prompt_id": str(prompt.id), "limit": 1, "offset": 1})
    ).json()

    assert len(body["data"]) == 1
    assert body["total"] == 1
    assert body["page"] == 2


async def test_listing_versions_for_an_unknown_or_unowned_prompt_is_a_404(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger)
    await db_session.commit()

    response = await authed_client.get(VERSIONS, params={"prompt_id": str(theirs.id)})
    unknown = await authed_client.get(VERSIONS, params={"prompt_id": str(uuid4())})

    assert response.status_code == 404
    assert unknown.status_code == 404
    assert response.json()["detail"] == NOT_FOUND_404


@pytest.mark.parametrize(
    ("params", "case"),
    [
        ({"prompt_id": "not-a-uuid"}, "malformed-prompt-id"),
        ({"prompt_id": str(uuid4()), "limit": 0}, "limit-below-one"),
        ({"prompt_id": str(uuid4()), "limit": 101}, "limit-above-cap"),
        ({"prompt_id": str(uuid4()), "offset": -1}, "negative-offset"),
    ],
)
async def test_list_parameter_validation_and_errors(
    authed_client: AsyncClient,
    params: dict[str, Any],
    case: str,
) -> None:
    response = await authed_client.get(VERSIONS, params=params)

    expected = 400 if case == "malformed-prompt-id" else 422
    assert response.status_code == expected, case


# ─────────────────────────────────────────────────────────────────────────────
# GET /prompt-versions/{version_id} — detail
# ─────────────────────────────────────────────────────────────────────────────


async def test_getting_a_version_returns_its_detail(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    version = await factories.create_prompt_version(
        db_session,
        prompt=prompt,
        version_type=VersionType.ENHANCED.value,
        content="Detail body",
        change_summary="Why it changed",
    )
    await db_session.commit()

    response = await authed_client.get(f"{VERSIONS}{version.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"] == "Prompt version retrieved."
    assert body["data"]["id"] == str(version.id)
    assert body["data"]["prompt_id"] == str(prompt.id)
    assert body["data"]["content"] == "Detail body"
    assert body["data"]["change_summary"] == "Why it changed"


async def test_getting_an_unowned_or_unknown_version_is_a_404(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    stranger = await factories.create_account(db_session)
    prompt = await factories.create_prompt(db_session, account=stranger)
    version = await factories.create_prompt_version(db_session, prompt=prompt)
    await db_session.commit()

    response = await authed_client.get(f"{VERSIONS}{version.id}")
    unknown = await authed_client.get(f"{VERSIONS}{uuid4()}")

    assert response.status_code == 404
    assert unknown.status_code == 404
    assert response.json()["detail"] == NOT_FOUND_404


async def test_a_malformed_version_id_is_a_generic_400(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.get(f"{VERSIONS}not-a-uuid")

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


# ─────────────────────────────────────────────────────────────────────────────
# POST /prompt-versions/{prompt_id}/restore — restore
# ─────────────────────────────────────────────────────────────────────────────


async def test_restoring_a_historical_version_switches_the_active_version_and_embedding(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    template = await factories.create_template(db_session, role="writer", mode="concise", title="Restore Template")
    prompt = await factories.create_prompt(
        db_session,
        account=account,
        template_id=template.id,
        original_prompt="Original restore text",
    )
    first = await factories.create_prompt_version(
        db_session,
        prompt=prompt,
        content="First restored body",
        set_current=False,
    )
    second = await factories.create_prompt_version(
        db_session,
        prompt=prompt,
        content="Second active body",
        set_current=True,
    )
    prompt_id = prompt.id
    await db_session.commit()

    response = await authed_client.post(
        f"{VERSIONS}{prompt_id}/restore",
        json={"version_id": str(first.id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Prompt version restored."
    db_session.expire_all()
    refreshed = await db_session.scalar(select(Prompt).where(Prompt.id == prompt_id))
    assert refreshed is not None
    assert refreshed.current_version_id == first.id

    expected_source = "Original restore text First restored body writer concise Restore Template"
    assert refreshed.embedding == pytest.approx(hashed_embedding(expected_source), abs=1e-6)
    assert refreshed.current_version_id != second.id


async def test_restoring_the_active_version_is_a_generic_400_not_a_409(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    active = await factories.create_prompt_version(db_session, prompt=prompt)
    await db_session.commit()

    response = await authed_client.post(
        f"{VERSIONS}{prompt.id}/restore",
        json={"version_id": str(active.id)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


async def test_restoring_a_version_from_another_prompt_is_a_404(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    mine = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=mine)
    other = await factories.create_prompt(db_session, account=account)
    foreign = await factories.create_prompt_version(db_session, prompt=other)
    await db_session.commit()

    response = await authed_client.post(
        f"{VERSIONS}{mine.id}/restore",
        json={"version_id": str(foreign.id)},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == NOT_FOUND_404


async def test_restoring_for_an_unowned_or_unknown_prompt_is_a_404(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    stranger = await factories.create_account(db_session)
    prompt = await factories.create_prompt(db_session, account=stranger)
    version = await factories.create_prompt_version(db_session, prompt=prompt)
    await db_session.commit()

    response = await authed_client.post(
        f"{VERSIONS}{prompt.id}/restore",
        json={"version_id": str(version.id)},
    )
    unknown = await authed_client.post(
        f"{VERSIONS}{uuid4()}/restore",
        json={"version_id": str(version.id)},
    )

    assert response.status_code == 404
    assert unknown.status_code == 404


@pytest.mark.parametrize(
    ("prompt_id", "body", "expected", "case"),
    [
        ("not-a-uuid", {"version_id": str(uuid4())}, 400, "malformed-prompt-id"),
        (None, {"version_id": "not-a-uuid"}, 422, "malformed-version-id"),
        (None, {}, 422, "missing-version-id"),
    ],
)
async def test_restore_parameter_and_body_validation(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
    prompt_id: str | None,
    body: dict[str, Any],
    expected: int,
    case: str,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=prompt)
    await db_session.commit()
    target = prompt_id or str(prompt.id)

    response = await authed_client.post(f"{VERSIONS}{target}/restore", json=body)

    assert response.status_code == expected, case


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────


def prompt_version_operations() -> list[tuple[str, str]]:
    paths = create_app().openapi()["paths"]
    operations = []
    for path, methods in paths.items():
        if not path.startswith("/api/v1/prompt-versions"):
            continue
        for method in methods:
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                operations.append((method.lower(), path))
    return sorted(operations)


async def test_every_prompt_version_route_rejects_an_anonymous_caller(
    client: AsyncClient,
) -> None:
    operations = prompt_version_operations()
    assert len(operations) == 4, operations

    outcomes = {}
    for method, path in operations:
        url = (
            path.replace("{prompt_id}", str(uuid4()))
            .replace("{version_id}", str(uuid4()))
        )
        response = await client.request(
            method,
            url,
            params={"prompt_id": str(uuid4())} if path.endswith("/") and method == "get" else None,
            json={"version_id": str(uuid4()), "version_number": 1, "content": "x"} if method == "post" else None,
        )
        outcomes[f"{method.upper()} {path}"] = response.status_code

    assert set(outcomes.values()) == {401}, outcomes


async def test_a_bearer_token_works_as_well_as_the_cookie(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    version = await factories.create_prompt_version(db_session, prompt=prompt)
    await db_session.commit()

    response = await client.get(f"{VERSIONS}{version.id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(version.id)


async def test_an_expired_token_is_rejected(
    client: AsyncClient,
    account: factories.Account,
) -> None:
    from app.core.security import create_access_token

    expired = create_access_token(
        {"sub": str(account.id)}, expires_delta=timedelta(minutes=-5)
    )

    response = await client.get(
        VERSIONS,
        params={"prompt_id": str(uuid4())},
        headers={"Authorization": f"Bearer {expired}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

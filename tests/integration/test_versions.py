"""Integration tests for ``/api/v1/prompt-versions``.

This router is the history surface for a prompt: append a version, list the
history for one prompt, read one version by id, and restore a historical
version as the active one. Like ``/prompts``, ownership is deliberately hidden:
another user's prompt or version comes back as a 404 rather than a 403.

**TWO OF THE FOUR ROUTES ON THIS ROUTER ARE DEAD.** Both call a method that does
not exist on ``PromptVersionService`` (whose real API is ``create_version``,
``list_versions``, ``restore_version``, ``delete_version``):

* ``POST /prompt-versions/`` calls ``create_version_for_prompt(...)``
* ``GET /prompt-versions/{version_id}`` calls ``get_version(...)``

Every request to either raises ``AttributeError`` inside the handler's
``try``, and the blanket ``except Exception: raise map_service_error(exc)``
turns that into ``400 {"detail": "An error occurred while processing your
request. Please try again."}`` — indistinguishable from a validation error. The
tests below pin that as ``KNOWN DEFECT`` rather than asserting the intended
behaviour, so the suite records the real contract and will fail loudly the day
the application is fixed.

One consequence worth stating: because create is dead, the ``version_number``
field on ``PromptVersionCreate`` cannot be exercised through the API at all.
``PromptVersionService.create_version`` computes the next sequential number
itself and ignores whatever the client sends, but no caller can reach that code
path today, so the mismatch is pinned as a unit-level fact only.

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


async def test_creating_a_version_is_a_generic_400_because_the_handler_is_dead(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """KNOWN DEFECT — ``POST /prompt-versions/`` cannot succeed for any input.

    The handler calls ``prompt_version_service.create_version_for_prompt(...)``,
    which does not exist on ``PromptVersionService``. The resulting
    ``AttributeError`` is caught by the handler's blanket ``except Exception``
    and mapped to the generic 400, so a completely broken endpoint is
    indistinguishable from a rejected payload.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.post(VERSIONS, params={"prompt_id": prompt_id}, json=payload())

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": GENERIC_400}


@pytest.mark.parametrize("version_type", ["draft", "published", "archived", "restored", None])
async def test_create_fails_the_same_way_for_every_version_type(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
    version_type: str | None,
) -> None:
    """KNOWN DEFECT — the failure is unconditional, not payload-dependent.

    Parametrised over every member of ``VersionType`` (plus the omitted case
    that the handler would default to ``"draft"``) to establish that nothing
    about the request content reaches a code path that works.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    body = payload()
    if version_type is None:
        body.pop("version_type")
    else:
        body["version_type"] = version_type

    response = await authed_client.post(VERSIONS, params={"prompt_id": prompt_id}, json=body)

    assert response.status_code == 400, response.text


async def test_a_failed_create_persists_nothing(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """KNOWN DEFECT — the dead handler at least leaves no partial row behind.

    ``AttributeError`` is raised before any ``session.add``, and the session
    dependency rolls back on the error path, so the prompt keeps whatever
    ``current_version_id`` it had and no version row appears.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = prompt.id
    await db_session.commit()

    await authed_client.post(VERSIONS, params={"prompt_id": str(prompt_id)}, json=payload())

    db_session.expire_all()
    versions = (
        await db_session.scalars(select(PromptVersion).where(PromptVersion.prompt_id == prompt_id))
    ).all()
    current = await db_session.scalar(select(Prompt.current_version_id).where(Prompt.id == prompt_id))

    assert versions == []
    assert current is None


async def test_the_ownership_check_runs_before_the_dead_service_call(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """``_assert_prompt_owner`` precedes the broken call, so 404 still wins.

    This is the one create behaviour that is still meaningful: an unknown or
    unowned ``prompt_id`` is rejected as 404 before the handler reaches the
    method that does not exist, so the defect does not turn an authorization
    failure into an ambiguous 400.
    """
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger)
    theirs_id = str(theirs.id)
    await db_session.commit()

    unknown = await authed_client.post(VERSIONS, params={"prompt_id": str(uuid4())}, json=payload())
    unowned = await authed_client.post(VERSIONS, params={"prompt_id": theirs_id}, json=payload())

    assert unknown.status_code == 404
    assert unowned.status_code == 404
    assert unknown.json()["detail"] == NOT_FOUND_404
    assert unowned.json()["detail"] == NOT_FOUND_404


async def test_the_service_ignores_a_client_supplied_version_number(
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """The ``version_number`` the create schema demands is computed, not honoured.

    Asserted against the service directly because the route that would expose
    it is dead (see the module docstring). ``PromptVersionCreate`` makes
    ``version_number`` a required ``ge=1`` field, but ``create_version`` derives
    the number from the highest existing version — so once the endpoint is
    fixed, a caller sending ``999`` will still get ``2``.
    """
    from app.api.v1.prompt_versions import prompt_version_service

    prompt = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=prompt, version_number=1)
    await db_session.flush()

    created = await prompt_version_service.create_version(
        session=db_session,
        prompt=prompt,
        content="A refined version of the prompt.",
        version_type="draft",
    )

    assert created.version_number == 2
    assert prompt.current_version_id == created.id


async def test_the_service_strips_markdown_control_tokens_from_the_saved_content(
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """``_clean_version_content`` removes markdown emphasis before persisting.

    Also asserted against the service directly, for the same reason.
    """
    from app.api.v1.prompt_versions import prompt_version_service

    prompt = await factories.create_prompt(db_session, account=account)
    await db_session.flush()

    created = await prompt_version_service.create_version(
        session=db_session,
        prompt=prompt,
        content="# Heading\n**Bold** and `code` with _italics_.",
        version_type="draft",
    )

    assert created.content == "Heading\nBold and code with italics."


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


async def test_getting_a_version_is_a_generic_400_because_the_handler_is_dead(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    """KNOWN DEFECT — ``GET /prompt-versions/{version_id}`` cannot succeed.

    The handler calls ``prompt_version_service.get_version(session, version_id)``,
    and ``PromptVersionService`` has no such method. As with create, the
    ``AttributeError`` is swallowed into the generic 400 — so the caller's own,
    perfectly valid version reads back as a bad request.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    version = await factories.create_prompt_version(
        db_session,
        prompt=prompt,
        version_type=VersionType.PUBLISHED.value,
        content="Detail body",
        change_summary="Why it changed",
    )
    version_id = version.id
    await db_session.commit()

    response = await authed_client.get(f"{VERSIONS}{version_id}")

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": GENERIC_400}


async def test_the_dead_detail_route_hides_the_404_it_documents(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """KNOWN DEFECT — unowned, unknown and owned ids are now indistinguishable.

    Unlike create, the detail handler calls the missing method *before*
    ``_assert_prompt_owner``, so the ownership check is unreachable. Every id
    collapses to the same generic 400, which is at least not an information
    leak — but the documented 404 can never be produced.
    """
    stranger = await factories.create_account(db_session)
    prompt = await factories.create_prompt(db_session, account=stranger)
    version = await factories.create_prompt_version(db_session, prompt=prompt)
    version_id = version.id
    await db_session.commit()

    unowned = await authed_client.get(f"{VERSIONS}{version_id}")
    unknown = await authed_client.get(f"{VERSIONS}{uuid4()}")

    assert unowned.status_code == 400
    assert unknown.status_code == 400
    assert unowned.json() == unknown.json() == {"detail": GENERIC_400}


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
    # House rule 4: capture the ids before the request. The restore commits and
    # the session dependency's post-request handling expires every loaded
    # instance, so ``first.id`` afterwards would be a lazy read from sync
    # context — MissingGreenlet, not a value.
    prompt_id, first_id, second_id = prompt.id, first.id, second.id
    await db_session.commit()

    response = await authed_client.post(
        f"{VERSIONS}{prompt_id}/restore",
        json={"version_id": str(first_id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Prompt version restored."
    db_session.expire_all()
    refreshed = await db_session.scalar(select(Prompt).where(Prompt.id == prompt_id))
    assert refreshed is not None
    assert refreshed.current_version_id == first_id

    expected_source = "Original restore text First restored body writer concise Restore Template"
    assert refreshed.embedding == pytest.approx(hashed_embedding(expected_source), abs=1e-6)
    assert refreshed.current_version_id != second_id


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
    # House rule 4 — the first request fails and rolls back, expiring both rows.
    prompt_id, version_id = prompt.id, version.id
    await db_session.commit()

    response = await authed_client.post(
        f"{VERSIONS}{prompt_id}/restore",
        json={"version_id": str(version_id)},
    )
    unknown = await authed_client.post(
        f"{VERSIONS}{uuid4()}/restore",
        json={"version_id": str(version_id)},
    )

    assert response.status_code == 404
    assert unknown.status_code == 404
    assert response.json()["detail"] == NOT_FOUND_404


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
    """Proved against the list route: the detail route is dead for every caller.

    ``GET /prompt-versions/{version_id}`` would be the natural target here, but
    it returns the generic 400 regardless of credentials, so it cannot
    distinguish an accepted token from a rejected one.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    version = await factories.create_prompt_version(db_session, prompt=prompt)
    prompt_id, version_id = str(prompt.id), str(version.id)
    await db_session.commit()

    response = await client.get(VERSIONS, params={"prompt_id": prompt_id}, headers=auth_headers)

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["data"]] == [version_id]


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

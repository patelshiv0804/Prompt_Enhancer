"""``/api/v1/prompts`` — the vault: list, detail, delete and "find similar".

Two properties of this router shape almost every test below.

**It is the one router that got an authorization pass, and only partly.** Every
route depends on ``get_current_user_id``, and ``_assert_owner`` deliberately
raises ``PromptNotFoundError`` (→ 404) rather than a 403 for a prompt owned by
someone else, so ids are not enumerable. ``list_prompts`` goes further and
*overrides* any client-supplied user id with the caller's own, under a comment
naming the hardening ticket (N4). But ``/similar/{id}`` — whose ownership check
on the query prompt is right there in the handler — hands the caller every user's
prompts as matches, because the search below it never learned about ``user_id``.
Its sibling ``/search`` passes ``user_id=str(user_id)`` with an explicit "N4"
comment, which is the evidence the omission is an oversight rather than a
decision. That is asserted, as a leak, in ``test_similar_leaks_...``.

**Every handler ends in ``except Exception as exc: raise map_service_error(exc)``.**
Nothing not isinstance-matched by that mapper survives: a pydantic
``ValidationError``, a bad UUID, a negative SQL ``LIMIT`` and the handler's own
``HTTPException(400, "Version parameter must be ...")`` all arrive as the same
opaque ``400``. Tests here therefore assert the *status* a caller sees and, where
the message is the only observable, that it is the generic one — pinning the
information loss rather than pretending it does not happen.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt, PromptVersion
from app.schemas.enums import ModelProvider
from app.main import create_app
from tests import factories

pytestmark = pytest.mark.integration

PROMPTS = "/api/v1/prompts/"
GENERIC_400 = "An error occurred while processing your request. Please try again."
NOT_FOUND_404 = "Requested resource or matching template was not found."


async def rows_for(db_session: AsyncSession, user_id: Any) -> int:
    return await db_session.scalar(
        select(func.count()).select_from(Prompt).where(Prompt.user_id == user_id)
    )


async def exists(db_session: AsyncSession, prompt_id: Any) -> bool:
    found = await db_session.scalar(select(Prompt.id).where(Prompt.id == prompt_id))
    return found is not None


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/prompts/ — the list
# ─────────────────────────────────────────────────────────────────────────────


async def test_the_list_returns_the_paginated_envelope(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account, title="Envelope")
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.get(PROMPTS)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Prompt list retrieved."
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert prompt_id in [item["id"] for item in body["data"]]


async def test_a_list_item_carries_the_prompt_summary_fields(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    await factories.create_prompt(
        db_session, account=account, title="Fields", original_prompt="summarise this"
    )
    await db_session.commit()

    body = (await authed_client.get(PROMPTS)).json()
    item = body["data"][0]

    assert item["title"] == "Fields"
    assert item["original_prompt"] == "summarise this"
    assert set(item) >= {
        "id",
        "title",
        "original_prompt",
        "template_id",
        "ai_model_id",
        "current_version_id",
        "old_analysis",
        "new_analysis",
        "grade",
        "tool_recommendations",
        "created_at",
        "updated_at",
    }


async def test_the_list_only_shows_the_callers_own_prompts(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    mine = await factories.create_prompt(db_session, account=account, title="Mine")
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger, title="Theirs")
    mine_id, theirs_id = str(mine.id), str(theirs.id)
    await db_session.commit()

    ids = [item["id"] for item in (await authed_client.get(PROMPTS)).json()["data"]]

    assert mine_id in ids
    assert theirs_id not in ids


async def test_a_client_supplied_user_id_cannot_widen_the_list(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """N4: the handler overwrites ``user_id`` with the caller's own before querying.

    The parameter is not even declared on the route any more, so FastAPI drops it
    on the floor; this test pins the *effect* — asking for someone else's prompts
    returns your own, never theirs.
    """
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger)
    mine = await factories.create_prompt(db_session, account=account)
    mine_id, theirs_id, stranger_id = str(mine.id), str(theirs.id), str(stranger.id)
    await db_session.commit()

    body = (await authed_client.get(PROMPTS, params={"user_id": stranger_id})).json()

    ids = [item["id"] for item in body["data"]]
    assert ids == [mine_id]
    assert theirs_id not in ids


async def test_total_is_a_real_count_and_not_the_page_length(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """Contrast with ``/templates/``, where ``total`` is ``len(page)``.

    This router issues a separate ``count_prompts``, so a client can compute a
    page count from it. That difference between two sibling routers is worth a
    test in its own right.
    """
    for index in range(3):
        await factories.create_prompt(db_session, account=account, title=f"Count {index}")
    await db_session.commit()

    body = (await authed_client.get(PROMPTS, params={"page_size": 1})).json()

    assert len(body["data"]) == 1
    assert body["total"] == 3


async def test_pages_are_disjoint_and_cover_the_whole_set(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    for index in range(5):
        await factories.create_prompt(db_session, account=account, title=f"Page {index}")
    await db_session.commit()

    first = (await authed_client.get(PROMPTS, params={"page": 1, "page_size": 2})).json()
    second = (await authed_client.get(PROMPTS, params={"page": 2, "page_size": 2})).json()
    third = (await authed_client.get(PROMPTS, params={"page": 3, "page_size": 2})).json()

    seen = [item["id"] for page in (first, second, third) for item in page["data"]]
    assert len(seen) == 5
    assert len(set(seen)) == 5
    assert first["page"] == 1 and second["page"] == 2 and third["page"] == 3


async def test_a_page_past_the_end_is_empty_but_still_reports_the_total(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    body = (await authed_client.get(PROMPTS, params={"page": 99, "page_size": 20})).json()

    assert body["data"] == []
    assert body["total"] == 1


@pytest.mark.parametrize(
    ("params", "case"),
    [
        ({"page": 0}, "page-below-one"),
        ({"page": -1}, "page-negative"),
        ({"page_size": 0}, "page-size-below-one"),
        ({"page_size": 1001}, "page-size-above-cap"),
        ({"page": "one"}, "page-not-an-integer"),
    ],
)
async def test_pagination_bounds_are_enforced(
    authed_client: AsyncClient, params: dict[str, Any], case: str
) -> None:
    response = await authed_client.get(PROMPTS, params=params)

    assert response.status_code == 422, case


async def test_the_default_order_is_newest_first(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """``created_at`` comes from a Python ``default_factory``, so the three rows
    get distinct timestamps in insertion order even inside one transaction."""
    titles = ["Oldest", "Middle", "Newest"]
    for title in titles:
        await factories.create_prompt(db_session, account=account, title=title)
    await db_session.commit()

    body = (await authed_client.get(PROMPTS)).json()

    assert [item["title"] for item in body["data"]] == list(reversed(titles))


@pytest.mark.parametrize(
    ("sort_order", "expected"),
    [("asc", ["A", "B", "C"]), ("desc", ["C", "B", "A"])],
)
async def test_sorting_by_a_real_column_works_in_both_directions(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
    sort_order: str,
    expected: list[str],
) -> None:
    for title in ("B", "A", "C"):
        await factories.create_prompt(db_session, account=account, title=title)
    await db_session.commit()

    body = (
        await authed_client.get(
            PROMPTS, params={"sort_by": "title", "sort_order": sort_order}
        )
    ).json()

    assert [item["title"] for item in body["data"]] == expected


async def test_an_unrecognised_sort_order_is_treated_as_ascending(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT — ``sort_order`` is an unvalidated ``str``.

    The repository branches on ``sort_order == "desc"`` and treats *everything
    else* as ascending, so a typo ("descending", "DESC", "sideways") silently
    reverses the caller's intent instead of returning 422. ``sort_order: str =
    Query(default="desc", pattern="^(asc|desc)$")`` would name the field.
    """
    for title in ("B", "A", "C"):
        await factories.create_prompt(db_session, account=account, title=title)
    await db_session.commit()

    for typo in ("DESC", "descending", "sideways"):
        body = (
            await authed_client.get(
                PROMPTS, params={"sort_by": "title", "sort_order": typo}
            )
        ).json()
        assert [item["title"] for item in body["data"]] == ["A", "B", "C"], typo


async def test_an_unknown_sort_column_silently_drops_the_ordering(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT — ``sort_by`` is fed straight to ``getattr(Prompt, sort_by)``.

    A truthy-but-unknown name makes ``col`` ``None``, and because the ``else``
    branch that installs the default ``created_at DESC`` only runs when ``sort_by``
    is *falsy*, the query goes out with **no ``ORDER BY`` at all**. The caller gets
    a 200 and whatever order Postgres feels like — which is stable enough in
    testing to look fine and will reorder under a different plan in production. A
    whitelist would make this a 422 naming the field; the test asserts only the
    status, since asserting an arbitrary order would be asserting a coincidence.
    """
    await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    response = await authed_client.get(PROMPTS, params={"sort_by": "no_such_column"})

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.parametrize("sort_by", ["versions", "metadata", "template"])
async def test_sorting_by_a_non_column_attribute_is_a_generic_400(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
    sort_by: str,
) -> None:
    """KNOWN DEFECT — same ``getattr``, worse outcome.

    ``versions``/``template`` are relationships and ``metadata`` is SQLAlchemy's
    own ``MetaData`` object; all three are non-``None``, so the handler calls
    ``.asc()``/``.desc()`` on them. ``NotImplementedError`` reaches
    ``map_service_error``, which matches nothing, so the caller cannot tell a
    misspelled sort key from a server fault.
    """
    await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    response = await authed_client.get(PROMPTS, params={"sort_by": sort_by})

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


async def test_filtering_by_template_id_narrows_the_list(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    template = await factories.create_template(db_session)
    wanted = await factories.create_prompt(
        db_session, account=account, template_id=template.id
    )
    await factories.create_prompt(db_session, account=account)
    wanted_id, template_id = str(wanted.id), str(template.id)
    await db_session.commit()

    body = (await authed_client.get(PROMPTS, params={"template_id": template_id})).json()

    assert [item["id"] for item in body["data"]] == [wanted_id]
    assert body["total"] == 1


async def test_filtering_by_ai_model_id_narrows_the_list(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    model = await factories.create_ai_model(db_session)
    wanted = await factories.create_prompt(
        db_session, account=account, ai_model_id=model.id
    )
    await factories.create_prompt(db_session, account=account)
    wanted_id, model_id = str(wanted.id), str(model.id)
    await db_session.commit()

    body = (await authed_client.get(PROMPTS, params={"ai_model_id": model_id})).json()

    assert [item["id"] for item in body["data"]] == [wanted_id]


@pytest.mark.parametrize("field", ["template_id", "ai_model_id"])
async def test_a_malformed_id_filter_is_silently_ignored(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
    field: str,
) -> None:
    """KNOWN DEFECT — the filter is dropped instead of rejected.

    Both parameters are typed ``Optional[str]``, so FastAPI never validates them,
    and the repository wraps each ``UUID(value)`` in ``try/except ValueError:
    pass`` — in ``list_prompts`` *and* in ``count_prompts``. A garbage filter
    therefore returns the caller's entire unfiltered vault with a 200 and a
    matching ``total``, which is the most misleading possible answer: a client
    filtering a list gets back rows that do not match its filter and has no way
    to know. Typing the parameters ``Optional[UUID]`` would give a 422 naming the
    field.
    """
    await factories.create_prompt(db_session, account=account)
    await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    response = await authed_client.get(PROMPTS, params={field: "not-a-uuid"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["total"] == 2


async def test_a_well_formed_but_unknown_id_filter_returns_an_empty_page(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    await factories.create_prompt(db_session, account=account)
    await db_session.commit()

    body = (
        await authed_client.get(PROMPTS, params={"template_id": str(uuid4())})
    ).json()

    assert body["data"] == []
    assert body["total"] == 0


async def test_the_list_never_populates_its_relationship_fields(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT — three eager loads whose results are then thrown away.

    ``list_prompts`` asks for ``selectinload(template)``, ``selectinload(ai_model)``
    and ``selectinload(current_version)``, then serialises with
    ``PromptSummary(**prompt.model_dump())`` — and SQLModel's ``model_dump()``
    returns *columns only*. So the three relationship fields declared on
    ``PromptSummary`` are structurally unreachable: always ``null``, at the cost of
    three extra round trips per page.

    This is load-bearing for the frontend: ``historyService.fetchHistoryStats``
    reads ``p.current_version?.new_analysis`` as its fallback score, and that
    branch can never fire. Either drop the eager loads and the fields, or build
    the response the way ``get_prompt`` does.
    """
    template = await factories.create_template(db_session)
    model = await factories.create_ai_model(db_session)
    prompt = await factories.create_prompt(
        db_session, account=account, template_id=template.id, ai_model_id=model.id
    )
    await factories.create_prompt_version(db_session, prompt=prompt)
    template_id, model_id = str(template.id), str(model.id)
    await db_session.commit()

    item = (await authed_client.get(PROMPTS)).json()["data"][0]

    assert item["template_id"] == template_id
    assert item["ai_model_id"] == model_id
    assert item["current_version_id"] is not None
    assert item["template"] is None
    assert item["ai_model"] is None
    assert item["current_version"] is None


async def test_unknown_query_parameters_are_accepted_and_ignored(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """A client trap rather than a server bug, but worth pinning.

    The route declares no ``search`` and no ``is_favorite``; FastAPI discards
    undeclared query parameters silently. A frontend that grows a search box and
    sends ``?search=`` gets a full unfiltered list back with a 200 and no hint
    that the server ignored it. (Search does exist — as ``POST /prompts/search``,
    which the history page uses instead.)
    """
    await factories.create_prompt(db_session, account=account, title="Findable")
    await factories.create_prompt(db_session, account=account, title="Other")
    await db_session.commit()

    body = (
        await authed_client.get(
            PROMPTS, params={"search": "Findable", "is_favorite": True}
        )
    ).json()

    assert body["total"] == 2


async def test_soft_deleted_prompts_are_hidden_from_the_list(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    await factories.create_prompt(
        db_session, account=account, deleted_at=datetime.now(timezone.utc)
    )
    live = await factories.create_prompt(db_session, account=account)
    live_id = str(live.id)
    await db_session.commit()

    body = (await authed_client.get(PROMPTS)).json()

    assert [item["id"] for item in body["data"]] == [live_id]
    assert body["total"] == 1


async def test_the_list_path_requires_its_trailing_slash(
    authed_client: AsyncClient,
) -> None:
    """Recorded as a client trap. ``redirect_slashes`` builds ``Location`` from the
    request's own host and scheme, so behind a TLS-terminating proxy this 307 can
    point at ``http://`` and a strict client will refuse to follow it."""
    response = await authed_client.get("/api/v1/prompts", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/api/v1/prompts/")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/prompts/{prompt_id} — the detail
# ─────────────────────────────────────────────────────────────────────────────


async def test_the_detail_returns_the_full_prompt(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(
        db_session, account=account, title="Detail", original_prompt="explain recursion"
    )
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.get(f"{PROMPTS}{prompt_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Prompt retrieved."
    data = body["data"]
    assert data["id"] == prompt_id
    assert data["title"] == "Detail"
    assert data["original_prompt"] == "explain recursion"
    assert set(data) >= {
        "id",
        "title",
        "original_prompt",
        "template",
        "ai_model",
        "current_version",
        "version_count",
        "old_analysis",
        "new_analysis",
        "grade",
        "analysis",
        "tool_recommendations",
        "created_at",
        "updated_at",
    }


async def test_the_detail_serialises_the_template_and_the_model(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """Unlike the list, the detail builds each nested object explicitly — so these
    fields are reachable here and not there."""
    template = await factories.create_template(db_session, title="Nested Template")
    model = await factories.create_ai_model(
        db_session, provider=ModelProvider.MISTRAL.value, model_name="nested-model"
    )
    prompt = await factories.create_prompt(
        db_session, account=account, template_id=template.id, ai_model_id=model.id
    )
    prompt_id, template_id, model_id = str(prompt.id), str(template.id), str(model.id)
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    assert data["template"]["id"] == template_id
    assert data["template"]["title"] == "Nested Template"
    assert data["ai_model"]["id"] == model_id
    assert data["ai_model"]["model_name"] == "nested-model"


async def test_the_detail_serialises_the_active_version_and_counts_the_history(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=prompt, content="first")
    latest = await factories.create_prompt_version(
        db_session, prompt=prompt, content="second"
    )
    prompt_id, latest_id = str(prompt.id), str(latest.id)
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    assert data["version_count"] == 2
    assert data["current_version"]["id"] == latest_id
    assert data["current_version"]["content"] == "second"
    assert data["current_version"]["version_number"] == 2


async def test_a_prompt_with_no_versions_reports_a_count_of_zero(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    assert data["version_count"] == 0
    assert data["current_version"] is None


async def test_the_analysis_summary_is_absent_until_the_prompt_has_been_scored(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    assert data["new_analysis"] is None
    assert data["analysis"] is None
    assert data["grade"] is None


async def test_the_analysis_summary_flattens_the_score_and_the_grade(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(
        db_session,
        account=account,
        new_analysis={"overall_score": 88, "clarity": 9, "notes": "keep"},
        grade="A",
    )
    prompt_id = str(prompt.id)
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    assert data["analysis"] == {"overall_score": 88, "grade": "A"}
    assert data["new_analysis"]["clarity"] == 9


async def test_a_scored_prompt_missing_an_overall_score_reads_as_zero(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """``prompt.new_analysis.get("overall_score", 0)`` — an analysis blob written
    by a provider that omitted the key is reported to the UI as a hard zero, which
    is indistinguishable from a genuinely terrible prompt."""
    prompt = await factories.create_prompt(
        db_session, account=account, new_analysis={"clarity": 7}, grade="B"
    )
    prompt_id = str(prompt.id)
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    assert data["analysis"] == {"overall_score": 0, "grade": "B"}


async def test_stored_tool_recommendations_are_returned_verbatim(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    stored = {"matched_task": "Stored Task", "match_type": "stored", "tools": []}
    prompt = await factories.create_prompt(
        db_session, account=account, tool_recommendations=stored
    )
    prompt_id = str(prompt.id)
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    assert data["tool_recommendations"] == stored


async def test_tool_recommendations_are_computed_on_the_fly_when_unset(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """The fallback path, and the fact that it deliberately does not persist.

    The handler carries a comment explaining why it must not commit here — a commit
    would expire the eagerly-loaded relationships it is about to serialise — so the
    computed block is returned but the column stays ``NULL`` and the work is redone
    on every read until the background task writes it.
    """
    prompt = await factories.create_prompt(
        db_session, account=account, original_prompt="write a blog post about testing"
    )
    prompt_id = str(prompt.id)
    prompt_uuid = prompt.id
    await db_session.commit()

    data = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]

    recommendations = data["tool_recommendations"]
    assert set(recommendations) == {
        "matched_task",
        "match_type",
        "match_confidence",
        "tools",
    }
    assert recommendations["tools"]

    db_session.expire_all()
    persisted = await db_session.scalar(
        select(Prompt.tool_recommendations).where(Prompt.id == prompt_uuid)
    )
    assert persisted is None


async def test_an_unknown_prompt_id_is_a_404_with_the_shared_message(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.get(f"{PROMPTS}{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == NOT_FOUND_404


async def test_a_malformed_prompt_id_is_a_generic_400(
    authed_client: AsyncClient,
) -> None:
    """KNOWN DEFECT — ``prompt_id: str`` instead of ``prompt_id: UUID``.

    FastAPI validates nothing, so the raw value reaches ``UUID(id)`` in the
    repository and the resulting ``ValueError`` becomes the catch-all 400.
    Declaring the path parameter as ``UUID`` would return a 422 that names it, and
    would do so before any database work.
    """
    response = await authed_client.get(f"{PROMPTS}not-a-uuid")

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


async def test_the_malformed_id_error_leaks_no_internals(
    authed_client: AsyncClient,
) -> None:
    """VULN-014 regression guard: the generic mapper is what keeps SQL, table
    names and stack frames out of the response body."""
    body = (await authed_client.get(f"{PROMPTS}'; DROP TABLE prompts; --")).text.lower()

    for leak in ("traceback", "sqlalchemy", "asyncpg", "select ", "prompts.", "uuid("):
        assert leak not in body, leak


@pytest.mark.parametrize("mangle", [str.upper, lambda value: value.replace("-", "")])
async def test_a_non_canonical_uuid_still_resolves(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
    mangle: Any,
) -> None:
    """``UUID(str)`` accepts upper case and the dashless form, so these are the
    same prompt. Harmless here — but ``/similar/{id}`` compares that raw string
    to a canonical one, which is how the self-exclusion bug below happens."""
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.get(f"{PROMPTS}{mangle(prompt_id)}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == prompt_id


async def test_a_soft_deleted_prompt_is_a_404(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(
        db_session, account=account, deleted_at=datetime.now(timezone.utc)
    )
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.get(f"{PROMPTS}{prompt_id}")

    assert response.status_code == 404


async def test_another_users_prompt_is_a_404_and_not_a_403(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """``_assert_owner`` raises ``PromptNotFoundError`` on purpose: a 403 would
    confirm the id exists and make the vault enumerable."""
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger)
    theirs_id = str(theirs.id)
    await db_session.commit()

    response = await authed_client.get(f"{PROMPTS}{theirs_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == NOT_FOUND_404


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/v1/prompts/{prompt_id}
# ─────────────────────────────────────────────────────────────────────────────


async def test_deleting_a_prompt_removes_the_row(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = prompt.id
    await db_session.commit()

    response = await authed_client.delete(f"{PROMPTS}{prompt_id}")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Prompt deleted successfully.",
        "data": None,
    }
    db_session.expire_all()
    assert not await exists(db_session, prompt_id)


async def test_a_deleted_prompt_is_gone_rather_than_flagged(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT — ``settings.enable_soft_delete`` is ``True`` and unused here.

    Every read path in the repository filters on ``deleted_at IS NULL``, so the
    feature is half-wired: the reads honour a column that nothing in this router
    ever writes. ``PromptService.delete_prompt`` issues a real ``DELETE`` under
    the comment "Vault deletion is permanent", which means an accidental delete is
    unrecoverable and the flag misrepresents the system's behaviour to anyone
    reading the config. Either write ``deleted_at`` when the flag is on, or drop
    the flag and the read filters together.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = prompt.id
    await db_session.commit()

    await authed_client.delete(f"{PROMPTS}{prompt_id}")

    db_session.expire_all()
    remaining = await db_session.scalar(
        select(func.count()).select_from(Prompt).where(Prompt.id == prompt_id)
    )
    assert remaining == 0


async def test_deleting_a_prompt_takes_its_versions_with_it(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """The database's ``ON DELETE CASCADE`` on ``prompt_versions.prompt_id`` does
    this, not the ORM — see house rule 5 for why that distinction matters."""
    prompt = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=prompt)
    await factories.create_prompt_version(db_session, prompt=prompt)
    prompt_id = prompt.id
    await db_session.commit()

    response = await authed_client.delete(f"{PROMPTS}{prompt_id}")

    assert response.status_code == 200
    db_session.expire_all()
    left = await db_session.scalar(
        select(func.count())
        .select_from(PromptVersion)
        .where(PromptVersion.prompt_id == prompt_id)
    )
    assert left == 0


async def test_the_detail_is_a_404_after_the_delete(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    await authed_client.delete(f"{PROMPTS}{prompt_id}")

    assert (await authed_client.get(f"{PROMPTS}{prompt_id}")).status_code == 404


async def test_deleting_twice_is_not_idempotent(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """A retried DELETE — after a dropped connection, say — reports failure for
    work that succeeded. Worth knowing before wiring a retrying client to it."""
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    first = await authed_client.delete(f"{PROMPTS}{prompt_id}")
    second = await authed_client.delete(f"{PROMPTS}{prompt_id}")

    assert first.status_code == 200
    assert second.status_code == 404


async def test_deleting_another_users_prompt_is_refused_and_leaves_it_intact(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger)
    theirs_id = theirs.id
    await db_session.commit()

    response = await authed_client.delete(f"{PROMPTS}{theirs_id}")

    assert response.status_code == 404
    db_session.expire_all()
    assert await exists(db_session, theirs_id)


@pytest.mark.parametrize(
    ("prompt_id", "expected"), [("not-a-uuid", 400), (None, 404)], ids=["malformed", "unknown"]
)
async def test_deleting_a_bad_id(
    authed_client: AsyncClient, prompt_id: str | None, expected: int
) -> None:
    target = prompt_id if prompt_id is not None else str(uuid4())

    response = await authed_client.delete(f"{PROMPTS}{target}")

    assert response.status_code == expected


async def test_deleting_one_prompt_leaves_the_others_alone(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    doomed = await factories.create_prompt(db_session, account=account)
    keeper = await factories.create_prompt(db_session, account=account)
    doomed_id, keeper_id = doomed.id, keeper.id
    await db_session.commit()

    await authed_client.delete(f"{PROMPTS}{doomed_id}")

    db_session.expire_all()
    assert not await exists(db_session, doomed_id)
    assert await exists(db_session, keeper_id)
    assert await rows_for(db_session, account.id) == 1


async def test_a_delete_after_reading_the_detail_still_succeeds(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """The harness-only trap from house rule 5, asserted so it cannot silently
    come back: with ``expire_all()`` standing in for production's per-request
    session, detail-then-delete is a clean 200."""
    prompt = await factories.create_prompt(db_session, account=account)
    await factories.create_prompt_version(db_session, prompt=prompt)
    prompt_id = str(prompt.id)
    await db_session.commit()

    assert (await authed_client.get(f"{PROMPTS}{prompt_id}")).status_code == 200
    db_session.expire_all()

    assert (await authed_client.delete(f"{PROMPTS}{prompt_id}")).status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/prompts/similar/{prompt_id}
# ─────────────────────────────────────────────────────────────────────────────


async def test_similar_prompts_come_back_with_a_score(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """The stub embedding is a deterministic lexical hash, so two prompts with
    identical text are exactly co-directional and score 1.0. That is what makes
    an assertion on the *value* legitimate here — cross-corpus comparisons against
    the cloned rows' real MiniLM vectors are noise and are never asserted on."""
    query = await factories.create_prompt(
        db_session, account=account, original_prompt="tune a postgres index"
    )
    twin = await factories.create_prompt(
        db_session, account=account, original_prompt="tune a postgres index"
    )
    query_id, twin_id = str(query.id), str(twin.id)
    await db_session.commit()

    response = await authed_client.get(f"{PROMPTS}similar/{query_id}")

    assert response.status_code == 200
    body = response.json()
    matches = {match["prompt_id"]: match for match in body["results"]}
    assert twin_id in matches
    assert matches[twin_id]["similarity_score"] == pytest.approx(1.0, abs=1e-6)
    assert set(matches[twin_id]) >= {"prompt_id", "title", "similarity_score"}
    assert body["message"] == f"Found {len(body['results'])} similar prompts."


async def test_a_prompt_is_not_similar_to_itself(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    body = (await authed_client.get(f"{PROMPTS}similar/{prompt_id}")).json()

    assert prompt_id not in [match["prompt_id"] for match in body["results"]]


async def test_an_uppercase_id_makes_a_prompt_similar_to_itself(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT — the self-exclusion compares strings, not UUIDs.

    The handler filters with ``r["prompt_id"] != prompt_id``, where the left side
    is the service's canonical lower-case ``str(uuid)`` and the right side is
    whatever the caller typed in the path. ``UUID()`` accepts upper case — the
    detail route serves it happily — so an upper-case id defeats the filter: the
    prompt is returned as its own nearest match at similarity 1.0, and
    ``len(results)`` is one higher than the caller asked for because the ``+1``
    fetched to make room for the exclusion is never consumed. Comparing
    ``UUID(r["prompt_id"]) != UUID(prompt_id)`` fixes both.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    body = (await authed_client.get(f"{PROMPTS}similar/{prompt_id.upper()}")).json()

    matches = {match["prompt_id"]: match for match in body["results"]}
    assert prompt_id in matches
    assert matches[prompt_id]["similarity_score"] == pytest.approx(1.0, abs=1e-6)


async def test_similar_leaks_other_users_prompts(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT (SECURITY) — cross-user disclosure of prompt bodies.

    ``_assert_owner`` guards the *query* prompt, and then
    ``PromptSimilarityService.search_similar_prompts`` runs an unfiltered vector
    search over the whole ``prompts`` table. The repository underneath it *has* a
    ``user_id`` parameter; the service neither accepts nor passes one, and the
    route supplies nothing. Each match carries ``title``, ``original_prompt``,
    ``old_analysis``, ``new_analysis`` and ``grade``, so any authenticated user can
    read every other user's prompt text — and, by varying the query text, walk the
    whole corpus.

    The sibling ``POST /prompts/search`` forces ``user_id=str(user_id)`` under a
    comment naming the same hardening ticket the list route cites, which is the
    evidence this is an oversight rather than a decision. ``/duplicates`` and
    ``/recommendations`` share the flaw (pinned in ``test_search.py``).

    Asserted as the leak it is: this test must fail the moment the scoping lands.
    """
    secret = "internal salary review memo for the board"
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(
        db_session, account=stranger, title="Their Private Prompt", original_prompt=secret
    )
    mine = await factories.create_prompt(db_session, account=account, original_prompt=secret)
    mine_id, theirs_id = str(mine.id), str(theirs.id)
    await db_session.commit()

    body = (await authed_client.get(f"{PROMPTS}similar/{mine_id}")).json()

    matches = {match["prompt_id"]: match for match in body["results"]}
    assert theirs_id in matches
    assert matches[theirs_id]["title"] == "Their Private Prompt"
    assert matches[theirs_id]["original_prompt"] == secret


async def test_the_active_version_content_is_what_gets_searched(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """``query_text`` prefers ``current_version.content`` over ``original_prompt``,
    so an enhanced prompt finds neighbours of its *enhanced* text."""
    enhanced = "orchestrate a kubernetes rollout with zero downtime"
    query = await factories.create_prompt(
        db_session, account=account, original_prompt="unrelated original text"
    )
    await factories.create_prompt_version(db_session, prompt=query, content=enhanced)
    twin = await factories.create_prompt(
        db_session, account=account, original_prompt=enhanced
    )
    query_id, twin_id = str(query.id), str(twin.id)
    await db_session.commit()

    body = (await authed_client.get(f"{PROMPTS}similar/{query_id}")).json()

    matches = {match["prompt_id"]: match for match in body["results"]}
    assert twin_id in matches
    assert matches[twin_id]["similarity_score"] == pytest.approx(1.0, abs=1e-6)


async def test_the_limit_caps_the_number_of_matches(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    query = await factories.create_prompt(db_session, account=account)
    for index in range(4):
        await factories.create_prompt(db_session, account=account, title=f"Near {index}")
    query_id = str(query.id)
    await db_session.commit()

    body = (
        await authed_client.get(f"{PROMPTS}similar/{query_id}", params={"limit": 2})
    ).json()

    assert len(body["results"]) == 2
    assert body["message"] == "Found 2 similar prompts."


async def test_a_limit_of_zero_means_the_default_rather_than_nothing(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT — ``limit or 10`` treats a legitimate 0 as "unset".

    ``limit=0`` is falsy, so both the search size and the final slice fall back to
    10 and the caller that asked for no results gets ten. ``Query(default=None,
    ge=1)`` would reject it instead.
    """
    query = await factories.create_prompt(db_session, account=account)
    for index in range(3):
        await factories.create_prompt(db_session, account=account, title=f"Filler {index}")
    query_id = str(query.id)
    await db_session.commit()

    body = (
        await authed_client.get(f"{PROMPTS}similar/{query_id}", params={"limit": 0})
    ).json()

    assert len(body["results"]) > 0


async def test_a_negative_limit_is_a_generic_400(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """KNOWN DEFECT — the unvalidated ``limit`` reaches SQL.

    ``search_limit = limit + 1`` stays negative, Postgres rejects ``LIMIT -4``, and
    the driver error is flattened into the catch-all 400. A ``ge=1`` bound would
    turn a client typo into a 422 that names the parameter instead of something
    that reads like a server fault.
    """
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await authed_client.get(
        f"{PROMPTS}similar/{prompt_id}", params={"limit": -5}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_400


async def test_similar_for_an_unowned_or_unknown_prompt_is_a_404(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(db_session, account=stranger)
    theirs_id = str(theirs.id)
    await db_session.commit()

    assert (await authed_client.get(f"{PROMPTS}similar/{theirs_id}")).status_code == 404
    assert (await authed_client.get(f"{PROMPTS}similar/{uuid4()}")).status_code == 404


async def test_similar_for_a_malformed_id_is_a_generic_400(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.get(f"{PROMPTS}similar/not-a-uuid")

    assert response.status_code == 400


async def test_a_prompt_with_no_embedding_is_never_a_match(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """``search_prompts_with_vector`` filters ``Prompt.embedding != None``, so a
    row whose embedding failed to generate is invisible to similarity search —
    silently, with no error to tell anyone it dropped out of the corpus."""
    query = await factories.create_prompt(
        db_session, account=account, original_prompt="identical text for matching"
    )
    invisible = await factories.create_prompt(
        db_session,
        account=account,
        original_prompt="identical text for matching",
        embedding=None,
    )
    query_id, invisible_id = str(query.id), str(invisible.id)
    await db_session.commit()

    body = (await authed_client.get(f"{PROMPTS}similar/{query_id}")).json()

    assert invisible_id not in [match["prompt_id"] for match in body["results"]]


async def test_a_soft_deleted_prompt_is_never_a_match(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    query = await factories.create_prompt(
        db_session, account=account, original_prompt="soft delete corpus check"
    )
    hidden = await factories.create_prompt(
        db_session,
        account=account,
        original_prompt="soft delete corpus check",
        deleted_at=datetime.now(timezone.utc),
    )
    query_id, hidden_id = str(query.id), str(hidden.id)
    await db_session.commit()

    body = (await authed_client.get(f"{PROMPTS}similar/{query_id}")).json()

    assert hidden_id not in [match["prompt_id"] for match in body["results"]]


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────


def prompt_operations() -> list[tuple[str, str]]:
    """Every ``/api/v1/prompts`` operation, read from the app's own OpenAPI doc.

    Enumerated rather than hand-listed so a route added later is covered without
    anyone remembering to add it here. ``app.routes`` cannot be walked for this —
    it holds lazy ``_IncludedRouter`` objects — but ``openapi()`` is fully resolved.
    """
    paths = create_app().openapi()["paths"]
    operations = []
    for path, methods in paths.items():
        if not path.startswith("/api/v1/prompts"):
            continue
        for method in methods:
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                operations.append((method.lower(), path))
    return sorted(operations)


async def test_every_prompt_route_rejects_an_anonymous_caller(
    client: AsyncClient,
) -> None:
    """The whole surface at once, including the SSE routes.

    ``get_current_user_id`` is a sub-dependency, so it resolves before the request
    body is validated — an unauthenticated POST with a bogus body must still be a
    401 rather than a 422 that reveals the schema.
    """
    operations = prompt_operations()
    assert len(operations) >= 11, operations

    outcomes = {}
    for method, path in operations:
        url = (
            path.replace("{prompt_id}", str(uuid4()))
            .replace("{version}", "1")
            .replace("{style_id}", str(uuid4()))
        )
        response = await client.request(
            method, url, json={} if method in {"post", "put", "patch"} else None
        )
        outcomes[f"{method.upper()} {path}"] = response.status_code

    assert set(outcomes.values()) == {401}, outcomes


async def test_the_bearer_header_authenticates_as_well_as_the_cookie(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    prompt = await factories.create_prompt(db_session, account=account)
    prompt_id = str(prompt.id)
    await db_session.commit()

    response = await client.get(f"{PROMPTS}{prompt_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["id"] == prompt_id


async def test_an_expired_token_is_rejected(
    client: AsyncClient, account: factories.Account
) -> None:
    from app.core.security import create_access_token

    expired = create_access_token(
        {"sub": str(account.id)}, expires_delta=timedelta(minutes=-5)
    )

    response = await client.get(PROMPTS, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


async def test_a_tampered_token_is_rejected(
    client: AsyncClient, access_token: str
) -> None:
    header, payload, signature = access_token.split(".")
    forged = f"{header}.{payload}.{signature[:-2]}xx"

    response = await client.get(PROMPTS, headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


async def test_a_token_for_a_user_with_no_prompts_sees_an_empty_vault(
    client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    """A valid token for a user who owns nothing is a 200 with an empty page — not
    a 404 and not someone else's data."""
    from tests.conftest import token_for

    await factories.create_prompt(db_session, account=account)
    stranger = await factories.create_account(db_session)
    await db_session.commit()

    response = await client.get(
        PROMPTS, headers={"Authorization": f"Bearer {token_for(stranger.id)}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["total"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Round trip
# ─────────────────────────────────────────────────────────────────────────────


async def test_list_then_read_then_delete_using_only_api_supplied_ids(
    authed_client: AsyncClient, db_session: AsyncSession, account: factories.Account
) -> None:
    prompt = await factories.create_prompt(db_session, account=account, title="Round Trip")
    await factories.create_prompt_version(db_session, prompt=prompt)
    await db_session.commit()

    listed = (await authed_client.get(PROMPTS)).json()["data"]
    assert [item["title"] for item in listed] == ["Round Trip"]
    prompt_id = listed[0]["id"]

    detail = (await authed_client.get(f"{PROMPTS}{prompt_id}")).json()["data"]
    assert detail["version_count"] == 1
    db_session.expire_all()

    assert (await authed_client.delete(f"{PROMPTS}{prompt_id}")).status_code == 200
    assert (await authed_client.get(PROMPTS)).json()["total"] == 0

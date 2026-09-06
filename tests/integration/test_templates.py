"""Integration tests for ``app/api/v1/templates.py`` — the template list surface.

Templates are the highest-value rows in the database: the enhance pipeline selects
an *approved* template by vector similarity and renders the user's prompt into its
``body`` before sending it to the LLM. So a template body is both the product's
proprietary asset and, effectively, executable input to the model.

``GET /templates/`` is the one route the product actually calls. Two properties
shape the tests below.

**The list is unauthenticated but withholds the body.** ``TemplateListItem``
deliberately drops ``body`` so the proprietary asset never reaches the client,
even though the route itself takes no auth dependency.

**Pagination reports the page size, not the match count.** ``total`` is
``len(templates)`` for the current page rather than the number of rows the filter
matched, so a client cannot derive the number of pages from it. That is pinned as
a defect rather than asserted as intended.

Rows are always created by the test itself. The database is a clone of dev with 170
templates in it, so nothing here asserts a count or an id it did not write.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests import factories

pytestmark = pytest.mark.integration

TEMPLATES = "/api/v1/templates/"


# ─────────────────────────────────────────────────────────────────────────────
# GET /templates/ — list
# ─────────────────────────────────────────────────────────────────────────────


async def test_the_list_omits_the_template_body(
    client: AsyncClient, db_session
) -> None:
    """``TemplateListItem`` deliberately drops ``body``.

    Scoped to a freshly created model so the page contains exactly one row and the
    check cannot be diluted by the cloned corpus. Asserted on the serialised *keys*
    rather than on a value, because a ``body`` of ``None`` would satisfy a value
    check while still leaking the field.
    """
    secret = "PROPRIETARY RECIPE — do not leak. {{prompt}}"
    model = await factories.create_ai_model(db_session)
    await factories.create_template(db_session, ai_model_id=model.id, body=secret)
    await db_session.commit()

    response = await client.get(TEMPLATES, params={"ai_model_id": str(model.id)})

    assert response.status_code == 200, response.text
    items = response.json()["data"]
    assert len(items) == 1
    assert "body" not in items[0]
    assert secret not in response.text


async def test_the_list_envelope_carries_pagination_fields(
    client: AsyncClient, db_session
) -> None:
    await factories.create_template(db_session)
    await db_session.commit()

    response = await client.get(TEMPLATES, params={"limit": 5, "offset": 10})

    envelope = response.json()
    assert envelope["success"] is True
    assert envelope["message"] == "Template list retrieved."
    assert envelope["page_size"] == 5
    assert envelope["page"] == 3  # offset // limit + 1
    assert isinstance(envelope["data"], list)


async def test_total_reports_the_page_size_not_the_match_count(
    client: AsyncClient, db_session
) -> None:
    """KNOWN DEFECT — ``total=len(templates)`` counts the rows on *this page*.

    The handler never issues a ``COUNT``, so ``total`` can never exceed ``limit``.
    With 170 approved templates in the database and ``limit=2``, a client is told
    the total is 2 and concludes there is a single page. Any UI that derives a page
    count from ``total`` therefore shows exactly one page regardless of the corpus
    size — which is consistent with the frontend having to paginate by
    "did I get a full page back?" instead.

    The fix is a second ``SELECT count(*)`` with the same filters. Asserted on the
    relationship (``total == len(data)``) rather than on 170, so the cloned-data
    rule holds.
    """
    for _ in range(3):
        await factories.create_template(db_session)
    await db_session.commit()

    response = await client.get(TEMPLATES, params={"limit": 2, "is_approved": True})

    envelope = response.json()
    assert len(envelope["data"]) == 2
    assert envelope["total"] == 2


async def test_limit_and_offset_walk_the_result_set(
    client: AsyncClient, db_session
) -> None:
    """Ordering is unspecified — the query has no ``ORDER BY`` — so this asserts
    only that the two pages are disjoint, which is the property a caller actually
    relies on. Pinning a specific order would be asserting something Postgres does
    not promise."""
    model = await factories.create_ai_model(db_session)
    for _ in range(4):
        await factories.create_template(db_session, ai_model_id=model.id)
    await db_session.commit()
    params = {"ai_model_id": str(model.id)}

    first = await client.get(TEMPLATES, params={**params, "limit": 2, "offset": 0})
    second = await client.get(TEMPLATES, params={**params, "limit": 2, "offset": 2})

    first_ids = {item["id"] for item in first.json()["data"]}
    second_ids = {item["id"] for item in second.json()["data"]}
    assert len(first_ids) == 2
    assert len(second_ids) == 2
    assert first_ids.isdisjoint(second_ids)


async def test_an_offset_past_the_end_returns_an_empty_page(
    client: AsyncClient, db_session
) -> None:
    model = await factories.create_ai_model(db_session)
    await factories.create_template(db_session, ai_model_id=model.id)
    await db_session.commit()

    response = await client.get(
        TEMPLATES, params={"ai_model_id": str(model.id), "offset": 50}
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == []
    assert response.json()["total"] == 0


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}],
    ids=["limit-0", "limit-101", "negative-offset"],
)
async def test_the_list_enforces_its_pagination_bounds(
    client: AsyncClient, params: dict[str, int]
) -> None:
    """``ge=1, le=100`` on ``limit`` and ``ge=0`` on ``offset``. The upper bound is
    the only thing stopping a single request from serialising the whole table."""
    response = await client.get(TEMPLATES, params=params)

    assert response.status_code == 422, response.text


async def test_filtering_by_ai_model_returns_only_that_models_templates(
    client: AsyncClient, db_session
) -> None:
    """The cleanest available isolation from cloned data: a freshly created model
    owns nothing else, so an exact set comparison is legitimate here."""
    mine = await factories.create_ai_model(db_session)
    theirs = await factories.create_ai_model(db_session)
    a = await factories.create_template(db_session, ai_model_id=mine.id)
    b = await factories.create_template(db_session, ai_model_id=mine.id)
    await factories.create_template(db_session, ai_model_id=theirs.id)
    expected = {str(a.id), str(b.id)}
    await db_session.commit()

    response = await client.get(TEMPLATES, params={"ai_model_id": str(mine.id)})

    assert {item["id"] for item in response.json()["data"]} == expected


async def test_filtering_by_mode_is_case_sensitive(
    client: AsyncClient, db_session
) -> None:
    """``Template.mode == mode``, no ``lower()`` on either side — unlike the
    ``role`` filter two lines below it in the same query builder. A caller who
    sends ``mode=Concise`` gets nothing back for a template stored as
    ``concise``.

    KNOWN DEFECT, and specifically an *inconsistency*: ``role`` is compared with
    ``func.lower()`` on both sides, ``mode`` and ``category`` are not. The
    asymmetry inside one function is the evidence that it was not deliberate.
    """
    model = await factories.create_ai_model(db_session)
    template = await factories.create_template(
        db_session, ai_model_id=model.id, mode="concise"
    )
    template_id = str(template.id)
    await db_session.commit()
    params = {"ai_model_id": str(model.id)}

    exact = await client.get(TEMPLATES, params={**params, "mode": "concise"})
    wrong_case = await client.get(TEMPLATES, params={**params, "mode": "Concise"})

    assert [item["id"] for item in exact.json()["data"]] == [template_id]
    assert wrong_case.json()["data"] == []


async def test_filtering_by_role_is_case_insensitive(
    client: AsyncClient, db_session
) -> None:
    """The counterpart: ``func.lower(Template.role) == func.lower(role)``, so this
    one does what a user expects. Both halves are pinned so the pair reads as a
    single finding rather than two unrelated tests."""
    model = await factories.create_ai_model(db_session)
    template = await factories.create_template(
        db_session, ai_model_id=model.id, role="Marketer"
    )
    template_id = str(template.id)
    await db_session.commit()
    params = {"ai_model_id": str(model.id)}

    for role in ("Marketer", "marketer", "MARKETER"):
        response = await client.get(TEMPLATES, params={**params, "role": role})
        assert [item["id"] for item in response.json()["data"]] == [template_id], role


async def test_filtering_by_category_is_case_sensitive(
    client: AsyncClient, db_session
) -> None:
    model = await factories.create_ai_model(db_session)
    await factories.create_template(
        db_session, ai_model_id=model.id, category="Writing"
    )
    await db_session.commit()
    params = {"ai_model_id": str(model.id)}

    exact = await client.get(TEMPLATES, params={**params, "category": "Writing"})
    wrong_case = await client.get(TEMPLATES, params={**params, "category": "writing"})

    assert len(exact.json()["data"]) == 1
    assert wrong_case.json()["data"] == []


async def test_the_approved_filter_partitions_the_result_set(
    client: AsyncClient, db_session
) -> None:
    model = await factories.create_ai_model(db_session)
    approved = await factories.create_template(
        db_session, ai_model_id=model.id, is_approved=True
    )
    pending = await factories.create_template(
        db_session, ai_model_id=model.id, is_approved=False
    )
    approved_id, pending_id = str(approved.id), str(pending.id)
    await db_session.commit()
    params = {"ai_model_id": str(model.id)}

    yes = await client.get(TEMPLATES, params={**params, "is_approved": "true"})
    no = await client.get(TEMPLATES, params={**params, "is_approved": "false"})
    unfiltered = await client.get(TEMPLATES, params=params)

    assert [item["id"] for item in yes.json()["data"]] == [approved_id]
    assert [item["id"] for item in no.json()["data"]] == [pending_id]
    assert {item["id"] for item in unfiltered.json()["data"]} == {approved_id, pending_id}


async def test_unapproved_templates_are_listed_to_anyone(
    client: AsyncClient, db_session
) -> None:
    """``is_approved`` defaults to ``None``, meaning *no filter* — so the public
    list includes drafts nobody has reviewed. Combined with the missing
    authentication, a submitted-but-unapproved template is visible to every
    caller the moment it is created."""
    model = await factories.create_ai_model(db_session)
    draft = await factories.create_template(
        db_session, ai_model_id=model.id, is_approved=False
    )
    draft_id = str(draft.id)
    await db_session.commit()

    response = await client.get(TEMPLATES, params={"ai_model_id": str(model.id)})

    assert [item["id"] for item in response.json()["data"]] == [draft_id]


async def test_the_featured_filter_partitions_the_result_set(
    client: AsyncClient, db_session
) -> None:
    model = await factories.create_ai_model(db_session)
    featured = await factories.create_template(
        db_session, ai_model_id=model.id, is_featured=True
    )
    featured_id = str(featured.id)
    await factories.create_template(db_session, ai_model_id=model.id, is_featured=False)
    await db_session.commit()
    params = {"ai_model_id": str(model.id)}

    response = await client.get(TEMPLATES, params={**params, "is_featured": "true"})

    assert [item["id"] for item in response.json()["data"]] == [featured_id]


async def test_only_active_models_drops_templates_on_a_disabled_model(
    client: AsyncClient, db_session
) -> None:
    """An inner join onto ``ai_models`` with ``is_active == True``. This is the
    kill switch: disabling a model has to remove its templates from the library in
    one step, or the UI keeps offering enhancements that cannot run."""
    live = await factories.create_ai_model(db_session, is_active=True)
    retired = await factories.create_ai_model(db_session, is_active=False)
    on_live = await factories.create_template(db_session, ai_model_id=live.id)
    on_retired = await factories.create_template(db_session, ai_model_id=retired.id)
    on_live_id, on_retired_id = str(on_live.id), str(on_retired.id)
    await db_session.commit()

    filtered = await client.get(
        TEMPLATES,
        params={"ai_model_id": str(retired.id), "only_active_models": "true"},
    )
    unfiltered = await client.get(
        TEMPLATES, params={"ai_model_id": str(retired.id)}
    )
    still_listed = await client.get(
        TEMPLATES, params={"ai_model_id": str(live.id), "only_active_models": "true"}
    )

    assert filtered.json()["data"] == []
    assert [item["id"] for item in unfiltered.json()["data"]] == [on_retired_id]
    assert [item["id"] for item in still_listed.json()["data"]] == [on_live_id]


async def test_only_active_models_defaults_to_off(
    client: AsyncClient, db_session
) -> None:
    """``Query(default=False)`` — so the *default* library view includes templates
    whose model is disabled. Worth pinning next to the test above: the kill switch
    only works if the caller opts in."""
    retired = await factories.create_ai_model(db_session, is_active=False)
    template = await factories.create_template(db_session, ai_model_id=retired.id)
    template_id = str(template.id)
    await db_session.commit()

    response = await client.get(TEMPLATES, params={"ai_model_id": str(retired.id)})

    assert [item["id"] for item in response.json()["data"]] == [template_id]


async def test_filters_combine_as_a_conjunction(
    client: AsyncClient, db_session
) -> None:
    model = await factories.create_ai_model(db_session)
    match = await factories.create_template(
        db_session,
        ai_model_id=model.id,
        mode="concise",
        category="writing",
        is_approved=True,
    )
    match_id = str(match.id)
    await factories.create_template(
        db_session, ai_model_id=model.id, mode="concise", category="code", is_approved=True
    )
    await factories.create_template(
        db_session,
        ai_model_id=model.id,
        mode="concise",
        category="writing",
        is_approved=False,
    )
    await db_session.commit()

    response = await client.get(
        TEMPLATES,
        params={
            "ai_model_id": str(model.id),
            "mode": "concise",
            "category": "writing",
            "is_approved": "true",
        },
    )

    assert [item["id"] for item in response.json()["data"]] == [match_id]


async def test_an_unknown_filter_value_returns_an_empty_page_not_an_error(
    client: AsyncClient
) -> None:
    """``mode`` and ``category`` are free-text strings, not enums, so a typo is a
    silent empty result rather than a 422. Pinned because it is the failure mode a
    frontend bug looks like from the server side."""
    response = await client.get(TEMPLATES, params={"mode": "no-such-mode-ever"})

    assert response.status_code == 200, response.text
    assert response.json()["data"] == []


async def test_the_list_path_requires_the_trailing_slash(
    client: AsyncClient
) -> None:
    """``/api/v1/templates`` answers ``307`` to ``/api/v1/templates/``.

    Recorded because it is a real client-side trap rather than a defect: a 307
    preserves the method and body, so it is safe, but the ``Location`` header is
    built from the request's own host — behind a proxy that terminates TLS this
    can redirect an HTTPS caller to an ``http://`` URL. httpx does not follow
    redirects by default, which is why every request in this file uses the slash.
    """
    response = await client.get("/api/v1/templates")

    assert response.status_code == 307
    assert response.headers["location"].endswith("/api/v1/templates/")

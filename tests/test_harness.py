"""Tests of the test harness.

Every other test in this repository rests on four claims made by
``tests/conftest.py``: that it is aimed at a clone of dev rather than dev itself,
that each test's writes are discarded, that no LLM call or model load can escape
to the outside world, and that the auth fixtures actually authenticate. If any of
those is quietly false, the whole suite becomes misleading rather than merely
broken — a green run against the dev database is worse than a red one.

So they are asserted here, first, before anything is built on them. This file is
the step-1 gate: it must pass before a single application test is written.

Two of the tests below are a deliberate ordered pair
(``…__part1_writes`` / ``…__part2_verifies_gone``). Proving isolation *requires*
looking across a test boundary — a single test cannot observe its own rollback.
They rely on pytest running tests in declaration order within a file, and each
carries an assertion message explaining the coupling so nobody reorders them by
accident.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_embedding_service, get_llm_provider
from app.core import redis_client
from app.core.config import settings
from app.core.security import verify_password
from app.db import session as db_session_module
from app.db.models import Profile, Template, User
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.embedding_service import EmbeddingService
from app.services.llm.mistral_provider import MistralProvider
from tests import factories
from tests.conftest import TEST_DATABASE_URL
from tests.constants import TEST_USER_EMAIL, TEST_USER_PASSWORD
from tests.stubs.embedding import EMBEDDING_DIM, hashed_embedding
from tests.stubs.llm import UNROUTED_MARKER, StubLLMProvider

pytestmark = pytest.mark.integration

PROTECTED_ROUTE = "/api/v1/profile/me"

# Shared between the two halves of each isolation pair. A domain no cloned row
# uses, so a stale match could only ever come from this file.
ROLLBACK_PROBE_EMAIL = "rollback-probe@harness.test"
COMMIT_PROBE_EMAIL = "commit-probe@harness.test"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Aimed at the right database
# ─────────────────────────────────────────────────────────────────────────────


def test_resolved_url_is_a_test_database() -> None:
    name = make_url(TEST_DATABASE_URL).database or ""
    assert name.endswith("_test"), (
        f"Resolved test database {name!r} does not end in '_test'. The conftest "
        "guard should have refused to start."
    )


def test_settings_and_app_engine_both_point_at_it() -> None:
    """The rewrite has to have landed before app.db.session built its engine.

    If this fails, the application's own engine — and therefore the background
    task at app/api/v1/enhancement.py, which imports async_session lazily — is
    still talking to the development database.
    """
    assert settings.database_url == TEST_DATABASE_URL
    assert (db_session_module.engine.url.database or "").endswith("_test")


async def test_server_reports_a_test_database(db_session: AsyncSession) -> None:
    """Asserts what the server actually connected to, not what the URL says."""
    current = await db_session.scalar(text("SELECT current_database()"))
    assert str(current).endswith("_test")


# ─────────────────────────────────────────────────────────────────────────────
# 2. The clone carried the data across
# ─────────────────────────────────────────────────────────────────────────────


async def test_cloned_templates_are_visible(db_session: AsyncSession) -> None:
    """An invariant, not a count: the corpus size drifts with dev usage."""
    total = await db_session.scalar(select(text("count(*)")).select_from(Template))
    assert total > 0, (
        "No templates in the test database. Run scripts/bootstrap_test_db.sh clone."
    )


async def test_cloned_templates_carry_real_384_dim_vectors(
    cloned_template: Template | None,
) -> None:
    """Semantic-search tests are only meaningful if the vectors came across.

    pgvector stores the dimension in the column type, so a wrong length here
    would mean the restore silently produced a different schema.
    """
    assert cloned_template is not None, "No approved template with an embedding."
    assert len(cloned_template.embedding) == EMBEDDING_DIM


async def test_bootstrap_user_can_authenticate(bootstrap_user: User) -> None:
    """Cloned accounts hash unknown plaintext; this one is upserted for us.

    Verifying the password here — rather than in the first auth test that needs
    it — means a bootstrap script that silently skipped the upsert is reported as
    a harness failure instead of an authentication bug.
    """
    assert bootstrap_user.email == TEST_USER_EMAIL
    assert verify_password(TEST_USER_PASSWORD, bootstrap_user.hashed_password)
    assert bootstrap_user.is_active


# ─────────────────────────────────────────────────────────────────────────────
# 3. Isolation — the property the old suite did not have
# ─────────────────────────────────────────────────────────────────────────────


async def test_rollback_isolation__part1_writes(db_session: AsyncSession) -> None:
    """Paired with part2. Writes a row and confirms it is visible in-test."""
    await factories.create_account(db_session, email=ROLLBACK_PROBE_EMAIL)

    found = await db_session.scalar(
        select(User).where(User.email == ROLLBACK_PROBE_EMAIL)
    )
    assert found is not None, "The row is not even visible to the test that wrote it."


async def test_rollback_isolation__part2_verifies_gone(
    db_session: AsyncSession,
) -> None:
    """Paired with part1 above; it must run after it.

    A failure here means the outer transaction is being committed and the suite
    is accumulating rows in the database — the exact defect the old
    ``DELETE ... WHERE title LIKE '%Test%'`` cleanup existed to paper over.
    """
    leaked = await db_session.scalar(
        select(User).where(User.email == ROLLBACK_PROBE_EMAIL)
    )
    assert leaked is None, (
        f"{ROLLBACK_PROBE_EMAIL} survived from the previous test. Rollback "
        "isolation is broken: check join_transaction_mode on the db_session "
        "fixture. (This test must run after …__part1_writes.)"
    )


async def test_commit_inside_the_transaction__part1_commits(
    db_session: AsyncSession,
) -> None:
    """``commit()`` must be a savepoint release, not a real commit.

    This is the specific mechanism that makes the harness work at all:
    ``get_async_session`` commits on the way out of every request, so without
    ``join_transaction_mode="create_savepoint"`` each API call would durably
    persist its writes.
    """
    await factories.create_account(db_session, email=COMMIT_PROBE_EMAIL)
    await db_session.commit()

    still_there = await db_session.scalar(
        select(User).where(User.email == COMMIT_PROBE_EMAIL)
    )
    assert still_there is not None, "commit() discarded the row instead of keeping it."


async def test_commit_inside_the_transaction__part2_verifies_gone(
    db_session: AsyncSession,
) -> None:
    """Paired with part1 above; it must run after it."""
    leaked = await db_session.scalar(
        select(User).where(User.email == COMMIT_PROBE_EMAIL)
    )
    assert leaked is None, (
        "A committed row escaped the test transaction. join_transaction_mode is "
        "not taking effect, and the suite is writing durable data."
    )


async def test_api_and_test_share_one_transaction(
    authed_client, account: factories.Account
) -> None:
    """Rows created by the test must be visible to the request handler.

    ``account`` exists only inside the test's uncommitted transaction. The
    endpoint reading it back proves the ``get_async_session`` override hands the
    route that same session — the half of the arrangement that a rollback test
    cannot demonstrate on its own.
    """
    response = await authed_client.get(PROTECTED_ROUTE)

    assert response.status_code == 200, response.text
    assert response.json()["email"] == account.email


# ─────────────────────────────────────────────────────────────────────────────
# 4. No LLM call and no model load can escape
# ─────────────────────────────────────────────────────────────────────────────


def test_llm_dependency_resolves_to_the_stub(
    app: FastAPI, stub_llm: StubLLMProvider
) -> None:
    override = app.dependency_overrides[get_llm_provider]
    assert override() is stub_llm, (
        "get_llm_provider is not overridden with the per-test stub, so services "
        "would construct a real MistralProvider and call the Mistral API."
    )


def test_embedding_dependency_resolves_to_the_stub(
    app: FastAPI, stub_embedding
) -> None:
    assert app.dependency_overrides[get_embedding_service]() is stub_embedding


async def test_direct_mistral_construction_is_neutralised(
    stub_llm: StubLLMProvider,
) -> None:
    """Covers the DI bypass at app/api/v1/enhancement.py:172.

    The background task constructs ``MistralProvider()`` itself, so
    ``dependency_overrides`` cannot reach it. The class-level patch must route it
    to the same stub instead of opening an HTTP connection.
    """
    provider = MistralProvider()

    result = await provider.generate("an instruction the routing table won't match")

    assert UNROUTED_MARKER in result.text
    assert [call.method for call in stub_llm.calls] == ["generate"]


async def test_direct_embedding_construction_is_neutralised() -> None:
    """Covers the module-level singletons and the ``or EmbeddingService()`` defaults."""
    service = EmbeddingService()

    vector = await service.generate_for_prompt_async("harness probe")

    assert len(vector) == EMBEDDING_DIM


def test_loading_the_real_model_is_blocked() -> None:
    """The 90 MB weight load has to fail loudly rather than just be slow."""
    with pytest.raises(AssertionError, match="real_embedding_service"):
        _ = EmbeddingService().model


# ─────────────────────────────────────────────────────────────────────────────
# 5. Authentication fixtures
# ─────────────────────────────────────────────────────────────────────────────


async def test_unauthenticated_request_is_rejected(client) -> None:
    """Guards the guard: with enable_dev_auth_bypass on, this would return 200
    and every authorization assertion in the suite would be vacuous."""
    response = await client.get(PROTECTED_ROUTE)

    assert response.status_code == 401, response.text


async def test_cookie_auth_reaches_a_protected_route(
    authed_client, account: factories.Account
) -> None:
    """The browser path: httpOnly cookie, as the frontend sends it."""
    response = await authed_client.get(PROTECTED_ROUTE)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(account.id)


async def test_bearer_auth_reaches_a_protected_route(
    client, auth_headers: dict[str, str], account: factories.Account
) -> None:
    """The API-client path. Both are supported, so both are covered."""
    response = await client.get(PROTECTED_ROUTE, headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(account.id)


async def test_account_fixture_creates_all_three_rows(
    db_session: AsyncSession, account: factories.Account
) -> None:
    """A login needs users + profiles + user_settings sharing one id.

    ``prompts.user_id`` points at ``profiles.id`` while the JWT ``sub`` is
    ``users.id``; they are the same UUID by design, and a factory that broke that
    would produce confusing 404s in ownership tests rather than an obvious error.
    """
    profile = await db_session.scalar(
        select(Profile).where(Profile.id == account.user.id)
    )
    assert profile is not None
    assert profile.email == account.user.email
    assert account.settings.user_id == profile.id


# ─────────────────────────────────────────────────────────────────────────────
# 6. Environment the suite assumes
# ─────────────────────────────────────────────────────────────────────────────


def test_global_rate_limit_middleware_is_not_registered(app: FastAPI) -> None:
    """It is added inside ``create_app()`` and cannot be removed afterwards, so
    the flag must already have been false when the app was built."""
    registered = {middleware.cls for middleware in app.user_middleware}
    assert RateLimitMiddleware not in registered, (
        "The 300/60s global limiter is active. Every request in the suite shares "
        "one client IP, so it will start returning 429 partway through a run."
    )


def test_route_level_limiters_are_overridden(app: FastAPI) -> None:
    from app.middleware.rate_limit import llm_rate_limiter, sensitive_rate_limiter

    assert sensitive_rate_limiter in app.dependency_overrides
    assert llm_rate_limiter in app.dependency_overrides


def test_redis_is_disabled() -> None:
    """Its classification and embedding caches are keyed on prompt text and
    shared with dev, so a warm entry there could answer a test's question."""
    assert settings.redis_enabled is False
    assert redis_client.is_configured() is False


def test_dev_auth_bypass_is_off() -> None:
    assert settings.enable_dev_auth_bypass is False


# ─────────────────────────────────────────────────────────────────────────────
# 7. The stubs behave as the tests built on them will assume
# ─────────────────────────────────────────────────────────────────────────────


def test_stub_embeddings_are_deterministic_unit_vectors() -> None:
    first = hashed_embedding("a reproducible sentence")
    second = hashed_embedding("a reproducible sentence")

    assert first == second
    assert len(first) == EMBEDDING_DIM
    assert abs(sum(value * value for value in first) - 1.0) < 1e-9


def test_stub_embeddings_encode_lexical_overlap() -> None:
    """Similarity has to carry *some* signal, or threshold logic is untestable.

    Only lexical signal — see the module docstring in tests/stubs/embedding.py for
    why that rules out semantic assertions against the cloned vectors.
    """
    base = hashed_embedding("prompt engineering for marketing copy")
    overlapping = hashed_embedding("prompt engineering for marketing emails")
    unrelated = hashed_embedding("quantum chromodynamics lattice simulation")

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    assert cosine(base, overlapping) > cosine(base, unrelated)


def test_stub_stream_chunks_reassemble_into_the_optimized_prompt(
    stub_llm: StubLLMProvider,
) -> None:
    """SSE tests compare the joined deltas against the blocking response, so the
    two have to be byte-identical."""
    assert "".join(stub_llm.stream_chunks) == stub_llm.optimized_prompt


def test_no_unrouted_generate_calls_leak_silently(
    stub_llm: StubLLMProvider,
) -> None:
    """Documents the drift alarm the rest of the suite relies on.

    ``generate()`` serves five callers with incompatible JSON contracts and is
    routed by matching each caller's declared response shape. When a caller's
    prompt changes, the match is lost — and this list is how that surfaces as a
    clear failure rather than a JSON parse error deep inside a service.
    """
    assert stub_llm.unrouted_prompts == []

"""Schemathesis contract tests against the app's OpenAPI document.

WHY THIS TIER IS DELIBERATELY SELF-CONTAINED
--------------------------------------------
Schemathesis drives the application from a **synchronous** Hypothesis test
function, and it manages its own event loop to do so. Every other tier in this
suite is the opposite: ``pytest.ini`` pins ``asyncio_default_fixture_loop_scope``
and ``asyncio_default_test_loop_scope`` to ``session`` because asyncpg
connections are bound to the loop that created them.

Mixing the two is what makes a fuzz tier quietly poison a whole run. If the
schema fixture requests the ordinary ``app`` fixture, it drags in ``db_session``
— a connection opened on the pytest-asyncio *session* loop — and then
Schemathesis awaits it from *its* loop. asyncpg answers that with
``InterfaceError: cannot perform operation: another operation is in progress``,
and the failure surfaces in whichever unrelated test happens to run next, not
here. The same applies to the application's own module-level engine pool, which
answers cross-loop reuse with ``RuntimeError: Event loop is closed``.

So this module never touches a database. It builds its own app, stubs the LLM and
embedding providers, and replaces the health module's ``verify_database_startup``
with a no-op. What remains under test is exactly what a contract tier is for:
that Schemathesis can read ``/openapi.json``, generate cases from it, call the
ASGI application, and find the responses conformant in status, content type and
schema.
"""

from __future__ import annotations

from typing import Iterator

import pytest
import schemathesis
from fastapi import FastAPI
from hypothesis import HealthCheck, settings
from httpx import AsyncClient

from app.api.v1.deps import get_embedding_service, get_llm_provider
from app.main import create_app
from tests.stubs.embedding import StubEmbeddingService
from tests.stubs.llm import StubLLMProvider

pytestmark = [pytest.mark.contract, pytest.mark.integration]

# The two operations that need neither authentication nor a seeded resource id.
FUZZED_PATHS = [
    "/api/v1/health",
    "/api/v1/health/liveness",
]


@pytest.fixture(scope="module")
def contract_app() -> Iterator[FastAPI]:
    """An app of this module's own, with every I/O dependency stubbed out.

    Module-scoped and built by hand rather than reusing the session-scoped
    ``app_instance``: sharing that instance would mean mutating the same
    ``dependency_overrides`` dict the async tiers rely on, and this fixture has to
    outlive individual Hypothesis examples.
    """
    import app.api.v1.health as health_module

    async def _no_database() -> None:
        return None

    original = health_module.verify_database_startup
    health_module.verify_database_startup = _no_database

    instance = create_app()
    instance.dependency_overrides[get_llm_provider] = lambda: StubLLMProvider()
    instance.dependency_overrides[get_embedding_service] = lambda: StubEmbeddingService()
    try:
        yield instance
    finally:
        health_module.verify_database_startup = original
        instance.dependency_overrides.clear()


@pytest.fixture(scope="module")
def api_schema(contract_app: FastAPI):
    return schemathesis.openapi.from_asgi("/openapi.json", contract_app)


# The filter goes on the *lazy* schema, not on the schema the fixture returns.
# ``schemathesis.pytest.from_fixture`` keeps its own ``filter_set``, and
# ``parametrize()`` expands operations against that one — a filter applied only to
# the fixture's schema object is silently ignored, and every operation gets
# generated instead of these two (most of them needing authentication and
# seeded ids, so they fail as "server error" and drown the real signal).
schema = schemathesis.pytest.from_fixture("api_schema").include(path=FUZZED_PATHS)


async def test_openapi_schema_is_served_and_contains_the_expected_surfaces(
    client: AsyncClient,
) -> None:
    """The document is reachable and describes the surfaces the tiers assert on.

    ``openapi_url`` is only disabled when ``environment == "production"``, so the
    document being served at all is part of the contract under test.
    """
    response = await client.get("/openapi.json")

    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    for path in (
        "/api/v1/health",
        "/api/v1/prompts/",
        "/api/v1/prompts/search",
        "/api/v1/templates/",
        "/api/v1/auth/login",
        "/api/v1/settings",
    ):
        assert path in paths, f"{path} missing from the OpenAPI document"


async def test_every_fuzzed_path_exists_in_the_document(client: AsyncClient) -> None:
    """Guards the filter list above against silent drift.

    ``include(path=...)`` matching nothing is not an error in Schemathesis — it
    simply generates no cases, and the fuzz test below would pass while testing
    nothing at all. This is the assertion that makes that impossible.
    """
    paths = (await client.get("/openapi.json")).json()["paths"]

    assert set(FUZZED_PATHS) <= set(paths)


@schema.parametrize()
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_health_endpoints_match_the_openapi_contract(case) -> None:
    case.call_and_validate()

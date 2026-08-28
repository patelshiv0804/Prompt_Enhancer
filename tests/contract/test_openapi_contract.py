"""Schemathesis contract tests against the app's OpenAPI document."""

from __future__ import annotations

import pytest
import schemathesis
from fastapi import FastAPI
from hypothesis import HealthCheck, settings
from httpx import AsyncClient

pytestmark = [pytest.mark.contract, pytest.mark.integration]


@pytest.fixture
def api_schema(app: FastAPI):
    """Load the schema through the ASGI app, then narrow the first fuzz slice.

    The health/readiness endpoints are intentionally the first contract surface:
    they need no generated authentication or seeded resource ids, and they still
    validate that Schemathesis can read ``/openapi.json``, generate cases, call
    the ASGI application, and check status/content/schema conformance.
    """
    return schemathesis.openapi.from_asgi("/openapi.json", app).include(
        path_regex=r"^/api/health(?:/liveness|/readiness)?$"
    )


schema = schemathesis.pytest.from_fixture("api_schema")


async def test_openapi_schema_is_served_and_contains_the_expected_surfaces(
    client: AsyncClient,
) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    assert "/api/health" in paths
    assert "/api/prompts/search" in paths
    assert "/api/prompt-versions/" in paths
    assert "/api/settings" in paths


@schema.parametrize()
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_health_endpoints_match_the_openapi_contract(case) -> None:
    case.call_and_validate()

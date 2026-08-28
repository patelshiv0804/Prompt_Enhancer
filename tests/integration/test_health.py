"""Integration tests for the health endpoints.

The harness makes these routes especially worth pinning because the embedding
service is stubbed. ``/api/v1/health`` and ``/api/v1/health/readiness`` call
``generate_for_prompt_async`` and therefore see the stub as healthy, while
``/api/v1/health/startup`` touches ``emb.model`` and the stub deliberately
raises there to prevent accidental model loads. So startup is degraded by
default under test even when the app is otherwise fine.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.llm.schemas import HealthCheckResult
from tests.stubs.llm import StubLLMProvider

pytestmark = pytest.mark.integration


async def test_health_reports_all_subsystems_healthy_by_default(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "embedding_model": "active",
        "llm_provider": "healthy",
    }


async def test_liveness_is_a_plain_200_probe(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/health/liveness")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_readiness_is_healthy_when_every_dependency_check_passes(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/health/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
        "embedding_model": "active",
        "llm_provider": "healthy",
    }


async def test_startup_is_not_ready_under_the_stubbed_embedding_model(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/health/startup")

    assert response.status_code == 503
    assert response.json() == {
        "status": "starting",
        "database": "connected",
        "embedding_model": "loading",
    }


async def test_health_degrades_when_the_database_check_fails(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("app.api.v1.health.verify_database_startup", boom)

    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "failed"


async def test_readiness_returns_503_when_the_llm_health_check_is_unhealthy(
    client: AsyncClient,
    stub_llm: StubLLMProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unhealthy() -> HealthCheckResult:
        return HealthCheckResult(healthy=False, details="stubbed failure")

    monkeypatch.setattr(stub_llm, "health_check", unhealthy)

    response = await client.get("/api/health/readiness")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "database": "connected",
        "embedding_model": "active",
        "llm_provider": "unhealthy",
    }


async def test_health_marks_the_embedding_layer_failed_when_generation_raises(
    client: AsyncClient,
    stub_embedding,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(_prompt: str) -> list[float]:
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(stub_embedding, "generate_for_prompt_async", fail)

    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["embedding_model"] == "failed"


async def test_health_root_endpoint_reports_environment_and_redis_visibility(
    client: AsyncClient,
) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "connected"
    assert body["status"] == "healthy"
    assert "environment" in body
    assert "redis" in body

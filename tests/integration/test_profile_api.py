"""
Integration tests — Profile Management API (Module A, P01–P08).
"""

import pytest
from httpx import AsyncClient


class TestGetProfile:
    """P01 — GET /api/v1/profile/me"""

    async def test_get_profile_success(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/profile/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "testuser@example.com"
        assert data["display_name"] == "Test User"
        assert data["plan"] == "free"
        assert data["onboarding_completed"] is False

    async def test_get_profile_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/profile/me")
        assert resp.status_code == 401

    async def test_get_profile_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401


class TestUpdateProfile:
    """P02 — PATCH /api/v1/profile/me"""

    async def test_update_display_name(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/profile/me", data={"display_name": "Shiv Patel"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Shiv Patel"

    async def test_update_profile_unauthenticated(self, client: AsyncClient):
        resp = await client.patch("/api/v1/profile/me", data={"display_name": "X"})
        assert resp.status_code == 401


class TestSoftDeleteProfile:
    """P03 — DELETE /api/v1/profile/me"""

    async def test_soft_delete_success(self, auth_client: AsyncClient):
        resp = await auth_client.delete("/api/v1/profile/me")
        assert resp.status_code == 200
        assert resp.json()["deleted_at"] is not None

    async def test_access_after_soft_delete(self, auth_client: AsyncClient):
        await auth_client.delete("/api/v1/profile/me")
        resp = await auth_client.get("/api/v1/profile/me")
        assert resp.status_code == 403


class TestRestoreProfile:
    """P04 — POST /api/v1/profile/restore"""

    async def test_request_restore_otp(self, auth_client: AsyncClient):
        await auth_client.delete("/api/v1/profile/me")
        resp = await auth_client.post(
            "/api/v1/profile/restore", json={"email": "testuser@example.com"},
        )
        assert resp.status_code == 200

    async def test_restore_with_valid_otp(self, auth_client: AsyncClient):
        await auth_client.delete("/api/v1/profile/me")
        await auth_client.post(
            "/api/v1/profile/restore", json={"email": "testuser@example.com"},
        )
        from app.modules.auth.service import _otp_store
        otp = _otp_store.get("testuser@example.com", (None,))[0]
        resp = await auth_client.post(
            "/api/v1/profile/restore/verify",
            json={"email": "testuser@example.com", "otp": otp},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted_at"] is None

    async def test_restore_with_invalid_otp(self, auth_client: AsyncClient):
        await auth_client.delete("/api/v1/profile/me")
        await auth_client.post(
            "/api/v1/profile/restore", json={"email": "testuser@example.com"},
        )
        resp = await auth_client.post(
            "/api/v1/profile/restore/verify",
            json={"email": "testuser@example.com", "otp": "000000"},
        )
        assert resp.status_code == 400


class TestGetPlan:
    """P05 — GET /api/v1/profile/plan"""

    async def test_get_plan_free(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/profile/plan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert data["limits"]["prompts_per_day"] == 10


class TestOnboarding:
    """P06 — PATCH /api/v1/profile/onboarding"""

    async def test_complete_onboarding(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/profile/onboarding", json={"onboarding_completed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["onboarding_completed"] is True


class TestGetStats:
    """P07 — GET /api/v1/profile/stats"""

    async def test_get_stats(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/profile/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_prompts"] == 0
        assert data["plan"] == "free"


class TestGetActivity:
    """P08 — GET /api/v1/profile/activity"""

    async def test_get_activity(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/profile/activity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] >= 1
        assert data["activities"][0]["action"] == "account_created"

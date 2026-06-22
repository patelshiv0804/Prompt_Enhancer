"""
Integration tests — User Settings API (Module B, S01–S08).
"""

import pytest
from httpx import AsyncClient


class TestGetSettings:
    """S01 — GET /api/v1/settings"""

    async def test_get_settings_defaults(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/v1/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "system"
        assert data["default_mode"] == "general"
        assert data["default_model"] == "chatgpt"
        assert data["show_diff_by_default"] is True
        assert data["auto_detect_intent"] is True

    async def test_get_settings_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/settings")
        assert resp.status_code == 401


class TestUpdateSettings:
    """S02 — PATCH /api/v1/settings"""

    async def test_bulk_update(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/settings",
            json={"theme": "dark", "default_model": "gpt-4", "default_mode": "research"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "dark"
        assert data["default_model"] == "gpt-4"
        assert data["default_mode"] == "research"

    async def test_partial_update(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/settings", json={"theme": "light"})
        assert resp.status_code == 200
        assert resp.json()["theme"] == "light"
        assert resp.json()["default_model"] == "chatgpt"  # unchanged


class TestResetSettings:
    """S03 — POST /api/v1/settings/reset"""

    async def test_reset_to_defaults(self, auth_client: AsyncClient):
        # Change settings first
        await auth_client.patch("/api/v1/settings", json={"theme": "dark"})
        # Reset
        resp = await auth_client.post("/api/v1/settings/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "system"
        assert data["default_model"] == "chatgpt"
        assert data["default_mode"] == "general"


class TestUpdateTheme:
    """S04 — PATCH /api/v1/settings/theme"""

    async def test_set_dark(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/settings/theme", json={"theme": "dark"})
        assert resp.status_code == 200
        assert resp.json()["theme"] == "dark"

    async def test_set_light(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/settings/theme", json={"theme": "light"})
        assert resp.status_code == 200
        assert resp.json()["theme"] == "light"

    async def test_invalid_theme(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/settings/theme", json={"theme": "neon"})
        assert resp.status_code == 422


class TestDefaultModel:
    """S05 — PATCH /api/v1/settings/default-model"""

    async def test_set_claude(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/settings/default-model", json={"default_model": "claude-sonnet-4.5"},
        )
        assert resp.status_code == 200
        assert resp.json()["default_model"] == "claude-sonnet-4.5"

    async def test_invalid_model(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/settings/default-model", json={"default_model": "fake-model"},
        )
        assert resp.status_code == 422


class TestDefaultMode:
    """S06 — PATCH /api/v1/settings/default-mode"""

    async def test_set_youtube_shorts(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/settings/default-mode", json={"default_mode": "youtube-shorts"},
        )
        assert resp.status_code == 200
        assert resp.json()["default_mode"] == "youtube-shorts"

    async def test_invalid_mode(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/settings/default-mode", json={"default_mode": "invalid"},
        )
        assert resp.status_code == 422


class TestIntentDetection:
    """S07 — PATCH /api/v1/settings/intent-detection"""

    async def test_disable(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/v1/settings/intent-detection", json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["auto_detect_intent"] is False

    async def test_enable(self, auth_client: AsyncClient):
        await auth_client.patch("/api/v1/settings/intent-detection", json={"enabled": False})
        resp = await auth_client.patch(
            "/api/v1/settings/intent-detection", json={"enabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["auto_detect_intent"] is True


class TestDiffView:
    """S08 — PATCH /api/v1/settings/diff-view"""

    async def test_disable(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/v1/settings/diff-view", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["show_diff_by_default"] is False

    async def test_enable(self, auth_client: AsyncClient):
        await auth_client.patch("/api/v1/settings/diff-view", json={"enabled": False})
        resp = await auth_client.patch("/api/v1/settings/diff-view", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["show_diff_by_default"] is True

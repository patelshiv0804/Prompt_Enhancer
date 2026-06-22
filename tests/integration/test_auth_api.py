"""
Integration tests — Auth API endpoints.
"""

import pytest
from httpx import AsyncClient


class TestAuthRegister:
    """Tests for POST /api/v1/auth/register"""

    async def test_register_success(self, client: AsyncClient):
        """Should register a new user and return profile."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "display_name": "New User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert data["display_name"] == "New User"
        assert data["plan"] == "free"
        assert data["onboarding_completed"] is False

    async def test_register_duplicate_email(self, client: AsyncClient):
        """Should reject duplicate email registration."""
        payload = {
            "email": "dup@example.com",
            "password": "SecurePass123!",
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409

    async def test_register_short_password(self, client: AsyncClient):
        """Should reject passwords shorter than 8 characters."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "short@example.com", "password": "123"},
        )
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        """Should reject invalid email format."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "SecurePass123!"},
        )
        assert resp.status_code == 422

    async def test_register_without_display_name(self, client: AsyncClient):
        """Should allow registration without display_name."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "noname@example.com", "password": "SecurePass123!"},
        )
        assert resp.status_code == 201
        assert resp.json()["display_name"] is None


class TestAuthLogin:
    """Tests for POST /api/v1/auth/login"""

    async def test_login_success(self, client: AsyncClient):
        """Should return JWT token on valid credentials."""
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "password": "SecurePass123!"},
        )

        # Login
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "login@example.com", "password": "SecurePass123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user_id" in data

    async def test_login_wrong_password(self, client: AsyncClient):
        """Should reject wrong password."""
        await client.post(
            "/api/v1/auth/register",
            json={"email": "wrong@example.com", "password": "SecurePass123!"},
        )

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "wrong@example.com", "password": "WrongPass!"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Should reject login for non-existent user."""
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "ghost@example.com", "password": "SecurePass123!"},
        )
        assert resp.status_code == 401

    async def test_login_returns_valid_token(self, client: AsyncClient):
        """Token from login should work for authenticated endpoints."""
        await client.post(
            "/api/v1/auth/register",
            json={"email": "valid@example.com", "password": "SecurePass123!"},
        )

        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "valid@example.com", "password": "SecurePass123!"},
        )
        token = login_resp.json()["access_token"]

        # Use token to access profile
        profile_resp = await client.get(
            "/api/v1/profile/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile_resp.status_code == 200
        assert profile_resp.json()["email"] == "valid@example.com"

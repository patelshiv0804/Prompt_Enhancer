"""
Integration test fixtures — auth helpers.
"""

import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """
    Client with a pre-registered and logged-in user.
    Sets the Authorization header automatically.
    """
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "testuser@example.com",
            "password": "Test1234!",
            "display_name": "Test User",
        },
    )
    assert register_resp.status_code == 201

    login_resp = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser@example.com",
            "password": "Test1234!",
        },
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    return client

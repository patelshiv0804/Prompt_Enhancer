"""Unit tests for refresh tokens and auth cookie fallback on invalid bearer tokens.

Covers:
- Commit 80545d7: implemented the refresh token feature (create_refresh_token, decode_refresh_token)
- Commit b2140e3: fallback to auth cookies on invalid bearer token
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_current_user_id,
)
from tests.unit.asgi_helpers import make_request

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# Refresh token creation and decoding (commit 80545d7)
# ─────────────────────────────────────────────────────────────────────────────


def test_create_refresh_token_has_refresh_type() -> None:
    """Ensure created refresh token contains type='refresh' and valid expiration."""
    user_id = str(uuid4())
    token = create_refresh_token({"sub": user_id})

    payload = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert payload.get("sub") == user_id
    assert payload.get("type") == "refresh"
    assert "exp" in payload


def test_decode_refresh_token_valid() -> None:
    """Ensure decode_refresh_token accepts a valid refresh token and returns payload."""
    user_id = str(uuid4())
    token = create_refresh_token({"sub": user_id})

    payload = decode_refresh_token(token)
    assert payload.get("sub") == user_id
    assert payload.get("type") == "refresh"


def test_decode_refresh_token_rejects_access_token() -> None:
    """Ensure decode_refresh_token rejects an access token (type='access')."""
    access_token = create_access_token({"sub": str(uuid4())})

    with pytest.raises(HTTPException) as exc_info:
        decode_refresh_token(access_token)

    assert exc_info.value.status_code == 401
    assert "Invalid token type" in exc_info.value.detail


def test_decode_refresh_token_rejects_expired() -> None:
    """Ensure decode_refresh_token rejects an expired refresh token."""
    expired_token = create_refresh_token(
        {"sub": str(uuid4())}, expires_delta=timedelta(seconds=-10)
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_refresh_token(expired_token)

    assert exc_info.value.status_code == 401
    assert "Invalid or expired" in exc_info.value.detail


def test_decode_access_token_rejects_refresh_token() -> None:
    """Ensure decode_access_token rejects a refresh token."""
    refresh_token = create_refresh_token({"sub": str(uuid4())})

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(refresh_token)

    assert exc_info.value.status_code == 401
    assert "Invalid token type" in exc_info.value.detail


# ─────────────────────────────────────────────────────────────────────────────
# Cookie fallback on invalid or absent bearer token (commit b2140e3)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_to_cookie_when_bearer_is_invalid() -> None:
    """When an invalid or expired bearer token is provided, fall back to valid cookie."""
    cookie_user_id = uuid4()
    valid_cookie_token = create_access_token({"sub": str(cookie_user_id)})
    invalid_bearer = "invalid.bearer.jwt_token"

    request = make_request(
        cookies={settings.access_cookie_name: valid_cookie_token}
    )

    resolved_user_id = await get_current_user_id(request, token=invalid_bearer)
    assert resolved_user_id == cookie_user_id


@pytest.mark.asyncio
async def test_fallback_to_cookie_when_bearer_is_expired() -> None:
    """When an expired bearer token is provided, fall back to valid cookie."""
    cookie_user_id = uuid4()
    valid_cookie_token = create_access_token({"sub": str(cookie_user_id)})
    expired_bearer = create_access_token(
        {"sub": str(uuid4())}, expires_delta=timedelta(seconds=-10)
    )

    request = make_request(
        cookies={settings.access_cookie_name: valid_cookie_token}
    )

    resolved_user_id = await get_current_user_id(request, token=expired_bearer)
    assert resolved_user_id == cookie_user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("junk_token", ["null", "undefined", "  ", ""])
async def test_fallback_to_cookie_when_bearer_is_stringified_null(junk_token: str) -> None:
    """Frontend bug defense: 'null' or 'undefined' bearer token string falls back to cookie."""
    cookie_user_id = uuid4()
    valid_cookie_token = create_access_token({"sub": str(cookie_user_id)})

    request = make_request(
        cookies={settings.access_cookie_name: valid_cookie_token}
    )

    resolved_user_id = await get_current_user_id(request, token=junk_token)
    assert resolved_user_id == cookie_user_id


@pytest.mark.asyncio
async def test_invalid_bearer_and_invalid_cookie_raises_401() -> None:
    """When both bearer token and cookie are invalid, raises 401 Unauthorized."""
    request = make_request(
        cookies={settings.access_cookie_name: "invalid_cookie_jwt"}
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(request, token="invalid_bearer_token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"

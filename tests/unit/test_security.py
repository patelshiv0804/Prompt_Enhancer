"""Unit tests for app/core/security.py — password hashing and JWT handling.

Everything here is derived from reading the module, not from any previous test
suite. Where the observed behaviour looks wrong, the test pins what the code
*currently does* and says so in its docstring: a test that asserted the desired
behaviour would fail on an application defect and stall the whole tier, which
hides the finding instead of recording it.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_current_user_id,
    hash_password,
    hash_password_async,
    verify_password,
    verify_password_async,
)
from tests.constants import ACCESS_COOKIE_NAME
from tests.unit.asgi_helpers import make_request

pytestmark = pytest.mark.unit

DEV_BYPASS_USER_ID = UUID("899fd613-4e56-4921-b8f6-7fc1bf85fead")

# bcrypt's hard input limit. bcrypt 5.x raises instead of silently truncating.
BCRYPT_MAX_BYTES = 72


def _unsigned_token(claims: dict) -> str:
    """Forge an ``alg: none`` JWT — the classic algorithm-confusion attack."""

    def segment(payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return f"{segment({'alg': 'none', 'typ': 'JWT'})}.{segment(claims)}."


# ─────────────────────────────────────────────────────────────────────────────
# Password hashing
# ─────────────────────────────────────────────────────────────────────────────


def test_hash_verify_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)


def test_hash_is_salted() -> None:
    """Two hashes of one password must differ, or the hashes are precomputable."""
    first = hash_password("same-password")
    second = hash_password("same-password")

    assert first != second
    assert verify_password("same-password", first)
    assert verify_password("same-password", second)


@pytest.mark.parametrize(
    "candidate",
    [
        "wrong-password",
        "correct horse battery stapl",  # one char short
        "Correct Horse Battery Staple",  # case matters
        "",
    ],
)
def test_verify_rejects_wrong_password(candidate: str) -> None:
    hashed = hash_password("correct horse battery staple")

    assert verify_password(candidate, hashed) is False


def test_hash_produces_a_bcrypt_2b_digest() -> None:
    """The prefix pins the algorithm and cost the cloned rows were hashed with.

    ``scripts/ensure_test_user.py`` and the factories rely on the application's
    own ``hash_password``, so a change of algorithm here would silently
    invalidate every stored credential rather than fail loudly.
    """
    hashed = hash_password("prefix-probe")

    assert hashed.startswith("$2b$")


async def test_async_wrappers_match_the_sync_ones() -> None:
    hashed = await hash_password_async("threaded")

    assert await verify_password_async("threaded", hashed) is True
    assert await verify_password_async("not-it", hashed) is False


def test_password_at_the_bcrypt_limit_is_accepted() -> None:
    at_limit = "a" * BCRYPT_MAX_BYTES

    assert verify_password(at_limit, hash_password(at_limit))


def test_password_over_72_bytes_raises_instead_of_hashing() -> None:
    """KNOWN DEFECT — pinning current behaviour, not endorsing it.

    ``RegisterRequest.password`` allows ``max_length=128``
    (app/schemas/auth.py:17) but bcrypt 5.x refuses anything over 72 bytes, so
    a 73–128 character password passes request validation and then raises
    ``ValueError`` out of ``hash_password``. Nothing in the auth service catches
    it, which surfaces to the client as HTTP 500.

    If the schema is capped at 72 (or the password is pre-hashed/truncated),
    invert this test.
    """
    with pytest.raises(ValueError, match="72 bytes"):
        hash_password("a" * (BCRYPT_MAX_BYTES + 1))


def test_verifying_an_over_long_password_raises_instead_of_returning_false() -> None:
    """KNOWN DEFECT — the login-side half of the defect above.

    ``verify_password`` is reached with attacker-controlled input on every login
    attempt, so an unauthenticated caller can turn a 401 into a 500 just by
    submitting a 73-character password.
    """
    hashed = hash_password("a-normal-password")

    with pytest.raises(ValueError, match="72 bytes"):
        verify_password("a" * (BCRYPT_MAX_BYTES + 1), hashed)


def test_verify_rejects_a_malformed_hash() -> None:
    """A corrupted or non-bcrypt stored hash must not be treated as a match."""
    with pytest.raises(ValueError):
        verify_password("anything", "not-a-bcrypt-hash")


# ─────────────────────────────────────────────────────────────────────────────
# Token creation and decoding
# ─────────────────────────────────────────────────────────────────────────────


def test_access_token_round_trip_preserves_claims() -> None:
    user_id = uuid4()

    payload = decode_access_token(create_access_token({"sub": str(user_id)}))

    assert payload["sub"] == str(user_id)
    assert "exp" in payload


def test_default_expiry_comes_from_settings() -> None:
    payload = decode_access_token(create_access_token({"sub": str(uuid4())}))

    expected = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    actual = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    assert abs((actual - expected).total_seconds()) < 5


def test_explicit_expires_delta_overrides_the_default() -> None:
    payload = decode_access_token(
        create_access_token({"sub": str(uuid4())}, expires_delta=timedelta(minutes=5))
    )

    expected = datetime.now(timezone.utc) + timedelta(minutes=5)
    actual = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    assert abs((actual - expected).total_seconds()) < 5


def test_create_access_token_does_not_mutate_its_input() -> None:
    """It copies before adding ``exp``; callers reuse these dicts."""
    claims = {"sub": str(uuid4())}

    create_access_token(claims)

    assert claims == {"sub": claims["sub"]}


def test_extra_claims_survive_the_round_trip() -> None:
    payload = decode_access_token(create_access_token({"sub": "abc", "scope": "reset"}))

    assert payload["scope"] == "reset"


def test_expired_token_is_rejected() -> None:
    expired = create_access_token(
        {"sub": str(uuid4())}, expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(expired)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_tampered_payload_is_rejected() -> None:
    """Flipping a payload byte invalidates the HMAC — the whole point of signing."""
    header, payload, signature = create_access_token({"sub": str(uuid4())}).split(".")
    swapped = "B" if payload[0] != "B" else "C"

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(f"{header}.{swapped}{payload[1:]}.{signature}")

    assert exc_info.value.status_code == 401


def test_token_signed_with_another_key_is_rejected() -> None:
    foreign = jwt.encode(
        {"sub": str(uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "a-completely-different-secret-key-value",
        algorithm=settings.algorithm,
    )

    with pytest.raises(HTTPException):
        decode_access_token(foreign)


def test_unsigned_alg_none_token_is_rejected() -> None:
    """``decode`` pins ``algorithms=[settings.ALGORITHM]``; this proves it holds."""
    with pytest.raises(HTTPException):
        decode_access_token(_unsigned_token({"sub": str(uuid4())}))


@pytest.mark.parametrize(
    "token",
    ["", "not-a-jwt", "a.b.c", "eyJhbGciOiJIUzI1NiJ9", "..."],
    ids=["empty", "garbage", "three-junk-segments", "header-only", "empty-segments"],
)
def test_structurally_invalid_tokens_are_rejected(token: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)

    assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# get_current_user_id — the dependency every protected route uses
# ─────────────────────────────────────────────────────────────────────────────


def test_cookie_name_constant_matches_settings() -> None:
    """Drift guard: the auth fixtures set the cookie by name, not via settings."""
    assert ACCESS_COOKIE_NAME == settings.access_cookie_name


async def test_bearer_token_is_accepted() -> None:
    user_id = uuid4()

    resolved = await get_current_user_id(
        make_request(), token=create_access_token({"sub": str(user_id)})
    )

    assert resolved == user_id


async def test_cookie_is_used_when_no_bearer_header_is_present() -> None:
    user_id = uuid4()
    request = make_request(
        cookies={settings.access_cookie_name: create_access_token({"sub": str(user_id)})}
    )

    assert await get_current_user_id(request, token=None) == user_id


async def test_bearer_token_takes_precedence_over_the_cookie() -> None:
    header_user, cookie_user = uuid4(), uuid4()
    request = make_request(
        cookies={
            settings.access_cookie_name: create_access_token({"sub": str(cookie_user)})
        }
    )

    resolved = await get_current_user_id(
        request, token=create_access_token({"sub": str(header_user)})
    )

    assert resolved == header_user


async def test_a_differently_named_cookie_is_ignored() -> None:
    request = make_request(
        cookies={"some_other_token": create_access_token({"sub": str(uuid4())})}
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(request, token=None)

    assert exc_info.value.status_code == 401


async def test_no_credentials_is_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(make_request(), token=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


@pytest.mark.parametrize(
    "claims",
    [{}, {"sub": None}, {"sub": ""}, {"sub": "not-a-uuid"}, {"sub": 12345}],
    ids=["no-sub", "null-sub", "empty-sub", "non-uuid-sub", "numeric-sub"],
)
async def test_a_valid_signature_with_an_unusable_sub_is_still_401(claims: dict) -> None:
    """The handler swallows ``Exception`` around the UUID parse.

    That is only safe if it then falls through to the 401 — otherwise a
    correctly-signed token with a junk ``sub`` would return None and every
    downstream ownership query would run against a null user id.
    """
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(make_request(), token=create_access_token(claims))

    assert exc_info.value.status_code == 401


async def test_expired_token_does_not_fall_through_to_a_user() -> None:
    expired = create_access_token(
        {"sub": str(uuid4())}, expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(make_request(), token=expired)

    assert exc_info.value.status_code == 401


async def test_dev_auth_bypass_returns_the_hardcoded_user(monkeypatch) -> None:
    """The bypass exists; this documents exactly what it grants.

    ``app.core.security`` holds a reference to the same ``Settings`` singleton,
    so patching the attribute is what a misconfigured deployment would do. The
    harness asserts the flag is off for every other test in the suite.
    """
    monkeypatch.setattr(settings, "enable_dev_auth_bypass", True)

    assert await get_current_user_id(make_request(), token=None) == DEV_BYPASS_USER_ID


async def test_dev_auth_bypass_also_rescues_an_invalid_token(monkeypatch) -> None:
    """Worth stating plainly: with the bypass on, a forged token authenticates."""
    monkeypatch.setattr(settings, "enable_dev_auth_bypass", True)

    resolved = await get_current_user_id(make_request(), token="garbage")

    assert resolved == DEV_BYPASS_USER_ID

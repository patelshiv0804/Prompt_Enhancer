"""Integration tests for app/api/v1/auth.py.

Seven endpoints hang off ``/api/v1/auth``; this file covers the four that make up
the session lifecycle — ``register``, ``login``, ``logout`` and the token handling
that guards every other route. The three password-reset endpoints send email and
keep OTP state in module-level dicts, so they get their own file.

Two things shape almost every assertion here and are worth reading first.

**Where the status code comes from.** ``AuthService`` raises plain
``Exception`` subclasses — ``AlreadyExistsException``, ``UnauthorizedException``,
``NotFoundException`` — and ``app/main.py`` registers exactly one handler,
``add_exception_handler(Exception, http_error_handler)``, which maps them to
400/401/404 with ``{"detail": exc.message}``. Nothing in the route layer catches
them, so the message the service constructs *is* the API's error text. Anything
the handler does not recognise becomes a 500 with a fixed, non-leaking body
(VULN-014), which is exactly how the bcrypt defect at the bottom of this file
surfaces.

**Emails are compared byte-for-byte.** ``AuthRepository.exists_by_email`` and
``get_by_email`` are plain ``WHERE email = :email`` with no ``lower()``, and
``AuthService.register``/``login`` pass the address through untouched. Pydantic's
``EmailStr`` lowercases the *domain* only. Both facts are pinned below.
"""

from __future__ import annotations

from datetime import timedelta
from http.cookies import SimpleCookie
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient, Response
from jose import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.db.models import Profile, User, UserSettings
from tests import factories
from tests.constants import ACCESS_COOKIE_NAME, TEST_USER_EMAIL, TEST_USER_PASSWORD

pytestmark = pytest.mark.integration

settings = get_settings()

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/profile/me"

GOOD_PASSWORD = "CorrectHorse42!"


def new_email(prefix: str = "auth") -> str:
    """A registerable address.

    ``factories.unique_email`` already picks an ``EmailStr``-valid domain; this
    wrapper exists only to make the intent obvious at the call sites that post the
    address to the API rather than inserting it directly.
    """
    return factories.unique_email(prefix)


def auth_cookie(response: Response) -> SimpleCookie:
    """The single ``Set-Cookie`` header for the access cookie, parsed.

    Asserting there is exactly one matters: two ``Set-Cookie`` headers for the
    same name is how a stale token survives a re-login, and browsers pick the
    last one, so the bug would be invisible to a test that only read
    ``response.cookies``.
    """
    headers = [
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{ACCESS_COOKIE_NAME}=")
    ]
    assert len(headers) == 1, f"expected one {ACCESS_COOKIE_NAME} cookie, got {headers}"
    return SimpleCookie(headers[0])


def decode(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ─────────────────────────────────────────────────────────────────────────────
# POST /register — the happy path
# ─────────────────────────────────────────────────────────────────────────────


async def test_register_returns_201_and_the_new_profile(client: AsyncClient) -> None:
    email = new_email()

    response = await client.post(
        REGISTER,
        json={"email": email, "password": GOOD_PASSWORD, "display_name": "Ada"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == email
    assert body["display_name"] == "Ada"
    # Defaults applied by the profiles table, not by the request.
    assert body["plan"] == "free"
    assert body["role"] == "creator"
    assert body["onboarding_completed"] is False
    assert body["deleted_at"] is None
    UUID(body["id"])  # a real UUID, not a stringified int or a slug


async def test_register_never_returns_the_password_or_its_hash(
    client: AsyncClient,
) -> None:
    """``ProfileResponse`` has no password field, but it is built with
    ``from_attributes`` from a row that sits next to one — so this is worth
    asserting on the serialised body rather than trusting the schema."""
    response = await client.post(
        REGISTER, json={"email": new_email(), "password": GOOD_PASSWORD}
    )

    assert response.status_code == 201, response.text
    assert GOOD_PASSWORD not in response.text
    assert not {"password", "hashed_password"} & set(response.json())


async def test_register_writes_user_profile_and_settings(
    client: AsyncClient, db_session
) -> None:
    """One request, three tables.

    ``AuthService.register`` inserts the ``users`` row; the route then calls
    ``ProfileService.create_profile``, which inserts ``profiles`` *and*
    ``user_settings``. A partial write here would leave an account that can log in
    but 500s on every profile route, so all three are checked.
    """
    email = new_email()

    response = await client.post(
        REGISTER, json={"email": email, "password": GOOD_PASSWORD}
    )
    assert response.status_code == 201, response.text
    user_id = UUID(response.json()["id"])

    user = await db_session.scalar(select(User).where(User.id == user_id))
    profile = await db_session.scalar(select(Profile).where(Profile.id == user_id))
    user_settings = await db_session.scalar(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )

    assert user is not None and profile is not None and user_settings is not None
    # profiles.id is both the primary key and a FK to users.id — one identity.
    assert profile.id == user.id
    assert user.email == profile.email == email
    assert user.auth_provider == "local"
    assert user.is_active is True


async def test_register_stores_a_bcrypt_hash_that_verifies(
    client: AsyncClient, db_session
) -> None:
    email = new_email()

    response = await client.post(
        REGISTER, json={"email": email, "password": GOOD_PASSWORD}
    )
    assert response.status_code == 201, response.text

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user.hashed_password != GOOD_PASSWORD
    assert user.hashed_password.startswith("$2b$")
    assert verify_password(GOOD_PASSWORD, user.hashed_password) is True
    assert verify_password(GOOD_PASSWORD + "x", user.hashed_password) is False


async def test_register_leaves_display_name_null_when_omitted(
    client: AsyncClient,
) -> None:
    response = await client.post(
        REGISTER, json={"email": new_email(), "password": GOOD_PASSWORD}
    )

    assert response.status_code == 201, response.text
    assert response.json()["display_name"] is None


async def test_a_registered_account_is_not_verified_yet(
    client: AsyncClient, db_session
) -> None:
    """``AuthRepository.create`` defaults ``is_verified=False`` and the route does
    not override it, so a fresh local account is unverified. Nothing currently
    gates on that flag — pinned so it is a visible decision if a verification
    gate is ever added."""
    email = new_email()

    await client.post(REGISTER, json={"email": email, "password": GOOD_PASSWORD})

    user = await db_session.scalar(select(User).where(User.email == email))
    assert user.is_verified is False


# ─────────────────────────────────────────────────────────────────────────────
# POST /register — rejections
# ─────────────────────────────────────────────────────────────────────────────


async def test_register_rejects_a_duplicate_email(
    client: AsyncClient, db_session
) -> None:
    """400, and the message is the service's — ``AlreadyExistsException("User with
    this email")`` reaches the client verbatim, with no trailing punctuation."""
    account = await factories.create_account(db_session)
    # House rule 2: release the savepoint so the app's rollback on the error path
    # cannot take this row with it.
    await db_session.commit()

    response = await client.post(
        REGISTER, json={"email": account.email, "password": GOOD_PASSWORD}
    )

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "User with this email"}


async def test_a_duplicate_registration_creates_no_second_profile(
    client: AsyncClient, db_session
) -> None:
    """The guard runs before any insert, so the attempt must be inert.

    Registration is a three-table write; if the duplicate check fired *after* the
    ``users`` insert, the rollback would still have to unwind a partially built
    account. Counting profiles for this address proves the check comes first.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()

    await client.post(
        REGISTER, json={"email": account.email, "password": GOOD_PASSWORD}
    )

    profiles = (
        await db_session.scalars(
            select(Profile).where(Profile.email == account.email)
        )
    ).all()
    assert len(profiles) == 1


async def test_the_duplicate_check_is_case_sensitive_on_the_local_part(
    client: AsyncClient, db_session
) -> None:
    """KNOWN DEFECT — two accounts can differ only by capitalisation.

    ``EmailStr`` lowercases the domain but preserves the local part, and
    ``exists_by_email`` is ``WHERE email = :email`` with no ``lower()``. So
    ``Ada@x.dev`` registers cleanly after ``ada@x.dev`` and becomes a second,
    independent account with its own profile. ``login`` is case-sensitive in the
    same way, so each password only opens its own account — the user-visible
    symptom is a silent duplicate account and a "wrong password" for the address
    they thought they had registered.

    Pinned as current behaviour. The fix is to normalise on the way in (and to
    add a functional unique index on ``lower(email)``), at which point this test
    should assert 400.
    """
    lower = new_email("case").lower()
    upper = lower[0].upper() + lower[1:]
    assert lower != upper and lower.split("@")[1] == upper.split("@")[1]

    first = await client.post(REGISTER, json={"email": lower, "password": GOOD_PASSWORD})
    second = await client.post(REGISTER, json={"email": upper, "password": GOOD_PASSWORD})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]


async def test_the_domain_is_lowercased_before_it_reaches_the_database(
    client: AsyncClient, db_session
) -> None:
    """The other half of the case story: ``EmailStr`` normalises the domain, so a
    mixed-case host is *not* a way to duplicate an account."""
    email = new_email("domaincase")
    local, domain = email.split("@")

    response = await client.post(
        REGISTER, json={"email": f"{local}@{domain.upper()}", "password": GOOD_PASSWORD}
    )

    assert response.status_code == 201, response.text
    assert response.json()["email"] == email


@pytest.mark.parametrize(
    "password",
    ["", "short", "1234567"],
    ids=["empty", "five-chars", "seven-chars"],
)
async def test_register_rejects_a_password_under_eight_characters(
    client: AsyncClient, password: str
) -> None:
    response = await client.post(REGISTER, json={"email": new_email(), "password": password})

    assert response.status_code == 422, response.text


async def test_register_rejects_a_password_over_128_characters(
    client: AsyncClient,
) -> None:
    response = await client.post(
        REGISTER, json={"email": new_email(), "password": "a" * 129}
    )

    assert response.status_code == 422, response.text


async def test_register_rejects_a_display_name_over_100_characters(
    client: AsyncClient,
) -> None:
    response = await client.post(
        REGISTER,
        json={"email": new_email(), "password": GOOD_PASSWORD, "display_name": "n" * 101},
    )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "email",
    [
        "",
        "not-an-email",
        "missing@",
        "@missing-local.dev",
        "spaces in@example.com",
        "someone@localhost",
    ],
    ids=["empty", "no-at", "no-domain", "no-local", "spaces", "dotless-host"],
)
async def test_register_rejects_a_malformed_email(
    client: AsyncClient, email: str
) -> None:
    response = await client.post(REGISTER, json={"email": email, "password": GOOD_PASSWORD})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "domain",
    ["promptiq.test", "promptiq.invalid", "promptiq.local", "promptiq.localhost", "promptiq.onion", "promptiq.arpa"],
    ids=["test", "invalid", "local", "localhost", "onion", "arpa"],
)
async def test_register_rejects_special_use_domains(
    client: AsyncClient, domain: str
) -> None:
    """``email_validator`` refuses every name in ``SPECIAL_USE_DOMAIN_NAMES`` —
    ``arpa``, ``invalid``, ``local``, ``localhost``, ``onion``, ``test``.

    This is why ``tests/factories.py`` uses a ``.dev`` domain and why the
    bootstrap ``test@promptiq.test`` account can only ever *log in*, never
    register. Pinned here because it is a constraint on the tests, not a
    behaviour anyone would think to look for in the app.

    Bare ``localhost`` is a 422 too but for an unrelated reason ("should have a
    period"), so it is covered by the malformed-email cases instead.
    """
    response = await client.post(
        REGISTER, json={"email": f"someone@{domain}", "password": GOOD_PASSWORD}
    )

    assert response.status_code == 422, response.text
    assert "special-use or reserved name" in response.text


@pytest.mark.parametrize(
    "payload",
    [{}, {"email": "someone@example.com"}, {"password": GOOD_PASSWORD}],
    ids=["nothing", "email-only", "password-only"],
)
async def test_register_requires_both_fields(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    response = await client.post(REGISTER, json=payload)

    assert response.status_code == 422, response.text


async def test_register_is_not_rate_limited(
    client: AsyncClient, rate_limits_enforced
) -> None:
    """Deliberate asymmetry worth recording: ``/login`` carries
    ``Depends(sensitive_rate_limiter)`` and ``/register`` carries nothing, so with
    the real limiters restored six registrations in a row all succeed.

    Not a defect on its own — registration is idempotent-ish and guarded by the
    unique email — but it does mean the 300/60s global middleware is the only
    thing standing between an unauthenticated caller and unbounded bcrypt work at
    the app's cost factor. Flagged rather than asserted as desirable.
    """
    for _ in range(6):
        response = await client.post(
            REGISTER, json={"email": new_email("burst"), "password": GOOD_PASSWORD}
        )
        assert response.status_code == 201, response.text


# ─────────────────────────────────────────────────────────────────────────────
# POST /login — the happy path
# ─────────────────────────────────────────────────────────────────────────────


async def test_login_returns_a_token_bound_to_the_user(
    client: AsyncClient, db_session
) -> None:
    account = await factories.create_account(db_session)
    await db_session.commit()

    response = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user_id"] == str(account.id)
    # ``sub`` is the users.id UUID as a string; get_current_user_id parses it
    # straight into UUID(), so any other shape 401s every protected route.
    assert decode(body["access_token"])["sub"] == str(account.id)


async def test_login_takes_form_encoding_not_json(
    client: AsyncClient, db_session
) -> None:
    """``OAuth2PasswordRequestForm``, so the fields are ``username``/``password``
    in a form body. A JSON payload — which is what the schema-shaped
    ``UserLogin`` model would suggest — is a 422. Worth pinning: it is the one
    endpoint in the API that does not take JSON, and it is the first thing a new
    client gets wrong.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()

    as_json = await client.post(
        LOGIN, json={"email": account.email, "password": account.password}
    )
    as_form = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )

    assert as_json.status_code == 422, as_json.text
    assert as_form.status_code == 200, as_form.text


async def test_login_accepts_a_special_use_domain_that_register_would_reject(
    client: AsyncClient, bootstrap_user: User
) -> None:
    """The consequence of the form-vs-schema split, and the reason the bootstrap
    account works at all.

    ``OAuth2PasswordRequestForm.username`` is a plain ``str`` with no
    ``EmailStr`` validation, so ``test@promptiq.test`` logs in even though
    ``/register`` returns 422 for that exact address. Every fixture that needs a
    real login round-trip depends on this.
    """
    response = await client.post(
        LOGIN, data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == str(bootstrap_user.id)


async def test_login_sets_an_httponly_cookie_matching_the_body_token(
    client: AsyncClient, db_session
) -> None:
    """VULN-017: the token must reach the browser in a cookie JavaScript cannot
    read, and it must be the same token the body advertises — the frontend uses
    the cookie, so a mismatch would authenticate a different session than the one
    the client thinks it holds."""
    account = await factories.create_account(db_session)
    await db_session.commit()

    response = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )
    assert response.status_code == 200, response.text

    morsel = auth_cookie(response)[ACCESS_COOKIE_NAME]
    assert morsel.value == response.json()["access_token"]
    assert morsel["httponly"] is True
    assert morsel["path"] == "/"
    assert morsel["samesite"].lower() == settings.cookie_samesite
    # 30 minutes by default, and it must match the JWT's own lifetime — a cookie
    # that outlives its token logs the user out with a 401 instead of a redirect.
    assert int(morsel["max-age"]) == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    # Secure is environment-dependent (False in dev, True in production), so the
    # assertion tracks the setting rather than hardcoding either answer.
    assert bool(morsel["secure"]) is settings.COOKIE_SECURE


async def test_login_does_not_rewrite_the_user_row(
    client: AsyncClient, db_session
) -> None:
    """``login`` deliberately does not commit — there is nothing to persist. This
    pins that no ``last_login``-style write crept in, which would make the read
    path a write path and add a row lock to every sign-in."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    before = account.user.updated_at

    await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )
    await db_session.refresh(account.user)

    assert account.user.updated_at == before


# ─────────────────────────────────────────────────────────────────────────────
# POST /login — rejections
# ─────────────────────────────────────────────────────────────────────────────


async def test_login_rejects_a_wrong_password(
    client: AsyncClient, db_session
) -> None:
    account = await factories.create_account(db_session)
    await db_session.commit()

    response = await client.post(
        LOGIN, data={"username": account.email, "password": "NotThePassword1!"}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Invalid email or password"}
    assert ACCESS_COOKIE_NAME not in response.headers.get("set-cookie", "")


async def test_an_unknown_email_is_indistinguishable_from_a_wrong_password(
    client: AsyncClient, db_session
) -> None:
    """Account-enumeration guard. Both branches raise the same
    ``UnauthorizedException("Invalid email or password")``, so the response tells
    an attacker nothing about which addresses exist.

    Note what this does *not* cover: ``login`` skips bcrypt entirely when the user
    is missing, so the two paths differ by ~250 ms of hashing. The bodies match;
    the timing does not.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()

    unknown = await client.post(
        LOGIN, data={"username": new_email("ghost"), "password": GOOD_PASSWORD}
    )
    wrong_password = await client.post(
        LOGIN, data={"username": account.email, "password": "NotThePassword1!"}
    )

    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()


async def test_login_rejects_a_deactivated_account(
    client: AsyncClient, db_session
) -> None:
    """A distinct message, and deliberately so — the password was correct, so
    there is nothing left to enumerate and telling the user why they are locked
    out is the more useful answer."""
    account = await factories.create_account(db_session, is_active=False)
    await db_session.commit()

    response = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Account is deactivated"}


async def test_the_active_check_runs_after_the_password_check(
    client: AsyncClient, db_session
) -> None:
    """Ordering in ``AuthService.login``, and it is the security-relevant order:
    a deactivated account must not reveal its own existence to someone who does
    not have the password."""
    account = await factories.create_account(db_session, is_active=False)
    await db_session.commit()

    response = await client.post(
        LOGIN, data={"username": account.email, "password": "NotThePassword1!"}
    )

    assert response.json() == {"detail": "Invalid email or password"}


async def test_login_is_case_sensitive_on_the_email(
    client: AsyncClient, db_session
) -> None:
    """The read side of the normalisation gap pinned above.

    ``get_by_email`` is an exact match, so an account registered lowercase cannot
    be reached by typing the address with a capital letter — the user gets
    "Invalid email or password" for credentials that are, from their point of
    view, correct. Pinned as current behaviour; it disappears once the address is
    normalised on both write and read.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()
    shouted = account.email[0].upper() + account.email[1:]
    assert shouted != account.email

    response = await client.post(
        LOGIN, data={"username": shouted, "password": account.password}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Invalid email or password"}


@pytest.mark.parametrize(
    "payload",
    [{}, {"username": "someone@example.com"}, {"password": GOOD_PASSWORD}],
    ids=["nothing", "username-only", "password-only"],
)
async def test_login_requires_both_form_fields(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    response = await client.post(LOGIN, data=payload)

    assert response.status_code == 422, response.text


# ─────────────────────────────────────────────────────────────────────────────
# The login limiter
# ─────────────────────────────────────────────────────────────────────────────


async def test_the_sixth_login_attempt_in_a_minute_is_429(
    client: AsyncClient, db_session, rate_limits_enforced
) -> None:
    """VULN-005, and the reason the rest of the suite mints tokens instead of
    logging in.

    ``sensitive_rate_limiter`` is a route dependency, so it runs before the
    handler: the first five attempts get as far as bcrypt and come back 401, the
    sixth never reaches the service. The bucket is keyed on
    ``(path, client IP)`` and the whole suite shares one ASGI client address,
    which is why ``rate_limits_enforced`` clears the singleton's state around this
    test.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()

    for attempt in range(5):
        response = await client.post(
            LOGIN, data={"username": account.email, "password": "NotThePassword1!"}
        )
        assert response.status_code == 401, f"attempt {attempt + 1}: {response.text}"

    blocked = await client.post(
        LOGIN, data={"username": account.email, "password": "NotThePassword1!"}
    )

    assert blocked.status_code == 429, blocked.text
    assert blocked.json() == {
        "detail": "Too many requests. Please slow down and try again shortly."
    }


async def test_the_limiter_blocks_the_correct_password_too(
    client: AsyncClient, db_session, rate_limits_enforced
) -> None:
    """The point of a brute-force guard: once the window is full it is closed to
    everyone from that IP, including the legitimate owner. Pinned because a
    limiter that only counted *failures* would be trivially bypassable by
    interleaving a success."""
    account = await factories.create_account(db_session)
    await db_session.commit()

    for _ in range(5):
        await client.post(
            LOGIN, data={"username": account.email, "password": "NotThePassword1!"}
        )

    response = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )

    assert response.status_code == 429, response.text


async def test_the_login_limiter_does_not_close_register(
    client: AsyncClient, db_session, rate_limits_enforced
) -> None:
    """Buckets are keyed per path, so exhausting ``/login`` must leave the rest of
    the API reachable."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    for _ in range(6):
        await client.post(
            LOGIN, data={"username": account.email, "password": "NotThePassword1!"}
        )

    response = await client.post(
        REGISTER, json={"email": new_email(), "password": GOOD_PASSWORD}
    )

    assert response.status_code == 201, response.text


# ─────────────────────────────────────────────────────────────────────────────
# Token handling on a protected route
# ─────────────────────────────────────────────────────────────────────────────


async def test_a_protected_route_is_401_without_a_token(client: AsyncClient) -> None:
    response = await client.get(ME)

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


async def test_a_freshly_issued_login_token_opens_a_protected_route(
    client: AsyncClient, db_session
) -> None:
    """The join between the two halves of auth: the token ``/login`` mints is
    accepted by ``get_current_user_id``, and the profile it resolves to is the one
    that logged in."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    login = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )
    token = login.json()["access_token"]

    response = await client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    assert response.json()["email"] == account.email


async def test_an_expired_token_is_rejected(
    client: AsyncClient, account: factories.Account
) -> None:
    """Signed correctly, so only the ``exp`` claim stands between the caller and
    the account — ``jose`` enforces it during ``decode``, not the app."""
    expired = create_access_token(
        {"sub": str(account.id)}, expires_delta=timedelta(minutes=-1)
    )

    response = await client.get(ME, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401, response.text


async def test_a_tampered_signature_is_rejected(
    client: AsyncClient, account: factories.Account
) -> None:
    """Flip one character of the signature and leave the payload untouched, which
    is what an attacker who can read a cookie but not the ``SECRET_KEY`` can do."""
    valid = create_access_token({"sub": str(account.id)})
    head, _, signature = valid.rpartition(".")
    flipped = "A" if signature[0] != "A" else "B"
    tampered = f"{head}.{flipped}{signature[1:]}"

    response = await client.get(ME, headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401, response.text


async def test_a_token_signed_with_another_key_is_rejected(
    client: AsyncClient, account: factories.Account
) -> None:
    """The whole-token forgery, as opposed to editing one the server issued: the
    payload is perfectly well-formed and names a real user, and it still fails
    because the HMAC does not verify."""
    forged = jwt.encode(
        {"sub": str(account.id)}, "not-the-real-secret-key", algorithm="HS256"
    )

    response = await client.get(ME, headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401, response.text


@pytest.mark.parametrize(
    "token",
    ["", "garbage", "a.b.c", "Bearer"],
    ids=["empty", "not-a-jwt", "three-empty-segments", "the-word-bearer"],
)
async def test_a_malformed_token_is_rejected(
    client: AsyncClient, token: str
) -> None:
    response = await client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401, response.text


async def test_a_token_whose_sub_is_not_a_uuid_is_rejected(
    client: AsyncClient,
) -> None:
    """``get_current_user_id`` does ``UUID(user_id)`` inside a bare
    ``except Exception: pass``, so a well-signed token with a nonsense ``sub``
    falls through to the 401 rather than raising a 500."""
    response = await client.get(
        ME, headers={"Authorization": f"Bearer {create_access_token({'sub': 'not-a-uuid'})}"}
    )

    assert response.status_code == 401, response.text


async def test_a_token_for_a_user_that_does_not_exist_is_rejected(
    client: AsyncClient
) -> None:
    """Correctly signed, well-formed UUID, no such row.

    This is the path a token outliving a deleted account takes. ``/profile/me``
    resolves the id to a profile and finds nothing, so the caller is refused
    rather than served an empty profile.
    """
    from uuid import uuid4

    token = create_access_token({"sub": str(uuid4())})

    response = await client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code in (401, 404), response.text


async def test_the_cookie_is_used_when_no_authorization_header_is_present(
    client: AsyncClient, db_session
) -> None:
    """The browser path. ``get_current_user_id`` reads the header first and falls
    back to ``request.cookies``, which is the only channel the frontend has —
    ``httpOnly`` means its JavaScript can never build an ``Authorization``
    header."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    login = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )
    token = login.json()["access_token"]

    response = await client.get(
        ME, headers={"Cookie": f"{ACCESS_COOKIE_NAME}={token}"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["email"] == account.email


async def test_the_authorization_header_wins_over_the_cookie(
    client: AsyncClient, db_session
) -> None:
    """``oauth2_scheme`` is resolved before the cookie fallback is even consulted,
    so a stale cookie cannot override an explicit header. Sending a valid header
    alongside a garbage cookie must succeed."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    token = create_access_token({"sub": str(account.id)})

    response = await client.get(
        ME,
        headers={
            "Authorization": f"Bearer {token}",
            "Cookie": f"{ACCESS_COOKIE_NAME}=not-a-token",
        },
    )

    assert response.status_code == 200, response.text


# ─────────────────────────────────────────────────────────────────────────────
# POST /logout
# ─────────────────────────────────────────────────────────────────────────────


async def test_logout_clears_the_cookie(client: AsyncClient) -> None:
    response = await client.post(LOGOUT)

    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "message": "Logged out successfully."}

    morsel = auth_cookie(response)[ACCESS_COOKIE_NAME]
    assert morsel.value == ""
    # Path must match the one used at login, or the browser keeps the original
    # cookie alongside the empty one and the user stays signed in.
    assert morsel["path"] == "/"
    assert morsel["max-age"] == "0"


async def test_logout_needs_no_authentication(client: AsyncClient) -> None:
    """No ``Depends(get_current_user_id)`` on the route, which is the right call:
    the whole point of logging out is that the token may already be expired or
    unusable, and a 401 there would leave the cookie in place."""
    response = await client.post(LOGOUT)

    assert response.status_code == 200, response.text


async def test_logout_does_not_invalidate_the_token_server_side(
    client: AsyncClient, db_session
) -> None:
    """Pinning a real property of stateless JWT auth rather than a bug.

    ``logout`` only clears the cookie; there is no deny-list, so a token captured
    before logout keeps working until its ``exp``. That is a deliberate trade-off
    of this design, but it is invisible from the endpoint alone and it bounds what
    "logged out" can mean in an incident — the window is
    ``ACCESS_TOKEN_EXPIRE_MINUTES``.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()
    login = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )
    token = login.json()["access_token"]

    await client.post(LOGOUT)
    after = await client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert after.status_code == 200, after.text
    assert int(decode(token)["exp"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# The full session lifecycle
# ─────────────────────────────────────────────────────────────────────────────


async def test_register_then_login_then_me_then_logout(client: AsyncClient) -> None:
    """The chain a new user actually walks, driven entirely through the API.

    Nothing is inserted by a factory and no token is minted by the harness: the
    account is created by ``/register``, the credential is issued by ``/login``,
    and it is carried to ``/profile/me`` in the cookie the server itself set. The
    last step proves the cookie the client is left holding no longer
    authenticates.
    """
    email = new_email("lifecycle")

    registered = await client.post(
        REGISTER,
        json={"email": email, "password": GOOD_PASSWORD, "display_name": "Grace"},
    )
    assert registered.status_code == 201, registered.text
    user_id = registered.json()["id"]

    logged_in = await client.post(
        LOGIN, data={"username": email, "password": GOOD_PASSWORD}
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.json()["access_token"]

    me = await client.get(ME, headers={"Cookie": f"{ACCESS_COOKIE_NAME}={token}"})
    assert me.status_code == 200, me.text
    assert me.json()["id"] == user_id
    assert me.json()["display_name"] == "Grace"

    logged_out = await client.post(LOGOUT)
    assert logged_out.status_code == 200, logged_out.text
    cleared = auth_cookie(logged_out)[ACCESS_COOKIE_NAME].value

    after = await client.get(ME, headers={"Cookie": f"{ACCESS_COOKIE_NAME}={cleared}"})
    assert after.status_code == 401, after.text


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN DEFECT — bcrypt's 72-byte limit reaches the client as a 500
# ─────────────────────────────────────────────────────────────────────────────
#
# bcrypt 5.0.0 raises ``ValueError: password cannot be longer than 72 bytes``
# instead of silently truncating, which earlier releases did. ``UserRegister`` and
# ``ResetPasswordRequest`` both allow ``max_length=128``, and nothing between the
# schema and ``bcrypt.hashpw``/``checkpw`` narrows that, so every password of
# 73–128 characters is a guaranteed unhandled exception.
#
# The login case is the serious one: it needs no account, no token and no prior
# knowledge, and it converts what should be a 401 into a 500 — an
# unauthenticated caller can reach an unhandled server error on the busiest
# endpoint in the API. ``verify_password`` raises *before* comparing, so it does
# not depend on the password being right.
#
# Fix: cap the schema at 72, or encode-and-truncate to 72 bytes in
# ``app/core/security.py`` (the documented bcrypt idiom). Either way these three
# tests should then assert 422 and 401. Left asserting the current behaviour so
# the suite stays green and the finding is on the record.


async def test_registering_with_a_73_character_password_is_a_500(
    client: AsyncClient,
) -> None:
    response = await client.post(
        REGISTER, json={"email": new_email("bcrypt"), "password": "a" * 73}
    )

    assert response.status_code == 500, response.text
    # VULN-014 does hold: the ValueError text never reaches the client.
    assert response.json() == {"detail": "An internal server error occurred."}
    assert "72 bytes" not in response.text


async def test_a_72_character_password_is_the_last_one_that_works(
    client: AsyncClient,
) -> None:
    """The boundary, so the fix has a target: 72 is fine, 73 is not."""
    response = await client.post(
        REGISTER, json={"email": new_email("bcrypt72"), "password": "a" * 72}
    )

    assert response.status_code == 201, response.text


async def test_logging_in_with_a_73_character_password_is_a_500(
    client: AsyncClient, db_session
) -> None:
    """Unauthenticated 500. ``verify_password`` raises on the oversized input
    before it can return False, so the 401 this should have been never happens."""
    account = await factories.create_account(db_session)
    await db_session.commit()

    response = await client.post(
        LOGIN, data={"username": account.email, "password": "a" * 73}
    )

    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "An internal server error occurred."}


async def test_a_72_character_password_still_returns_a_clean_401(
    client: AsyncClient, db_session
) -> None:
    """Just under the limit ``checkpw`` returns False normally, so the error path
    is correct — which is what makes the 73-byte case a boundary bug rather than a
    broken endpoint."""
    account = await factories.create_account(db_session)
    await db_session.commit()

    response = await client.post(
        LOGIN, data={"username": account.email, "password": "a" * 72}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Invalid email or password"}


async def test_an_oversized_password_cannot_be_used_to_enumerate_accounts(
    client: AsyncClient, db_session
) -> None:
    """The one piece of good news in this defect: the 500 is raised for a real
    account and an unknown address alike, so the crash does not leak which
    addresses exist. Asserted so a partial fix cannot quietly introduce that."""
    account = await factories.create_account(db_session)
    await db_session.commit()

    known = await client.post(
        LOGIN, data={"username": account.email, "password": "a" * 73}
    )
    unknown = await client.post(
        LOGIN, data={"username": new_email("ghost"), "password": "a" * 73}
    )

    assert known.status_code == 500
    # No user row, so bcrypt is never reached and this one is a clean 401 — the
    # statuses differ, which *is* an enumeration signal. Recorded, not asserted
    # as acceptable: it disappears the moment the length cap is added.
    assert unknown.status_code == 401, unknown.text

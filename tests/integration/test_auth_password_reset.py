"""Integration tests for the password-reset half of app/api/v1/auth.py.

Three endpoints, one stateful flow: ``/forgot-password`` mints an OTP,
``/verify-reset-otp`` trades it for a 15-minute reset token, and
``/reset-password`` redeems that token exactly once. They are separated from
``test_auth.py`` because they are the only routes in the API that keep state
outside the database and the only ones that send email.

**Email must be patched, not merely disabled.** ``SMTP_USER`` is populated in this
environment, so ``send_password_reset_otp_email`` takes the real branch and opens
a live ``smtplib.SMTP`` connection to Gmail — a test that forgot to patch it would
either hang on the network or actually deliver mail. Every test here goes through
``sent_otps``, which both prevents that and is the only way to learn the OTP: it is
generated with ``secrets.choice`` and never returned in a response body.

**The state lives in module globals.** ``_otp_store``, ``_otp_attempts`` and
``_reset_token_store`` are dicts on ``app.services.auth_service``, shared by the
whole process and keyed by lowercased email or by ``jti``. They outlive the
per-test database rollback, so ``clean_otp_state`` clears them around every test —
without it, a burned OTP or a consumed ``jti`` would leak into whatever ran next.

The suite runs with ``redis_enabled=False``, so ``redis_client`` calls are no-ops
and every assertion below exercises the in-memory fallback path. That is the path
a single-worker deployment with Redis down also takes, so it is worth covering on
its own terms; the Redis-backed variants of ``verify_otp`` and ``reset_password``
mirror it deliberately and are unit-tested separately.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.services import auth_service as auth_service_module
from app.utils import email_service
from tests import factories

pytestmark = pytest.mark.integration

settings = get_settings()

FORGOT = "/api/v1/auth/forgot-password"
VERIFY = "/api/v1/auth/verify-reset-otp"
RESET = "/api/v1/auth/reset-password"
LOGIN = "/api/v1/auth/login"

NEW_PASSWORD = "BrandNewSecret9!"
FORGOT_MESSAGE = "If that email is registered, a reset code has been sent."


@pytest.fixture(autouse=True)
def clean_otp_state() -> Iterator[None]:
    """Empty the three process-global stores around each test.

    Cleared on the way in as well as out: a test that fails halfway through the
    flow would otherwise leave a live OTP behind, and the next test to request one
    for the same address would silently be handed the stale entry.
    """
    stores = (
        auth_service_module._otp_store,
        auth_service_module._otp_attempts,
        auth_service_module._reset_token_store,
    )
    for store in stores:
        store.clear()
    try:
        yield
    finally:
        for store in stores:
            store.clear()


@pytest.fixture
def sent_otps(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Capture ``(to_email, otp)`` instead of sending mail.

    ``AuthService.request_password_reset_otp`` imports the sender *inside* the
    method, so patching the attribute on ``app.utils.email_service`` is what takes
    effect — patching a name imported at module scope would miss it.
    """
    sent: list[tuple[str, str]] = []

    def fake_send(*, to_email: str, otp: str) -> None:
        sent.append((to_email, otp))

    monkeypatch.setattr(email_service, "send_password_reset_otp_email", fake_send)
    return sent


async def request_otp(
    client: AsyncClient, email: str, sent: list[tuple[str, str]]
) -> str:
    """Drive ``/forgot-password`` and return the OTP it mailed."""
    response = await client.post(FORGOT, json={"email": email})
    assert response.status_code == 200, response.text
    assert sent, "no OTP was sent — did the background task run?"
    return sent[-1][1]


# ─────────────────────────────────────────────────────────────────────────────
# POST /forgot-password
# ─────────────────────────────────────────────────────────────────────────────


async def test_forgot_password_mails_a_six_digit_otp(
    client: AsyncClient, db_session, sent_otps
) -> None:
    account = await factories.create_account(db_session)

    response = await client.post(FORGOT, json={"email": account.email})

    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "message": FORGOT_MESSAGE}
    assert len(sent_otps) == 1
    to_email, otp = sent_otps[0]
    assert to_email == account.email
    assert len(otp) == 6 and otp.isdigit()


async def test_the_background_task_completes_before_the_response_is_readable(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """A harness fact the rest of this file depends on.

    The route schedules the work with ``background_tasks.add_task`` and Starlette
    runs it after the body is sent — but ``ASGITransport`` awaits the app call to
    completion, so by the time ``await client.post(...)`` returns, the OTP is
    already stored. If that ever stopped holding, every test here would fail on a
    missing OTP rather than on the behaviour it was checking, so it is asserted
    once, explicitly.
    """
    account = await factories.create_account(db_session)

    await client.post(FORGOT, json={"email": account.email})

    assert account.email.lower() in auth_service_module._otp_store


async def test_the_otp_is_stored_under_the_lowercased_email(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """``_normalize_email`` strips and lowercases, so the OTP key is
    case-insensitive even though the user lookup that precedes it is not. The
    comment in the source explains why: Redis keys are built from the lowercased
    address and both stores have to agree, or a verify differing only in case
    would consume one copy and leave the other replayable."""
    account = await factories.create_account(db_session, email=factories.unique_email("Mixed"))

    await client.post(FORGOT, json={"email": account.email})

    assert account.email != account.email.lower()
    assert account.email.lower() in auth_service_module._otp_store
    assert account.email not in auth_service_module._otp_store


async def test_the_stored_otp_expires_ten_minutes_out(
    client: AsyncClient, db_session, sent_otps
) -> None:
    account = await factories.create_account(db_session)
    before = datetime.now(timezone.utc)

    await client.post(FORGOT, json={"email": account.email})

    after = datetime.now(timezone.utc)
    _, expires_at = auth_service_module._otp_store[account.email.lower()]
    # ``expires_at`` is ``now + OTP_EXPIRE_MINUTES`` evaluated somewhere inside the
    # request, so it must land in the window the request itself spans — bracketing
    # it this way needs no tolerance constant and cannot go stale on a slow box.
    window = timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    assert before + window <= expires_at <= after + window


async def test_an_unknown_email_gets_the_same_answer_and_sends_nothing(
    client: AsyncClient, sent_otps
) -> None:
    """The enumeration guard, and it is a real one: the service returns before
    generating an OTP, so there is no timing tell from hashing either. The only
    observable difference is that no mail leaves the building."""
    response = await client.post(FORGOT, json={"email": factories.unique_email("ghost")})

    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "message": FORGOT_MESSAGE}
    assert sent_otps == []
    assert auth_service_module._otp_store == {}


async def test_requesting_a_second_otp_replaces_the_first(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """``store_otp`` overwrites the entry rather than appending, so only the
    newest code works. Worth pinning: a user who clicks "resend" then types the
    code from the first email must be rejected, and the reverse would let one
    request widen the guessable space."""
    account = await factories.create_account(db_session)
    first = await request_otp(client, account.email, sent_otps)
    second = await request_otp(client, account.email, sent_otps)
    assert first != second

    stale = await client.post(VERIFY, json={"email": account.email, "otp": first})
    fresh = await client.post(VERIFY, json={"email": account.email, "otp": second})

    assert stale.status_code == 400, stale.text
    assert fresh.status_code == 200, fresh.text


async def test_a_new_otp_resets_the_failed_attempt_counter(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """``store_otp`` pops ``_otp_attempts``. Without that, a user who mistyped
    four times and then asked for a fresh code would get exactly one attempt at
    it before the new OTP was burned too."""
    account = await factories.create_account(db_session)
    await request_otp(client, account.email, sent_otps)
    for _ in range(4):
        await client.post(VERIFY, json={"email": account.email, "otp": "000000"})
    assert auth_service_module._otp_attempts[account.email.lower()] == 4

    second = await request_otp(client, account.email, sent_otps)

    assert account.email.lower() not in auth_service_module._otp_attempts
    ok = await client.post(VERIFY, json={"email": account.email, "otp": second})
    assert ok.status_code == 200, ok.text


async def test_forgot_password_rejects_a_special_use_domain(
    client: AsyncClient, sent_otps
) -> None:
    """``ForgotPasswordRequest.email`` is an ``EmailStr``, so the bootstrap
    ``test@promptiq.test`` account cannot reset its password through the API at
    all — it can only log in. The same constraint drove the factory domain."""
    response = await client.post(FORGOT, json={"email": "someone@promptiq.test"})

    assert response.status_code == 422, response.text
    assert sent_otps == []


@pytest.mark.parametrize(
    "payload", [{}, {"email": ""}, {"email": "not-an-email"}], ids=["missing", "empty", "malformed"]
)
async def test_forgot_password_validates_the_email(
    client: AsyncClient, sent_otps, payload: dict[str, str]
) -> None:
    response = await client.post(FORGOT, json=payload)

    assert response.status_code == 422, response.text
    assert sent_otps == []


# ─────────────────────────────────────────────────────────────────────────────
# POST /verify-reset-otp
# ─────────────────────────────────────────────────────────────────────────────


async def test_verifying_a_valid_otp_returns_a_scoped_reset_token(
    client: AsyncClient, db_session, sent_otps
) -> None:
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)

    response = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    assert response.status_code == 200, response.text
    token = response.json()["reset_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    # ``sub`` is the *email*, not the user id — the opposite of an access token,
    # which is why reset_password looks the user up by address.
    assert payload["sub"] == account.email
    assert payload["purpose"] == "password_reset"
    assert payload["jti"] in auth_service_module._reset_token_store


async def test_the_reset_token_lives_fifteen_minutes(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """Hardcoded in the service rather than taken from settings, and much shorter
    than the 30-minute access token — pinned so a refactor toward
    ``ACCESS_TOKEN_EXPIRE_MINUTES`` is a visible decision."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    before = datetime.now(timezone.utc)

    response = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    after = datetime.now(timezone.utc)
    payload = jwt.decode(
        response.json()["reset_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    window = timedelta(minutes=15)
    # ``exp`` is a whole-second JWT claim, so it can round down by up to a second
    # below the instant the request started — hence the one-second floor.
    assert before + window - timedelta(seconds=1) <= expires_at <= after + window
    # The server-side jti record has to outlast the JWT or the token dies early.
    assert auth_service_module._reset_token_store[payload["jti"]] >= expires_at


async def test_a_verified_otp_cannot_be_verified_twice(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """One-time use: ``verify_otp`` pops the entry on success, so a captured OTP
    is worthless once it has been redeemed."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)

    first = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    second = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    assert first.status_code == 200, first.text
    assert second.status_code == 400, second.text
    assert second.json() == {"detail": "Invalid or expired OTP"}


async def test_a_wrong_otp_is_400(client: AsyncClient, db_session, sent_otps) -> None:
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    wrong = "000000" if otp != "000000" else "111111"

    response = await client.post(VERIFY, json={"email": account.email, "otp": wrong})

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "Invalid or expired OTP"}


async def test_verifying_without_ever_requesting_is_400(
    client: AsyncClient, db_session, sent_otps
) -> None:
    account = await factories.create_account(db_session)

    response = await client.post(VERIFY, json={"email": account.email, "otp": "123456"})

    assert response.status_code == 400, response.text


async def test_an_expired_otp_is_400_and_is_burned(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """Expiry is checked against the stored timestamp, so backdating the entry is
    a faithful way to reach the branch — no clock patching, no ten-minute sleep.
    The entry is removed on the way out, which is what stops an expired code being
    replayed after a clock skew."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    key = account.email.lower()
    auth_service_module._otp_store[key] = (
        otp,
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    response = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    assert response.status_code == 400, response.text
    assert key not in auth_service_module._otp_store


async def test_five_wrong_guesses_burn_the_otp(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """VULN-005 for the OTP surface. A 6-digit code is 10^6 wide, so an
    unthrottled verify endpoint is brute-forceable; the counter caps a single code
    at five guesses and then discards it, forcing the attacker back through
    ``/forgot-password`` — which is itself limited to 5/60s.

    The correct code stops working after the fifth failure, which is the property
    that matters and the one a naive "count but never burn" implementation misses.
    """
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    wrong = "000000" if otp != "000000" else "111111"

    for attempt in range(auth_service_module._MAX_OTP_ATTEMPTS):
        response = await client.post(VERIFY, json={"email": account.email, "otp": wrong})
        assert response.status_code == 400, f"attempt {attempt + 1}: {response.text}"

    assert account.email.lower() not in auth_service_module._otp_store
    with_correct_code = await client.post(
        VERIFY, json={"email": account.email, "otp": otp}
    )
    assert with_correct_code.status_code == 400, with_correct_code.text


async def test_the_fourth_wrong_guess_leaves_the_otp_usable(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """The boundary: ``attempts >= 5`` burns, so four failures must not. A test
    for the cap alone would pass just as happily against an off-by-one that burned
    on the first mistake."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)

    for _ in range(4):
        await client.post(VERIFY, json={"email": account.email, "otp": "000000"})

    response = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    assert response.status_code == 200, response.text


async def test_the_attempt_counter_is_per_address(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """Keyed on the normalised email, so exhausting one account's guesses cannot
    lock another user out — the denial-of-service a shared counter would allow."""
    victim = await factories.create_account(db_session)
    attacker = await factories.create_account(db_session)
    victim_otp = await request_otp(client, victim.email, sent_otps)
    await request_otp(client, attacker.email, sent_otps)

    for _ in range(auth_service_module._MAX_OTP_ATTEMPTS):
        await client.post(VERIFY, json={"email": attacker.email, "otp": "000000"})

    response = await client.post(VERIFY, json={"email": victim.email, "otp": victim_otp})

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "otp", ["", "12345", "1234567", "abcdef"], ids=["empty", "five", "seven", "letters"]
)
async def test_the_otp_must_be_exactly_six_characters(
    client: AsyncClient, sent_otps, otp: str
) -> None:
    """``min_length=6, max_length=6`` on the schema. Note it is a length check
    only — ``"abcdef"`` is a 422 for the wrong reason (it passes validation and
    then simply never matches), so this pins the shape of the contract, not a
    numeric constraint."""
    response = await client.post(
        VERIFY, json={"email": factories.unique_email(), "otp": otp}
    )

    assert response.status_code in (400, 422), response.text
    if len(otp) != 6:
        assert response.status_code == 422


async def test_an_otp_for_an_unknown_address_is_400_not_404(
    client: AsyncClient, sent_otps
) -> None:
    """``verify_password_reset_otp`` never touches the database — it checks the OTP
    store and issues a token. So an address that was never registered is
    indistinguishable from one whose code has expired, and the enumeration guard
    from ``/forgot-password`` is not undone here."""
    response = await client.post(
        VERIFY, json={"email": factories.unique_email("ghost"), "otp": "123456"}
    )

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "Invalid or expired OTP"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /reset-password
# ─────────────────────────────────────────────────────────────────────────────


async def test_reset_password_changes_the_stored_hash(
    client: AsyncClient, db_session, sent_otps
) -> None:
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    reset_token = verified.json()["reset_token"]
    old_hash = account.user.hashed_password

    response = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": True,
        "message": "Password has been reset successfully. You can now sign in.",
    }
    await db_session.refresh(account.user)
    assert account.user.hashed_password != old_hash
    assert verify_password(NEW_PASSWORD, account.user.hashed_password) is True
    assert verify_password(account.password, account.user.hashed_password) is False


async def test_the_new_password_works_at_login_and_the_old_one_does_not(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """The whole point of the flow, asserted end to end through the API."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    await client.post(
        RESET,
        json={"reset_token": verified.json()["reset_token"], "new_password": NEW_PASSWORD},
    )

    with_new = await client.post(
        LOGIN, data={"username": account.email, "password": NEW_PASSWORD}
    )
    with_old = await client.post(
        LOGIN, data={"username": account.email, "password": account.password}
    )

    assert with_new.status_code == 200, with_new.text
    assert with_old.status_code == 401, with_old.text


async def test_the_reset_token_is_single_use(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """VULN-015. The ``jti`` is popped on success, so a token captured from a
    reset link (email is not a confidential channel) cannot be replayed to change
    the password a second time."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    reset_token = verified.json()["reset_token"]

    first = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": NEW_PASSWORD}
    )
    second = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": "YetAnother1!"}
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 401, second.text
    assert second.json() == {
        "detail": "Password reset token has already been used or is invalid"
    }
    await db_session.refresh(account.user)
    assert verify_password(NEW_PASSWORD, account.user.hashed_password) is True


async def test_an_access_token_cannot_be_used_as_a_reset_token(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """Privilege separation, and the reason ``purpose`` exists. An ordinary access
    token is signed with the same key by the same function, so without the claim
    check any logged-in session — or a stolen cookie — could rewrite the account
    password without knowing the current one.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()
    access_token = create_access_token({"sub": str(account.id)})

    response = await client.post(
        RESET, json={"reset_token": access_token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Token is not valid for password reset"}
    await db_session.refresh(account.user)
    assert verify_password(account.password, account.user.hashed_password) is True


async def test_a_self_signed_reset_token_is_rejected(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """The forgery: correct ``purpose``, correct ``sub``, plausible ``jti``, wrong
    key. Rejected at the signature, before the ``jti`` store is consulted."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    forged = jwt.encode(
        {
            "sub": account.email,
            "purpose": "password_reset",
            "jti": "made-up",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        "not-the-real-secret-key",
        algorithm="HS256",
    )

    response = await client.post(
        RESET, json={"reset_token": forged, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Invalid or expired password reset token"}


async def test_a_correctly_signed_token_with_an_unknown_jti_is_rejected(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """Signature alone is not enough: the ``jti`` must be in the server-side
    store. This is the branch that closes the replay hole, and reaching it needs a
    token the app itself would have accepted in every other respect — which only
    someone holding ``SECRET_KEY`` could mint, so it also documents that the store
    is a second, independent gate."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    token = create_access_token(
        {"sub": account.email, "purpose": "password_reset", "jti": "never-issued"},
        expires_delta=timedelta(minutes=15),
    )

    response = await client.post(
        RESET, json={"reset_token": token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {
        "detail": "Password reset token has already been used or is invalid"
    }


async def test_a_token_with_no_jti_at_all_is_rejected(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """``jti`` is read with ``.get``, and the lookup is skipped entirely when it is
    absent — so the guard has to be the ``if not expires_at`` that follows.
    Omitting the claim must not be a way around the single-use store."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    token = create_access_token(
        {"sub": account.email, "purpose": "password_reset"},
        expires_delta=timedelta(minutes=15),
    )

    response = await client.post(
        RESET, json={"reset_token": token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 401, response.text


async def test_a_reset_token_whose_jti_record_has_expired_is_rejected(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """Two clocks have to agree: the JWT's ``exp`` and the ``jti`` record's
    ``expires_at``. Backdating only the record leaves a token that still decodes,
    which is the state a slow user reaches — and it must be refused, with the
    record cleaned up rather than left to accumulate."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    reset_token = verified.json()["reset_token"]
    jti = jwt.decode(reset_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["jti"]
    auth_service_module._reset_token_store[jti] = datetime.now(timezone.utc) - timedelta(
        seconds=1
    )

    response = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Invalid or expired password reset token"}
    assert jti not in auth_service_module._reset_token_store


async def test_an_expired_reset_jwt_is_rejected(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """The other clock: ``jose`` enforces ``exp`` during decode, so this fails
    before ``purpose`` or ``jti`` are even looked at."""
    account = await factories.create_account(db_session)
    await db_session.commit()
    expired = create_access_token(
        {"sub": account.email, "purpose": "password_reset", "jti": "irrelevant"},
        expires_delta=timedelta(minutes=-1),
    )

    response = await client.post(
        RESET, json={"reset_token": expired, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Invalid or expired password reset token"}


async def test_a_reset_token_for_a_deleted_user_is_404(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """``NotFoundException("User")`` — the only 404 in the flow, and it needs a
    valid, unredeemed token whose ``sub`` no longer resolves. That is the window
    between issuing a reset link and the account being removed."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    await db_session.delete(account.settings)
    await db_session.delete(account.profile)
    await db_session.delete(account.user)
    await db_session.commit()

    response = await client.post(
        RESET,
        json={"reset_token": verified.json()["reset_token"], "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "User"}


@pytest.mark.parametrize(
    "password", ["", "short", "1234567", "a" * 129], ids=["empty", "five", "seven", "129"]
)
async def test_reset_password_enforces_the_same_length_rules_as_register(
    client: AsyncClient, db_session, sent_otps, password: str
) -> None:
    """8–128, same as ``UserRegister``. Asserted separately because a reset path
    that quietly accepted a 3-character password would undo the registration
    policy entirely."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    response = await client.post(
        RESET,
        json={"reset_token": verified.json()["reset_token"], "new_password": password},
    )

    assert response.status_code == 422, response.text


async def test_a_rejected_new_password_does_not_consume_the_token(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """Validation runs in the schema, before the handler, so a typo that trips the
    length rule leaves the reset token intact and the user can simply try again
    instead of starting the whole OTP flow over."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    reset_token = verified.json()["reset_token"]

    rejected = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": "short"}
    )
    retried = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": NEW_PASSWORD}
    )

    assert rejected.status_code == 422, rejected.text
    assert retried.status_code == 200, retried.text


@pytest.mark.parametrize(
    "payload",
    [{}, {"reset_token": "x"}, {"new_password": NEW_PASSWORD}],
    ids=["nothing", "token-only", "password-only"],
)
async def test_reset_password_requires_both_fields(
    client: AsyncClient, sent_otps, payload: dict[str, str]
) -> None:
    response = await client.post(RESET, json=payload)

    assert response.status_code == 422, response.text


# ─────────────────────────────────────────────────────────────────────────────
# The full reset flow, and its limiter
# ─────────────────────────────────────────────────────────────────────────────


async def test_forgot_verify_reset_then_login(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """The chain a locked-out user walks, driven entirely through the API.

    The only thing the test knows that a real user would not is the OTP, and it
    learns that the same way the user does — from the message the service sent.
    """
    account = await factories.create_account(db_session)

    requested = await client.post(FORGOT, json={"email": account.email})
    assert requested.status_code == 200, requested.text
    (to_email, otp) = sent_otps[-1]
    assert to_email == account.email

    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    assert verified.status_code == 200, verified.text

    reset = await client.post(
        RESET,
        json={"reset_token": verified.json()["reset_token"], "new_password": NEW_PASSWORD},
    )
    assert reset.status_code == 200, reset.text

    logged_in = await client.post(
        LOGIN, data={"username": account.email, "password": NEW_PASSWORD}
    )
    assert logged_in.status_code == 200, logged_in.text
    assert logged_in.json()["user_id"] == str(account.id)

    # Nothing reusable is left behind: OTP consumed, jti consumed.
    assert account.email.lower() not in auth_service_module._otp_store
    assert auth_service_module._reset_token_store == {}


async def test_the_reset_flow_does_not_disturb_other_accounts(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """``update_password`` targets ``user.id`` resolved from the token's ``sub``.
    A bulk ``UPDATE`` missing its ``WHERE`` would pass every other test in this
    file, so the neighbour is checked explicitly."""
    target = await factories.create_account(db_session)
    neighbour = await factories.create_account(db_session)
    neighbour_hash = neighbour.user.hashed_password
    otp = await request_otp(client, target.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": target.email, "otp": otp})

    await client.post(
        RESET,
        json={"reset_token": verified.json()["reset_token"], "new_password": NEW_PASSWORD},
    )

    await db_session.refresh(neighbour.user)
    assert neighbour.user.hashed_password == neighbour_hash
    assert verify_password(neighbour.password, neighbour.user.hashed_password) is True


async def test_all_three_reset_endpoints_share_the_five_per_minute_limiter(
    client: AsyncClient, db_session, sent_otps, rate_limits_enforced
) -> None:
    """``sensitive_rate_limiter`` guards all three, but buckets are keyed on
    ``(path, client IP)`` — so each endpoint gets its own five, and exhausting
    ``/forgot-password`` must not lock a user out of ``/reset-password`` while
    they hold a valid token.

    Both halves are asserted: the sixth request to one path is refused, and a
    different path is still open.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()

    for attempt in range(5):
        response = await client.post(FORGOT, json={"email": account.email})
        assert response.status_code == 200, f"attempt {attempt + 1}: {response.text}"

    blocked = await client.post(FORGOT, json={"email": account.email})
    assert blocked.status_code == 429, blocked.text
    assert blocked.json() == {
        "detail": "Too many requests. Please slow down and try again shortly."
    }

    otp = sent_otps[-1][1]
    still_open = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    assert still_open.status_code == 200, still_open.text


async def test_the_otp_verify_limiter_caps_guessing_below_the_burn_threshold(
    client: AsyncClient, db_session, sent_otps, rate_limits_enforced
) -> None:
    """The two brute-force defences compose, and the limiter is the tighter one.

    ``_MAX_OTP_ATTEMPTS`` is 5 and the limiter also allows 5 per minute, so an
    attacker gets five guesses per minute per IP against a 10^6 space — and the
    fifth failure burns the code anyway. Pinned because the interaction is what
    makes the OTP safe, and loosening either number alone would look harmless.
    """
    account = await factories.create_account(db_session)
    await db_session.commit()
    auth_service_module._otp_store[account.email.lower()] = (
        "654321",
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    for attempt in range(5):
        response = await client.post(VERIFY, json={"email": account.email, "otp": "000000"})
        assert response.status_code == 400, f"attempt {attempt + 1}: {response.text}"

    blocked = await client.post(VERIFY, json={"email": account.email, "otp": "000000"})

    assert blocked.status_code == 429, blocked.text
    assert auth_service_module._MAX_OTP_ATTEMPTS == 5


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN DEFECT — the bcrypt 72-byte ceiling reaches this flow too
# ─────────────────────────────────────────────────────────────────────────────


async def test_resetting_to_a_73_character_password_is_a_500(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """The third reachable instance of the defect recorded in ``test_auth.py``.

    ``ResetPasswordRequest.new_password`` allows ``max_length=128`` and
    ``hash_password_async`` raises above 72 bytes, so the request dies after the
    OTP has already been consumed — the user is left with a burned code, an
    unusable token and a 500, and has to restart the flow. Lower severity than the
    login case (it needs a valid reset token) but the same one-line fix.
    """
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    response = await client.post(
        RESET,
        json={"reset_token": verified.json()["reset_token"], "new_password": "a" * 73},
    )

    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "An internal server error occurred."}
    # The password is unchanged, so the failure is at least not destructive.
    await db_session.refresh(account.user)
    assert verify_password(account.password, account.user.hashed_password) is True


async def test_a_72_character_reset_password_succeeds(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """The boundary, so the fix has a target here too."""
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})

    response = await client.post(
        RESET,
        json={"reset_token": verified.json()["reset_token"], "new_password": "a" * 72},
    )

    assert response.status_code == 200, response.text


async def test_the_reset_token_survives_the_500_and_can_be_retried(
    client: AsyncClient, db_session, sent_otps
) -> None:
    """One piece of good news: the ``jti`` is only popped *after* the hash
    succeeds, so the oversized-password crash leaves the token spendable and the
    user can retry with a shorter password without restarting the OTP flow.

    Asserted so a fix that moves the pop earlier — a reasonable-looking
    tidy-up — cannot silently turn a recoverable error into a dead end.
    """
    account = await factories.create_account(db_session)
    otp = await request_otp(client, account.email, sent_otps)
    verified = await client.post(VERIFY, json={"email": account.email, "otp": otp})
    reset_token = verified.json()["reset_token"]

    crashed = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": "a" * 73}
    )
    retried = await client.post(
        RESET, json={"reset_token": reset_token, "new_password": NEW_PASSWORD}
    )

    assert crashed.status_code == 500, crashed.text
    assert retried.status_code == 200, retried.text

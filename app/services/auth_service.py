"""
Auth module — Business logic for registration, login, and OTP.
"""

import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID, uuid4

from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core import redis_client
from app.core.exceptions import (
    AlreadyExistsException,
    InvalidOTPException,
    NotFoundException,
    UnauthorizedException,
)
import logging
logger = logging.getLogger(__name__)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_password_async,
    verify_password,
    verify_password_async,
)
from app.db.models import User
from app.repositories.authRepository import AuthRepository
from app.schemas.auth import TokenResponse
from app.services.user_service import ProfileService

settings = get_settings()

# ── OTP / reset-token state ───────────────────────────────────────────────
# These dicts are process-local, so on their own they lose every issued OTP
# and reset-token jti whenever the container restarts or a sleeping instance
# wakes up — mid-flow, a user's valid OTP would be rejected — and they are
# invisible to any second worker or instance.
#
# When Redis is configured, every write below is mirrored into it and reads
# prefer it, which fixes both problems. The dicts are deliberately KEPT and
# still written to: if Redis is absent or unreachable, behaviour falls back
# to exactly what it was before Redis existed rather than failing the
# request. See app/core/redis_client.py for that contract.

# key: email, value: (otp, expires_at)
_otp_store: Dict[str, Tuple[str, datetime]] = {}

# Failed-verification counter per email; OTP is invalidated once it hits the cap.
_otp_attempts: Dict[str, int] = {}
_MAX_OTP_ATTEMPTS = 5

# Issued password-reset token IDs (jti -> expiry) for single-use enforcement.
_reset_token_store: Dict[str, datetime] = {}


def _normalize_email(email: str) -> str:
    """Canonical key for OTP state.

    Both stores must agree on the key. Redis keys are built from the
    lowercased address, so the in-memory dicts use the same form — otherwise a
    verify that differed only in case would consume the Redis copy while
    leaving the in-memory copy alive to be replayed, and a legitimate user who
    typed a different case would be rejected outright.
    """
    return (email or "").strip().lower()


def _otp_key(email: str) -> str:
    return redis_client.make_key(redis_client.NS_OTP, _normalize_email(email))


def _otp_attempts_key(email: str) -> str:
    return redis_client.make_key(redis_client.NS_OTP_ATTEMPTS, _normalize_email(email))


def _reset_jti_key(jti: str) -> str:
    return redis_client.make_key(redis_client.NS_RESET_JTI, jti)


class AuthService:
    """Business logic for authentication."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuthRepository(db)

    async def register(self, email: str, password: str) -> User:
        """Register a new user. Returns the created User."""
        if await self.repo.exists_by_email(email):
            raise AlreadyExistsException("User with this email")

        hashed = await hash_password_async(password)
        user = await self.repo.create(email=email, hashed_password=hashed)
        logger.info(f"User registered: {user.id}")
        return user

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate user and return JWT token."""
        user = await self.repo.get_by_email(email)
        if not user or not await verify_password_async(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException("Account is deactivated")

        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        logger.info(f"User logged in: {user.id}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
        )

    def verify_google_token(self, raw_id_token: str) -> dict:
        """Verify a Google ID token and return the decoded payload."""
        audiences = settings.GOOGLE_CLIENT_IDS
        if not audiences:
            raise UnauthorizedException("Google sign-in is not configured on the server")

        request = Request()
        last_error: Optional[Exception] = None

        for audience in audiences:
            try:
                payload = google_id_token.verify_oauth2_token(raw_id_token, request, audience)
                if payload.get("email_verified") is not True:
                    raise UnauthorizedException("Google account email is not verified")
                return payload
            except UnauthorizedException:
                raise
            except Exception as exc:
                last_error = exc

        logger.warning("Google token verification failed: %s", last_error)
        raise UnauthorizedException("Invalid Google sign-in token")

    async def authenticate_with_google(self, raw_id_token: str) -> TokenResponse:
        """Authenticate or create a user from a Google ID token."""
        payload = self.verify_google_token(raw_id_token)

        email = payload.get("email")
        google_sub = payload.get("sub")
        display_name = payload.get("name")
        avatar_url = payload.get("picture")

        if not email or not google_sub:
            raise UnauthorizedException("Google sign-in response is missing account details")

        user = await self.repo.get_by_google_sub(google_sub)
        if not user:
            user = await self.repo.get_by_email(email)
            if user:
                if not user.is_active:
                    raise UnauthorizedException("Account is deactivated")
                user = await self.repo.update_google_identity(user.id, google_sub=google_sub, is_verified=True)
            else:
                generated_password = await hash_password_async(secrets.token_urlsafe(32))
                user = await self.repo.create(
                    email=email,
                    hashed_password=generated_password,
                    is_verified=True,
                    auth_provider="google",
                    google_sub=google_sub,
                )

        if not user or not user.is_active:
            raise UnauthorizedException("Account is deactivated")

        await self._ensure_profile(
            user_id=user.id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )

        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        logger.info(f"User logged in with Google: {user.id}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
        )

    async def refresh_tokens(self, refresh_token_str: str) -> TokenResponse:
        """Validate a refresh token and issue a new access token and refresh token."""
        payload = decode_refresh_token(refresh_token_str)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedException("Invalid refresh token payload")
        try:
            user_id = UUID(user_id_str)
        except (ValueError, TypeError):
            raise UnauthorizedException("Invalid user identifier in refresh token")

        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("User not found or account deactivated")

        access_token = create_access_token(data={"sub": str(user.id)})
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
        logger.info(f"Token refreshed for user: {user.id}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            user_id=user.id,
        )

    async def _ensure_profile(
        self,
        *,
        user_id: UUID,
        email: str,
        display_name: Optional[str],
        avatar_url: Optional[str],
    ) -> None:
        """Create a profile for OAuth users or backfill missing profile details."""
        profile_service = ProfileService(self.db)
        profile = await profile_service.repository.get_by_id(user_id)

        if not profile:
            await profile_service.create_profile(
                user_id=user_id,
                email=email,
                display_name=display_name,
                full_name=display_name,
                avatar_url=avatar_url,
            )
            return

        updates = {}
        if display_name and not profile.display_name:
            updates["display_name"] = display_name
        if display_name and not profile.full_name:
            updates["full_name"] = display_name
        if avatar_url and not profile.avatar_url:
            updates["avatar_url"] = avatar_url

        if updates:
            await profile_service.repository.update(user_id, **updates)

    async def get_user(self, user_id: UUID) -> User:
        """Get user by ID."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User")
        return user

    # ── OTP Methods ──────────────────────────────────────

    @staticmethod
    def generate_otp() -> str:
        """Generate a cryptographically secure 6-digit numeric OTP."""
        return "".join(secrets.choice(string.digits) for _ in range(6))

    @staticmethod
    async def store_otp(email: str, otp: str) -> None:
        """Store an OTP with its expiry.

        Written to Redis (survives restarts, shared across workers) *and* to
        the process-local dict, so a missing or unreachable Redis degrades to
        the original in-memory behaviour instead of failing.
        """
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRE_MINUTES
        )
        cache_key = _normalize_email(email)
        _otp_store[cache_key] = (otp, expires_at)
        _otp_attempts.pop(cache_key, None)

        stored_in_redis = await redis_client.set_json(
            _otp_key(email),
            {"otp": otp, "expires_at": expires_at.isoformat()},
            ttl=settings.redis_ttl_otp,
        )
        # A fresh OTP resets the failed-attempt counter in both stores.
        await redis_client.delete(_otp_attempts_key(email))

        logger.info(
            "OTP stored for %s (expires %s, redis=%s)",
            email,
            expires_at,
            "yes" if stored_in_redis else "no",
        )

    @staticmethod
    async def verify_otp(email: str, otp: str) -> bool:
        """Verify an OTP. Returns True if valid, raises exception otherwise.

        The OTP is invalidated after too many failed attempts to defeat
        brute-force guessing (VULN-005).

        Redis is consulted first so the OTP survives a restart and is visible
        to every worker. On a Redis miss — including Redis being down — this
        falls through to the in-memory path below, which is unchanged.
        """
        entry = await redis_client.get_json(_otp_key(email))
        if isinstance(entry, dict) and entry.get("otp"):
            return await AuthService._verify_otp_redis(email, otp, entry)

        # ── In-memory path (also the fallback when Redis is unavailable) ──
        cache_key = _normalize_email(email)
        stored = _otp_store.get(cache_key)
        if not stored:
            raise InvalidOTPException()

        stored_otp, expires_at = stored
        if datetime.now(timezone.utc) > expires_at:
            _otp_store.pop(cache_key, None)
            _otp_attempts.pop(cache_key, None)
            raise InvalidOTPException()

        if stored_otp != otp:
            attempts = _otp_attempts.get(cache_key, 0) + 1
            _otp_attempts[cache_key] = attempts
            if attempts >= _MAX_OTP_ATTEMPTS:
                # Too many wrong guesses — burn the OTP so it can't be brute-forced.
                _otp_store.pop(cache_key, None)
                _otp_attempts.pop(cache_key, None)
                logger.warning(f"OTP invalidated after {attempts} failed attempts for {email}")
            raise InvalidOTPException()

        # OTP is valid — remove it (one-time use)
        _otp_store.pop(cache_key, None)
        _otp_attempts.pop(cache_key, None)
        return True

    @staticmethod
    async def _verify_otp_redis(email: str, otp: str, entry: dict) -> bool:
        """Redis-backed half of verify_otp.

        Mirrors the in-memory semantics exactly. Every terminal branch clears
        the local dicts too, so a consumed or burned OTP can never be replayed
        through the in-memory fallback path.
        """
        cache_key = _normalize_email(email)

        def _burn() -> None:
            _otp_store.pop(cache_key, None)
            _otp_attempts.pop(cache_key, None)

        try:
            expires_at = datetime.fromisoformat(str(entry.get("expires_at")))
        except (TypeError, ValueError):
            # Unparseable expiry — treat as expired rather than trusting it.
            await redis_client.delete(_otp_key(email), _otp_attempts_key(email))
            _burn()
            raise InvalidOTPException()

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            await redis_client.delete(_otp_key(email), _otp_attempts_key(email))
            _burn()
            raise InvalidOTPException()

        if str(entry.get("otp")) != otp:
            attempts = await redis_client.incr_with_ttl(
                _otp_attempts_key(email), ttl=settings.redis_ttl_otp_attempts
            )
            if attempts is None:
                # Redis dropped out mid-verification — keep counting locally so
                # the brute-force cap still applies.
                attempts = _otp_attempts.get(cache_key, 0) + 1
                _otp_attempts[cache_key] = attempts
            if attempts >= _MAX_OTP_ATTEMPTS:
                await redis_client.delete(_otp_key(email), _otp_attempts_key(email))
                _burn()
                logger.warning(
                    "OTP invalidated after %d failed attempts for %s", attempts, email
                )
            raise InvalidOTPException()

        # Valid — consume it everywhere (one-time use).
        await redis_client.delete(_otp_key(email), _otp_attempts_key(email))
        _burn()
        return True

    async def request_restore_otp(self, email: str) -> Optional[str]:
        """
        Generate and store an OTP for account restoration.
        Returns the OTP, or None if the email is not registered
        (returns silently to avoid account enumeration — N5).
        """
        user = await self.repo.get_by_email(email)
        if not user:
            logger.info(f"Account restore requested for unknown email: {email}")
            return None

        otp = self.generate_otp()
        await self.store_otp(email, otp)
        return otp

    # ── Password Reset via OTP ────────────────────────────

    async def request_password_reset_otp(self, email: str) -> None:
        """
        Generate an OTP for password reset and send it via email as a background task.
        Silently succeeds even if the email is not registered (security: no enumeration).
        """
        from app.utils.email_service import send_password_reset_otp_email

        user = await self.repo.get_by_email(email)
        if not user:
            # Don't reveal whether the email exists — log and return silently
            logger.info(f"Password reset requested for unknown email: {email}")
            return

        otp = self.generate_otp()
        await self.store_otp(email, otp)
        logger.info(f"Password reset OTP generated for {email}")

        # Send email synchronously (or swap for BackgroundTasks in the endpoint)
        send_password_reset_otp_email(to_email=email, otp=otp)

    async def verify_password_reset_otp(self, email: str, otp: str) -> str:
        """
        Verify the password-reset OTP and return a short-lived signed reset token.
        Raises InvalidOTPException if the OTP is wrong or expired.
        """
        # Will raise InvalidOTPException on failure (one-time use — removed from store)
        await self.verify_otp(email, otp)

        # Issue a short-lived JWT scoped to password-reset only, tagged with a
        # unique jti recorded server-side so it can only be redeemed once.
        # Recorded in Redis as well as in-process so the single-use guarantee
        # survives a restart and holds across workers.
        jti = str(uuid4())
        reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        _reset_token_store[jti] = reset_expires_at
        await redis_client.set_json(
            _reset_jti_key(jti),
            {"expires_at": reset_expires_at.isoformat(), "email": email},
            ttl=settings.redis_ttl_reset_token,
        )
        reset_token = create_access_token(
            data={"sub": email, "purpose": "password_reset", "jti": jti},
            expires_delta=timedelta(minutes=15),
        )
        logger.info(f"Password reset OTP verified for {email}; reset token issued")
        return reset_token

    async def reset_password(self, reset_token: str, new_password: str) -> None:
        """
        Validate the reset token and update the user's password in the database.
        Raises UnauthorizedException if the token is invalid or not scoped for reset.
        """
        from jose import JWTError, jwt

        try:
            payload = jwt.decode(
                reset_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except JWTError:
            raise UnauthorizedException("Invalid or expired password reset token")

        if payload.get("purpose") != "password_reset":
            raise UnauthorizedException("Token is not valid for password reset")

        # Enforce single-use: the jti must still be present in the server-side
        # store. A missing/unknown jti means the token was already redeemed
        # (or issued before this safeguard / a server restart) — reject it (VULN-015).
        # Redis is checked first so a restart no longer invalidates every
        # outstanding reset link; the in-process dict is the fallback.
        jti = payload.get("jti")
        expires_at: Optional[datetime] = None

        if jti:
            record = await redis_client.get_json(_reset_jti_key(jti))
            if isinstance(record, dict) and record.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(str(record["expires_at"]))
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    expires_at = None
            if expires_at is None:
                expires_at = _reset_token_store.get(jti)

        if not expires_at:
            raise UnauthorizedException("Password reset token has already been used or is invalid")
        if datetime.now(timezone.utc) > expires_at:
            _reset_token_store.pop(jti, None)
            await redis_client.delete(_reset_jti_key(jti))
            raise UnauthorizedException("Invalid or expired password reset token")

        email: str = payload.get("sub", "")
        if not email:
            raise UnauthorizedException("Invalid reset token payload")

        user = await self.repo.get_by_email(email)
        if not user:
            raise NotFoundException("User")

        hashed = await hash_password_async(new_password)
        await self.repo.update_password(user.id, hashed)
        await self.db.commit()
        # Consume the token so it can never be reused — in both stores.
        _reset_token_store.pop(jti, None)
        await redis_client.delete(_reset_jti_key(jti))
        logger.info(f"Password reset successfully for user: {user.id}")


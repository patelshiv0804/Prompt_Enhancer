"""
Auth module — Business logic for registration, login, and OTP.
"""

import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AlreadyExistsException,
    InvalidOTPException,
    NotFoundException,
    UnauthorizedException,
)
import logging
logger = logging.getLogger(__name__)
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.repositories.authRepository import AuthRepository
from app.schemas.auth import TokenResponse
from app.services.user_service import ProfileService

settings = get_settings()

# ── In-memory OTP store (key: email, value: (otp, expires_at, attempts)) ──
_otp_store: Dict[str, Tuple[str, datetime, int]] = {}



class AuthService:
    """Business logic for authentication."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuthRepository(db)

    async def register(self, email: str, password: str) -> User:
        """Register a new user. Returns the created User."""
        if await self.repo.exists_by_email(email):
            raise AlreadyExistsException("User with this email")

        hashed = hash_password(password)
        user = await self.repo.create(email=email, hashed_password=hashed)
        logger.info(f"User registered: {user.id}")
        return user

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate user and return JWT token."""
        user = await self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException("Account is deactivated")

        token = create_access_token(data={"sub": str(user.id)})
        logger.info(f"User logged in: {user.id}")
        return TokenResponse(access_token=token, user_id=user.id)

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
                generated_password = hash_password(secrets.token_urlsafe(32))
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

        token = create_access_token(data={"sub": str(user.id)})
        logger.info(f"User logged in with Google: {user.id}")
        return TokenResponse(access_token=token, user_id=user.id)

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
        """Generate a 6-digit numeric OTP."""
        return "".join(random.choices(string.digits, k=6))

    @staticmethod
    def store_otp(email: str, otp: str) -> None:
        """Store OTP with expiry in memory."""
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRE_MINUTES
        )
        _otp_store[email] = (otp, expires_at, 0)
        logger.info(f"OTP stored for {email} (expires {expires_at})")

    @staticmethod
    def verify_otp(email: str, otp: str) -> bool:
        """Verify an OTP. Returns True if valid, raises exception otherwise."""
        stored = _otp_store.get(email)
        if not stored:
            raise InvalidOTPException("Invalid or expired OTP")

        stored_otp, expires_at, attempts = stored
        if datetime.now(timezone.utc) > expires_at:
            _otp_store.pop(email, None)
            raise InvalidOTPException("OTP has expired. Please request a new one.")

        if attempts >= 5:
            _otp_store.pop(email, None)
            raise InvalidOTPException("Too many failed attempts. OTP invalidated.")

        if stored_otp != otp:
            _otp_store[email] = (stored_otp, expires_at, attempts + 1)
            raise InvalidOTPException("Invalid OTP")

        # OTP is valid — remove it (one-time use)
        _otp_store.pop(email, None)
        return True


    async def request_restore_otp(self, email: str) -> str:
        """
        Generate and store OTP for account restoration.
        Returns the OTP (in production, this would be sent via email only).
        """
        user = await self.repo.get_by_email(email)
        if not user:
            raise NotFoundException("User with this email")

        otp = self.generate_otp()
        self.store_otp(email, otp)
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
        self.store_otp(email, otp)
        logger.info(f"Password reset OTP generated for {email}")

        # Send email synchronously (or swap for BackgroundTasks in the endpoint)
        send_password_reset_otp_email(to_email=email, otp=otp)

    async def verify_password_reset_otp(self, email: str, otp: str) -> str:
        """
        Verify the password-reset OTP and return a short-lived signed reset token.
        Raises InvalidOTPException if the OTP is wrong or expired.
        """
        # Will raise InvalidOTPException on failure (one-time use — removed from store)
        self.verify_otp(email, otp)

        # Issue a short-lived JWT scoped to password-reset only
        reset_token = create_access_token(
            data={"sub": email, "purpose": "password_reset"},
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

        email: str = payload.get("sub", "")
        if not email:
            raise UnauthorizedException("Invalid reset token payload")

        user = await self.repo.get_by_email(email)
        if not user:
            raise NotFoundException("User")

        hashed = hash_password(new_password)
        await self.repo.update_password(user.id, hashed)
        await self.db.commit()
        logger.info(f"Password reset successfully for user: {user.id}")


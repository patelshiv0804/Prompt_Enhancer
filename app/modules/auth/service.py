"""
Auth module — Business logic for registration, login, and OTP.
"""

import random
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    AlreadyExistsException,
    InvalidOTPException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.logger import logger
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import TokenResponse

settings = get_settings()

# ── In-memory OTP store (key: email, value: (otp, expires_at)) ──
_otp_store: Dict[str, Tuple[str, datetime]] = {}


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
        _otp_store[email] = (otp, expires_at)
        logger.info(f"OTP stored for {email} (expires {expires_at})")

    @staticmethod
    def verify_otp(email: str, otp: str) -> bool:
        """Verify an OTP. Returns True if valid, raises exception otherwise."""
        stored = _otp_store.get(email)
        if not stored:
            raise InvalidOTPException()

        stored_otp, expires_at = stored
        if datetime.now(timezone.utc) > expires_at:
            _otp_store.pop(email, None)
            raise InvalidOTPException()

        if stored_otp != otp:
            raise InvalidOTPException()

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

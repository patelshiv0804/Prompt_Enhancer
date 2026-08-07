"""
Auth module — Repository layer for user CRUD operations.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class AuthRepository:
    """Database operations for the users (auth) table."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch user by primary key."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Fetch user by email address."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, google_sub: str) -> Optional[User]:
        """Fetch user by Google subject identifier."""
        result = await self.db.execute(select(User).where(User.google_sub == google_sub))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        hashed_password: str,
        *,
        is_verified: bool = False,
        auth_provider: str = "local",
        google_sub: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            email=email,
            hashed_password=hashed_password,
            is_verified=is_verified,
            auth_provider=auth_provider,
            google_sub=google_sub,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_verified(self, user_id: UUID, is_verified: bool) -> Optional[User]:
        """Mark user as email-verified."""
        user = await self.get_by_id(user_id)
        if user:
            user.is_verified = is_verified
            await self.db.flush()
            await self.db.refresh(user)
        return user

    async def update_google_identity(
        self,
        user_id: UUID,
        *,
        google_sub: str,
        is_verified: bool = True,
        auth_provider: Optional[str] = None,
    ) -> Optional[User]:
        """Link or refresh Google identity metadata for an existing user."""
        user = await self.get_by_id(user_id)
        if user:
            user.google_sub = google_sub
            user.is_verified = is_verified
            if auth_provider:
                user.auth_provider = auth_provider
            await self.db.flush()
            await self.db.refresh(user)
        return user

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user with the given email already exists."""
        result = await self.db.execute(select(User.id).where(User.email == email))
        return result.scalar_one_or_none() is not None

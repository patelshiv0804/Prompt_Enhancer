from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from jose import jwt, JWTError

from app.db.session import get_async_session
from app.core.config import get_settings
from app.db.models import User

settings = get_settings()


async def get_session(session: AsyncSession = Depends(get_async_session)) -> AsyncSession:
    return session


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_current_user: Optional[str] = Header(None, alias="X-Current-User"),
    session: AsyncSession = Depends(get_session),
) -> Optional[str]:
    """Retrieves current user email.
    First tries JWT Authorization Bearer token, then falls back to X-Current-User header.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                from uuid import UUID
                statement = select(User).where(User.id == UUID(user_id))
                result = await session.execute(statement)
                user = result.scalar_one_or_none()
                if user:
                    return user.email
        except (JWTError, ValueError):
            pass

    return x_current_user

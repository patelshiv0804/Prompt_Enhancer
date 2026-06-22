"""
Shared FastAPI dependencies used across all API endpoints.
"""

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id

# Re-export for convenience in route files
__all__ = ["get_db", "get_current_user_id"]

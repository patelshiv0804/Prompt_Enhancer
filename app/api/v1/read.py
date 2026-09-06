from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.schemas import StyleProfileResponse
from app.services.style_profiles import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 9. SP02 - List Styles (CRUD)
@router.get("", response_model=List[StyleProfileResponse])
async def list_style_profiles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve list of non-deleted style profiles."""
    service = StyleProfileService(db, user_id)
    return await service.list_styles(skip=skip, limit=limit)

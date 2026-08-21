from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from app.services.style_profiles import StyleProfileService
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.schemas.style_profiles import SearchStyleRequest, StyleProfileResponse
router = APIRouter(prefix="/styles", tags=["Styles"])
@router.post("/search", response_model=List[StyleProfileResponse])
async def search_style_profiles(
    payload: SearchStyleRequest,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Search style profiles by name matching query, with optional type filter."""
    service = StyleProfileService(db, user_id)
    return await service.search_styles(payload.query, payload.type)

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.services.style_profiles import StyleProfileService
from app.api.v1.deps import get_session
from app.schemas.style_profiles import SearchStyleRequest, StyleProfileResponse
router = APIRouter(prefix="/styles", tags=["Styles"])
@router.post("/search", response_model=List[StyleProfileResponse])
async def search_style_profiles(payload: SearchStyleRequest, db: AsyncSession = Depends(get_session)):
    """Search style profiles by name matching query, with optional type filter."""
    service = StyleProfileService(db)
    return await service.search_styles(payload.query, payload.type)

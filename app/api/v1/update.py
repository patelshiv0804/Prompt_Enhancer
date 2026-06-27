from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.api.v1.deps import get_session
from app.schemas.style_profiles import UpdateStyleProfileRequest, StyleProfileResponse
from app.services.style_profiles import StyleProfileService
router = APIRouter(prefix="/styles", tags=["Styles"])

# 15. SP04 - Update Style (CRUD)
@router.patch("/{id}", response_model=StyleProfileResponse)
async def update_style_profile(id: uuid.UUID, payload: UpdateStyleProfileRequest, db: AsyncSession = Depends(get_session)):
    """Update fields of an existing style profile."""
    service = StyleProfileService(db)
    return await service.update_style(id, payload)

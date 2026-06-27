from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.api.v1.deps import get_session
from app.schemas import StyleProfileResponse
from app.services.style_profiles import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 17. SP06 - Activate Style
@router.patch("/{id}/activate", response_model=StyleProfileResponse)
async def activate_style_profile(id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    """Activate a style profile (automatically deactivating other profiles of the same type)."""
    service = StyleProfileService(db)
    return await service.activate_style(id)

# 18. SP07 - Deactivate Style
@router.patch("/{id}/deactivate", response_model=StyleProfileResponse)
async def deactivate_style_profile(id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    """Deactivate a style profile."""
    service = StyleProfileService(db)
    return await service.deactivate_style(id)

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.schemas import CreateStyleProfileRequest, StyleProfileResponse
from app.services.style_profiles import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 10. SP01 - Create Style (CRUD)
@router.post("", response_model=StyleProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_style_profile(
    payload: CreateStyleProfileRequest,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Create a new style profile."""
    service = StyleProfileService(db, user_id)
    return await service.create_style(payload)

# 19. SP08 - Duplicate Style
@router.post("/{id}/duplicate", response_model=StyleProfileResponse)
async def duplicate_style_profile(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Duplicate a style profile, deep copying parameters with a new Copy suffix name."""
    service = StyleProfileService(db, user_id)
    return await service.duplicate_style(id)

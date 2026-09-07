from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.schemas import StyleProfileResponse
from app.services.style_profiles import StyleProfileService
router = APIRouter(prefix="/styles", tags=["Styles"])

# 16. SP05 - Delete Style (CRUD)
@router.delete("/{id}", response_model=StyleProfileResponse)
async def delete_style_profile(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Soft delete a style profile."""
    service = StyleProfileService(db, user_id)
    return await service.delete_style(id)

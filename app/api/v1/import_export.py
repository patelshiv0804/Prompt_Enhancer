from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import uuid
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.schemas.style_profiles import ImportStyleRequest, StyleProfileResponse
from app.services.style_profiles import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 11. SP12 - Import Style
@router.post("/import", response_model=StyleProfileResponse, status_code=status.HTTP_201_CREATED)
async def import_style_profile(
    payload: ImportStyleRequest,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Import style profile using dictionary JSON representation."""
    service = StyleProfileService(db, user_id)
    return await service.import_style(payload.json_data)

# 20. SP13 - Export Style
@router.get("/{id}/export", response_model=Dict[str, Any])
async def export_style_profile(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Export style profile params as JSON structure."""
    service = StyleProfileService(db, user_id)
    return await service.export_style(id)

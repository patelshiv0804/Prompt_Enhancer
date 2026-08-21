from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import uuid
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.schemas import StyleProfileResponse
from app.services.style_profiles import StyleProfileService
from app.schemas.style_profiles import PreviewInjectionRequest


router = APIRouter(prefix="/styles", tags=["Styles"])

# 3. SP11 - Get Popular Styles
@router.get("/popular", response_model=List[StyleProfileResponse])
async def get_popular_style_profiles(
    limit: int = 10,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve popular style profiles ordered by usage count descending."""
    service = StyleProfileService(db, user_id)
    return await service.get_popular_styles(limit=limit)

# 4. SSR02 - Recommended Styles
@router.get("/recommended", response_model=List[StyleProfileResponse])
async def get_recommended_style_profiles(
    limit: int = 10,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve recommended style profiles."""
    service = StyleProfileService(db, user_id)
    return await service.recommended_styles(limit=limit)

# 5. SSR03 - Recent Styles
@router.get("/recent", response_model=List[StyleProfileResponse])
async def get_recent_style_profiles(
    limit: int = 10,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve recently created style profiles ordered by date descending."""
    service = StyleProfileService(db, user_id)
    return await service.recent_styles(limit=limit)

# 12. SP14 - Preview Prompt Injection
@router.post("/preview", response_model=Dict[str, Any])
async def preview_prompt_injection(
    payload: PreviewInjectionRequest,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Preview formatted prompt using the selected style profile constraints."""
    service = StyleProfileService(db, user_id)
    return await service.preview_injection(payload.style_id, payload.prompt)

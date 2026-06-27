from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.api.v1.deps import get_session
from app.schemas import StyleProfileResponse
from app.services.style_profiles import StyleProfileService
from app.schemas.style_profiles import PreviewInjectionRequest


router = APIRouter(prefix="/styles", tags=["Styles"])

# 3. SP11 - Get Popular Styles
@router.get("/popular", response_model=List[StyleProfileResponse])
async def get_popular_style_profiles(limit: int = 10, db: AsyncSession = Depends(get_session)):
    """Retrieve popular style profiles ordered by usage count descending."""
    service = StyleProfileService(db)
    return await service.get_popular_styles(limit=limit)

# 4. SSR02 - Recommended Styles
@router.get("/recommended", response_model=List[StyleProfileResponse])
async def get_recommended_style_profiles(limit: int = 10, db: AsyncSession = Depends(get_session)):
    """Retrieve recommended style profiles."""
    service = StyleProfileService(db)
    return await service.recommended_styles(limit=limit)

# 5. SSR03 - Recent Styles
@router.get("/recent", response_model=List[StyleProfileResponse])
async def get_recent_style_profiles(limit: int = 10, db: AsyncSession = Depends(get_session)):
    """Retrieve recently created style profiles ordered by date descending."""
    service = StyleProfileService(db)
    return await service.recent_styles(limit=limit)

# 12. SP14 - Preview Prompt Injection
@router.post("/preview", response_model=Dict[str, Any])
async def preview_prompt_injection(payload: PreviewInjectionRequest, db: AsyncSession = Depends(get_session)):
    """Preview formatted prompt using the selected style profile constraints."""
    service = StyleProfileService(db)
    return await service.preview_injection(payload.style_id, payload.prompt)

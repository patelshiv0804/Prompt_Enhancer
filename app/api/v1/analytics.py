from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.api.v1.deps import get_session
from app.services.style_profiles import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 6. SP15 - Usage Analytics
@router.get("/analytics", response_model=Dict[str, Any])
async def get_usage_analytics(db: AsyncSession = Depends(get_session)):
    """Retrieve aggregate usage analytics data for style profiles."""
    service = StyleProfileService(db)
    return await service.usage_analytics()

# 7. SSR05 - Usage History
@router.get("/history", response_model=List[Dict[str, Any]])
async def get_usage_history(db: AsyncSession = Depends(get_session)):
    """Retrieve history of style profiles usage."""
    service = StyleProfileService(db)
    return await service.usage_history()

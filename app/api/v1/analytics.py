from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import uuid
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.services.style_profiles import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 6. SP15 - Usage Analytics
@router.get("/analytics", response_model=Dict[str, Any])
async def get_usage_analytics(
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve aggregate usage analytics data for style profiles."""
    service = StyleProfileService(db, user_id)
    return await service.usage_analytics()

# 7. SSR05 - Usage History
@router.get("/history", response_model=List[Dict[str, Any]])
async def get_usage_history(
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve history of style profiles usage."""
    service = StyleProfileService(db, user_id)
    return await service.usage_history()

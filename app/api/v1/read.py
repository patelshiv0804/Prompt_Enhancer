from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from app.api.v1.deps import get_session
from app.core.security import get_current_user_id
from app.schemas import StyleProfileResponse
from app.services.style_profiles import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 2. SP10 - Get Style Types
@router.get("/types", response_model=List[str])
def get_style_types(user_id: uuid.UUID = Depends(get_current_user_id)):
    """Returns static list of allowed style types."""
    return StyleProfileService.get_types()

# 2. SP09 - Get Active Profiles
@router.get("/active", response_model=List[StyleProfileResponse])
async def get_active_style_profiles(
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve all currently active style profiles across types."""
    service = StyleProfileService(db, user_id)
    return await service.get_active_profiles()

# 8. SSR04 - Styles by type
@router.get("/type/{type}", response_model=List[StyleProfileResponse])
async def get_styles_by_type(
    type: str,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve style profiles filtered by a specific type category."""
    service = StyleProfileService(db, user_id)
    return await service.styles_by_type(type)

# 9. SP02 - List Styles (CRUD)
@router.get("", response_model=List[StyleProfileResponse])
async def list_style_profiles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve list of non-deleted style profiles."""
    service = StyleProfileService(db, user_id)
    return await service.list_styles(skip=skip, limit=limit)

# 14. SP03 - Get Style by ID (CRUD)
@router.get("/{id}", response_model=StyleProfileResponse)
async def get_style_profile(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve style profile details by ID."""
    service = StyleProfileService(db, user_id)
    return await service.get_style(id)

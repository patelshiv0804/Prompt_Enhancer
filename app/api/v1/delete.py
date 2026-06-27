from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
import uuid
from app.api.v1.deps import get_session
from app.schemas import DeletedStyleResponse, StyleProfileResponse
from app.services.style_profiles import StyleProfileService
router = APIRouter(prefix="/styles", tags=["Styles"])

# SP17 - Deleted Profiles
@router.get("/deleted", response_model=List[DeletedStyleResponse])
async def get_deleted_style_profiles(db: AsyncSession = Depends(get_session)):
    """Retrieve list of soft-deleted style profiles."""
    service = StyleProfileService(db)
    return await service.list_deleted_styles()

# SP16 - Restore Profile
@router.post("/{id}/restore", response_model=StyleProfileResponse)
async def restore_style_profile(id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    """Recover a soft-deleted style profile."""
    service = StyleProfileService(db)
    return await service.restore_style(id)

# SP18 - Permanent Delete
@router.delete("/{id}/permanent", response_model=Dict[str, str])
async def permanent_delete_style_profile(id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    """Permanently delete a style profile from the database."""
    service = StyleProfileService(db)
    return await service.permanent_delete(id)

# 16. SP05 - Delete Style (CRUD)
@router.delete("/{id}", response_model=StyleProfileResponse)
async def delete_style_profile(id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    """Soft delete a style profile."""
    service = StyleProfileService(db)
    return await service.delete_style(id)

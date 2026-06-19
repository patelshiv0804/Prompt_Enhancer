from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict
import uuid
from app.core.database import get_db
from app.modules.style_profiles.schemas import StyleProfileResponse, DeletedStyleResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# SP17 - Deleted Profiles
@router.get("/deleted", response_model=List[DeletedStyleResponse])
def get_deleted_style_profiles(db: Session = Depends(get_db)):
    """Retrieve list of soft-deleted style profiles."""
    service = StyleProfileService(db)
    return service.list_deleted_styles()

# SP16 - Restore Profile
@router.post("/{id}/restore", response_model=StyleProfileResponse)
def restore_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Recover a soft-deleted style profile."""
    service = StyleProfileService(db)
    return service.restore_style(id)

# SP18 - Permanent Delete
@router.delete("/{id}/permanent", response_model=Dict[str, str])
def permanent_delete_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Permanently delete a style profile from the database."""
    service = StyleProfileService(db)
    return service.permanent_delete(id)

# 16. SP05 - Delete Style (CRUD)
@router.delete("/{id}", response_model=StyleProfileResponse)
def delete_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Soft delete a style profile."""
    service = StyleProfileService(db)
    return service.delete_style(id)

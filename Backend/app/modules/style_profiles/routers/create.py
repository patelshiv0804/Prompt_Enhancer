from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
import uuid
from app.core.database import get_db
from app.modules.style_profiles.schemas import CreateStyleProfileRequest, StyleProfileResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 10. SP01 - Create Style (CRUD)
@router.post("", response_model=StyleProfileResponse, status_code=status.HTTP_201_CREATED)
def create_style_profile(payload: CreateStyleProfileRequest, db: Session = Depends(get_db)):
    """Create a new style profile."""
    service = StyleProfileService(db)
    return service.create_style(payload)

# 19. SP08 - Duplicate Style
@router.post("/{id}/duplicate", response_model=StyleProfileResponse)
def duplicate_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Duplicate a style profile, deep copying parameters with a new Copy suffix name."""
    service = StyleProfileService(db)
    return service.duplicate_style(id)

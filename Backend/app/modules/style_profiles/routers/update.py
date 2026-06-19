from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from app.core.database import get_db
from app.modules.style_profiles.schemas import UpdateStyleProfileRequest, StyleProfileResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 15. SP04 - Update Style (CRUD)
@router.patch("/{id}", response_model=StyleProfileResponse)
def update_style_profile(id: uuid.UUID, payload: UpdateStyleProfileRequest, db: Session = Depends(get_db)):
    """Update fields of an existing style profile."""
    service = StyleProfileService(db)
    return service.update_style(id, payload)

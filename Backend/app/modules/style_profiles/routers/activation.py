from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from app.core.database import get_db
from app.modules.style_profiles.schemas import StyleProfileResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 17. SP06 - Activate Style
@router.patch("/{id}/activate", response_model=StyleProfileResponse)
def activate_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Activate a style profile (automatically deactivating other profiles of the same type)."""
    service = StyleProfileService(db)
    return service.activate_style(id)

# 18. SP07 - Deactivate Style
@router.patch("/{id}/deactivate", response_model=StyleProfileResponse)
def deactivate_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Deactivate a style profile."""
    service = StyleProfileService(db)
    return service.deactivate_style(id)

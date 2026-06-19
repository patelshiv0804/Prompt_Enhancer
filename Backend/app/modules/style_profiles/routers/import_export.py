from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
import uuid
from app.core.database import get_db
from app.modules.style_profiles.schemas import ImportStyleRequest, StyleProfileResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 11. SP12 - Import Style
@router.post("/import", response_model=StyleProfileResponse)
def import_style_profile(payload: ImportStyleRequest, db: Session = Depends(get_db)):
    """Import style profile using dictionary JSON representation."""
    service = StyleProfileService(db)
    return service.import_style(payload.json_data)

# 20. SP13 - Export Style
@router.get("/{id}/export", response_model=Dict[str, Any])
def export_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Export style profile params as JSON structure."""
    service = StyleProfileService(db)
    return service.export_style(id)

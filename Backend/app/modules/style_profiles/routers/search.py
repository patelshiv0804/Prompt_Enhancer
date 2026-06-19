from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.modules.style_profiles.schemas import SearchStyleRequest, StyleProfileResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 13. SSR01 - Search Styles
@router.post("/search", response_model=List[StyleProfileResponse])
def search_style_profiles(payload: SearchStyleRequest, db: Session = Depends(get_db)):
    """Search style profiles by name matching query, with optional type filter."""
    service = StyleProfileService(db)
    return service.search_styles(payload.query, payload.type)

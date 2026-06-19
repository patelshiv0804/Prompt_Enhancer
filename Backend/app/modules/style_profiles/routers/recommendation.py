from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.core.database import get_db
from app.modules.style_profiles.schemas import PreviewInjectionRequest, StyleProfileResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 3. SP11 - Get Popular Styles
@router.get("/popular", response_model=List[StyleProfileResponse])
def get_popular_style_profiles(limit: int = 10, db: Session = Depends(get_db)):
    """Retrieve popular style profiles ordered by usage count descending."""
    service = StyleProfileService(db)
    return service.get_popular_styles(limit=limit)

# 4. SSR02 - Recommended Styles
@router.get("/recommended", response_model=List[StyleProfileResponse])
def get_recommended_style_profiles(limit: int = 10, db: Session = Depends(get_db)):
    """Retrieve recommended style profiles."""
    service = StyleProfileService(db)
    return service.recommended_styles(limit=limit)

# 5. SSR03 - Recent Styles
@router.get("/recent", response_model=List[StyleProfileResponse])
def get_recent_style_profiles(limit: int = 10, db: Session = Depends(get_db)):
    """Retrieve recently created style profiles ordered by date descending."""
    service = StyleProfileService(db)
    return service.recent_styles(limit=limit)

# 12. SP14 - Preview Prompt Injection
@router.post("/preview", response_model=Dict[str, Any])
def preview_prompt_injection(payload: PreviewInjectionRequest, db: Session = Depends(get_db)):
    """Preview formatted prompt using the selected style profile constraints."""
    service = StyleProfileService(db)
    return service.preview_injection(payload.style_id, payload.prompt)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid
from app.core.database import get_db
from app.modules.style_profiles.schemas import StyleProfileResponse
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 2. SP10 - Get Style Types
@router.get("/types", response_model=List[str])
def get_style_types():
    """Returns static list of allowed style types."""
    return StyleProfileService.get_types()

# 2. SP09 - Get Active Profiles
@router.get("/active", response_model=List[StyleProfileResponse])
def get_active_style_profiles(db: Session = Depends(get_db)):
    """Retrieve all currently active style profiles across types."""
    service = StyleProfileService(db)
    return service.get_active_profiles()

# 8. SSR04 - Styles by type
@router.get("/type/{type}", response_model=List[StyleProfileResponse])
def get_styles_by_type(type: str, db: Session = Depends(get_db)):
    """Retrieve style profiles filtered by a specific type category."""
    service = StyleProfileService(db)
    return service.styles_by_type(type)

# 9. SP02 - List Styles (CRUD)
@router.get("", response_model=List[StyleProfileResponse])
def list_style_profiles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve list of non-deleted style profiles."""
    service = StyleProfileService(db)
    return service.list_styles(skip=skip, limit=limit)

# 14. SP03 - Get Style by ID (CRUD)
@router.get("/{id}", response_model=StyleProfileResponse)
def get_style_profile(id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve style profile details by ID."""
    service = StyleProfileService(db)
    return service.get_style(id)

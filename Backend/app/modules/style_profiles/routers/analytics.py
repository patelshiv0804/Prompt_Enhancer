from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.core.database import get_db
from app.modules.style_profiles.service import StyleProfileService

router = APIRouter(prefix="/styles", tags=["Styles"])

# 6. SP15 - Usage Analytics
@router.get("/analytics", response_model=Dict[str, Any])
def get_usage_analytics(db: Session = Depends(get_db)):
    """Retrieve aggregate usage analytics data for style profiles."""
    service = StyleProfileService(db)
    return service.usage_analytics()

# 7. SSR05 - Usage History
@router.get("/history", response_model=List[Dict[str, Any]])
def get_usage_history(db: Session = Depends(get_db)):
    """Retrieve history of style profiles usage."""
    service = StyleProfileService(db)
    return service.usage_history()

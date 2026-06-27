from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Union

class CreateStyleProfileRequest(BaseModel):
    name: str = Field(..., max_length=100)
    type: str = Field(..., description="Valid types: 'character', 'cinematic', 'art_style', 'environment', 'brand_voice'")
    attributes: Dict[str, Any] = Field(..., description="Attributes dictionary for the style profile")
    injection_template: Optional[str] = None
    thumbnail_url: Optional[str] = None

class UpdateStyleProfileRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    type: Optional[str] = Field(None, description="Valid types: 'character', 'cinematic', 'art_style', 'environment', 'brand_voice'")
    attributes: Optional[Dict[str, Any]] = None
    injection_template: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_active: Optional[bool] = None

class PreviewInjectionRequest(BaseModel):
    style_id: uuid.UUID
    prompt: str

class ImportStyleRequest(BaseModel):
    json_data: Union[Dict[str, Any], str] = Field(..., description="JSON serialized string or raw dictionary data to import")

class SearchStyleRequest(BaseModel):
    query: str
    type: Optional[str] = None

class StyleProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    attributes: Dict[str, Any]
    thumbnail_url: Optional[str]
    is_active: bool
    use_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeletedStyleResponse(BaseModel):
    id: uuid.UUID
    name: str
    deleted_at: datetime

    class Config:
        from_attributes = True


from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class ThemeEnum(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"

class ModelEnum(str, Enum):
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    GROK = "grok"
    MIDJOURNEY = "midjourney"
    VEO = "veo"
    PERPLEXITY = "perplexity"

class ModeEnum(str, Enum):
    GENERAL = "general"
    CREATIVE = "creative"
    TECHNICAL = "technical"
    MARKETING = "marketing"
    CODING = "coding"
    CODE = "code"  # legacy alias

class ThemeUpdate(BaseModel):
    theme: str

class DefaultModelUpdate(BaseModel):
    default_model: str

class DefaultModeUpdate(BaseModel):
    default_mode: str

class BooleanToggle(BaseModel):
    enabled: bool

class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    default_mode: Optional[str] = None
    default_model: Optional[str] = None
    show_diff_by_default: Optional[bool] = None
    auto_detect_intent: Optional[str | bool] = None

class SettingsResponse(BaseModel):
    id: UUID
    user_id: UUID
    theme: str
    default_mode: str
    default_model: str
    show_diff_by_default: bool
    auto_detect_intent: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

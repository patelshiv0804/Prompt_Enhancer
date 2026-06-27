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

class ModeEnum(str, Enum):
    GENERAL = "general"
    CODE = "code"
    CREATIVE = "creative"

class ThemeUpdate(BaseModel):
    theme: ThemeEnum

class DefaultModelUpdate(BaseModel):
    default_model: ModelEnum

class DefaultModeUpdate(BaseModel):
    default_mode: ModeEnum

class BooleanToggle(BaseModel):
    enabled: bool

class SettingsUpdate(BaseModel):
    theme: Optional[ThemeEnum] = None
    default_mode: Optional[ModeEnum] = None
    default_model: Optional[ModelEnum] = None
    show_diff_by_default: Optional[bool] = None
    auto_detect_intent: Optional[bool] = None

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

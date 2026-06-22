"""
Settings schemas — Pydantic models for user settings API (Module B).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import DefaultMode, DefaultModel, Theme


class SettingsResponse(BaseModel):
    """Full settings response."""
    id: UUID
    user_id: UUID
    theme: str
    default_mode: str
    default_model: str
    show_diff_by_default: bool
    auto_detect_intent: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    """Bulk update for multiple settings at once."""
    theme: Optional[str] = None
    default_mode: Optional[str] = None
    default_model: Optional[str] = None
    show_diff_by_default: Optional[bool] = None
    auto_detect_intent: Optional[bool] = None


class ThemeUpdate(BaseModel):
    """Update theme setting."""
    theme: Theme


class DefaultModelUpdate(BaseModel):
    """Update default AI model."""
    default_model: DefaultModel


class DefaultModeUpdate(BaseModel):
    """Update default prompt mode."""
    default_mode: DefaultMode


class BooleanToggle(BaseModel):
    """Generic boolean toggle for features."""
    enabled: bool

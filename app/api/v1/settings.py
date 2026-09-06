"""
Settings router — FastAPI endpoints for user settings management (Module B).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_session as get_db
from app.core.security import get_current_user_id
from app.schemas.settings import (
    BooleanToggle,
    DefaultModeUpdate,
    DefaultModelUpdate,
    SettingsResponse,
    SettingsUpdate,
    ThemeUpdate,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["User Settings"])


# ── S01: Get user settings ───────────────────────────────
@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get user settings",
)
async def get_settings(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch all saved user settings."""
    service = SettingsService(db)
    return await service.get_settings(user_id)


# ── S02: Update settings (bulk) ──────────────────────────
@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update settings",
)
async def update_settings(
    body: SettingsUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple settings at once."""
    service = SettingsService(db)
    return await service.update_settings(
        user_id,
        theme=body.theme,
        default_mode=body.default_mode,
        default_model=body.default_model,
        show_diff_by_default=body.show_diff_by_default,
        auto_detect_intent=body.auto_detect_intent if isinstance(body.auto_detect_intent, bool) else None,
    )


# ── S04: Update theme ───────────────────────────────────
@router.patch(
    "/theme",
    response_model=SettingsResponse,
    summary="Update theme",
)
async def update_theme(
    body: ThemeUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Change the application theme (light, dark, system)."""
    service = SettingsService(db)
    return await service.update_theme(user_id, body.theme)


# ── S05: Change default AI model ─────────────────────────
@router.patch(
    "/default-model",
    response_model=SettingsResponse,
    summary="Change default AI model",
)
async def update_default_model(
    body: DefaultModelUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Set the preferred AI model as default."""
    service = SettingsService(db)
    return await service.update_default_model(user_id, body.default_model)


# ── S06: Change default prompt mode ──────────────────────
@router.patch(
    "/default-mode",
    response_model=SettingsResponse,
    summary="Change default prompt mode",
)
async def update_default_mode(
    body: DefaultModeUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Set the preferred prompt mode as default."""
    service = SettingsService(db)
    return await service.update_default_mode(user_id, body.default_mode)


# ── S07: Enable / Disable intent detection ───────────────
@router.patch(
    "/intent-detection",
    response_model=SettingsResponse,
    summary="Toggle intent detection",
)
async def toggle_intent_detection(
    body: BooleanToggle,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable automatic intent detection on prompt input."""
    service = SettingsService(db)
    return await service.toggle_intent_detection(user_id, body.enabled)


# ── S08: Enable / Disable diff view ─────────────────────
@router.patch(
    "/diff-view",
    response_model=SettingsResponse,
    summary="Toggle diff view",
)
async def toggle_diff_view(
    body: BooleanToggle,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable showing changes between original and optimized prompts."""
    service = SettingsService(db)
    return await service.toggle_diff_view(user_id, body.enabled)

import json
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any, Union
import uuid
from datetime import datetime
from fastapi import HTTPException, status
from app.repositories.style_profiles import StyleProfileRepository
from app.schemas.style_profiles import CreateStyleProfileRequest, UpdateStyleProfileRequest
from app.db.models import StyleProfile

VALID_TYPES = ["character", "cinematic", "art_style", "environment", "brand_voice"]

class StyleProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _validate_type(self, type_str: Optional[str]) -> None:
        if type_str is not None and type_str not in VALID_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type '{type_str}'. Allowed types: {VALID_TYPES}"
            )

    async def create_style(self, request: CreateStyleProfileRequest, user_id: Optional[uuid.UUID] = None) -> StyleProfile:
        """SP01 - Create a new style profile."""
        self._validate_type(request.type)
        return await StyleProfileRepository.create_style(self.db, request, user_id)

    async def list_styles(self, skip: int = 0, limit: int = 100) -> List[StyleProfile]:
        """SP02 - List all non-deleted style profiles."""
        return await StyleProfileRepository.get_all_styles(self.db, skip=skip, limit=limit)

    async def get_style(self, id: uuid.UUID) -> StyleProfile:
        """SP03 - Retrieve a single style profile by ID."""
        style = await StyleProfileRepository.get_style_by_id(self.db, id)
        if not style:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Style profile with ID '{id}' not found."
            )
        return style

    async def update_style(self, id: uuid.UUID, request: UpdateStyleProfileRequest) -> StyleProfile:
        """SP04 - Update an existing style profile."""
        style = await self.get_style(id)
        if request.type is not None:
            self._validate_type(request.type)
        return await StyleProfileRepository.update_style(self.db, style, request)

    async def delete_style(self, id: uuid.UUID) -> StyleProfile:
        """SP05 - Soft delete a style profile."""
        style = await self.get_style(id)
        return await StyleProfileRepository.soft_delete_style(self.db, style)

    async def activate_style(self, id: uuid.UUID) -> StyleProfile:
        """SP06 - Activate style profile. Allows user to activate multiple style profiles independently."""
        style = await self.get_style(id)
        return await StyleProfileRepository.activate_style(self.db, style)

    async def deactivate_style(self, id: uuid.UUID) -> StyleProfile:
        """SP07 - Deactivate a style profile."""
        style = await self.get_style(id)
        return await StyleProfileRepository.deactivate_style(self.db, style)

    async def duplicate_style(self, id: uuid.UUID) -> StyleProfile:
        """SP08 - Duplicate a style profile."""
        style = await self.get_style(id)
        return await StyleProfileRepository.duplicate_style(self.db, style)

    async def get_active_profiles(self) -> List[StyleProfile]:
        """SP09 - Retrieve all active style profiles."""
        return await StyleProfileRepository.get_active_styles(self.db)

    @staticmethod
    def get_types() -> List[str]:
        """SP10 - Returns list of valid types."""
        return VALID_TYPES

    async def get_popular_styles(self, limit: int = 10) -> List[StyleProfile]:
        """SP11 - Retrieve popular style profiles sorted by use count."""
        return await StyleProfileRepository.get_popular_styles(self.db, limit=limit)

    async def import_style(self, json_data: Union[dict, str]) -> StyleProfile:
        """SP12 - Import style profile from JSON data."""
        try:
            return await StyleProfileRepository.import_style(self.db, json_data)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    async def export_style(self, id: uuid.UUID) -> dict:
        """SP13 - Export style profile parameters as dictionary."""
        style = await self.get_style(id)
        return await StyleProfileRepository.export_style(self.db, style)

    async def preview_injection(self, style_id: uuid.UUID, prompt: str) -> dict:
        """SP14 - Preview injecting style attributes into prompt using the injection template."""
        style = await self.get_style(style_id)
        
        # Increment usage count for preview
        await StyleProfileRepository.increment_use_count(self.db, style)
        
        template = style.injection_template
        attributes = style.attributes or {}
        
        injected_text = ""
        if template:
            try:
                injected_text = template.format(**attributes)
            except Exception:
                injected_text = template
                for k, v in attributes.items():
                    injected_text = injected_text.replace(f"{{{k}}}", str(v))
        else:
            lines = []
            for k, v in attributes.items():
                if isinstance(v, list):
                    val_str = ", ".join(map(str, v))
                elif isinstance(v, dict):
                    val_str = json.dumps(v)
                else:
                    val_str = str(v)
                lines.append(f"{k.capitalize()}: {val_str}")
            injected_text = "\n".join(lines)
            
        # Combine prompt with styles
        full_injected_prompt = f"{prompt}\n\n{injected_text}".strip()
        
        return {
            "prompt": prompt,
            "injected_prompt": full_injected_prompt
        }

    async def usage_analytics(self) -> dict:
        """SP15 - Retrieve overall usage analytics for style profiles."""
        return await StyleProfileRepository.get_usage_analytics(self.db)

    async def search_styles(self, query: str, type: Optional[str] = None) -> List[StyleProfile]:
        """SSR01 - Search for style profiles by name matching query, with optional type filter."""
        if type is not None:
            self._validate_type(type)
        return await StyleProfileRepository.search_styles(self.db, query, type)

    async def recommended_styles(self, limit: int = 10) -> List[StyleProfile]:
        """SSR02 - Retrieve recommended style profiles."""
        return await StyleProfileRepository.get_recommended_styles(self.db, limit=limit)

    async def recent_styles(self, limit: int = 10) -> List[StyleProfile]:
        """SSR03 - Retrieve recent style profiles sorted by created date."""
        return await StyleProfileRepository.get_recent_styles(self.db, limit=limit)

    async def styles_by_type(self, type_str: str) -> List[StyleProfile]:
        """SSR04 - Retrieve style profiles filtered by type."""
        self._validate_type(type_str)
        return await StyleProfileRepository.get_styles_by_type(self.db, type_str)

    async def usage_history(self) -> List[dict]:
        """SSR05 - Retrieve usage history for style profiles."""
        return await StyleProfileRepository.get_usage_history(self.db)

    async def restore_style(self, id: uuid.UUID) -> StyleProfile:
        """SP16 - Recover a soft-deleted style profile."""
        style = await StyleProfileRepository.get_style_by_id_raw(self.db, id)
        if not style:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Style profile with ID '{id}' not found."
            )
        return await StyleProfileRepository.restore_style(self.db, style)

    async def list_deleted_styles(self) -> List[StyleProfile]:
        """SP17 - Retrieve list of soft-deleted style profiles."""
        return await StyleProfileRepository.get_deleted_styles(self.db)

    async def permanent_delete(self, id: uuid.UUID) -> dict:
        """SP18 - Permanently delete a style profile."""
        style = await StyleProfileRepository.get_style_by_id_raw(self.db, id)
        if not style:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Style profile with ID '{id}' not found."
            )
        await StyleProfileRepository.permanent_delete_style(self.db, style)
        return {"detail": f"Style profile '{style.name}' permanently deleted."}

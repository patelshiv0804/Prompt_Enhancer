import os
import uuid
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, UserSettings, Prompt, Template
from app.repositories.user import ProfileRepository, SettingsRepository
from app.utils.validators import is_valid_avatar_extension, sanitize_display_name
from app.core.constants import MAX_AVATAR_FILE_SIZE

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ProfileRepository(db)
        self.settings_repository = SettingsRepository(db)

    async def get_profile(self, user_id: UUID) -> Profile:
        profile = await self.repository.get_by_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile

    async def create_profile(
        self,
        user_id: UUID,
        email: str,
        display_name: Optional[str] = None,
    ) -> Profile:
        # Create profile
        profile = await self.repository.create(
            user_id=user_id,
            email=email,
            display_name=display_name,
        )
        # Create default settings
        await self.settings_repository.create_defaults(user_id)
        return profile

    async def update_profile(
        self,
        user_id: UUID,
        display_name: Optional[str] = None,
        avatar_file: Optional[UploadFile] = None,
    ) -> Profile:
        kwargs = {}
        if display_name is not None:
            kwargs["display_name"] = sanitize_display_name(display_name)
            kwargs["full_name"] = sanitize_display_name(display_name)

        if avatar_file is not None:
            filename = avatar_file.filename or ""
            if not is_valid_avatar_extension(filename):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid avatar file extension. Allowed: jpg, jpeg, png, gif, webp"
                )
            
            # Read size
            content = await avatar_file.read()
            if len(content) > MAX_AVATAR_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail="Avatar file size exceeds the 5MB limit."
                )

            # Ensure upload directory exists
            upload_dir = os.path.join("uploads", "avatars")
            os.makedirs(upload_dir, exist_ok=True)

            # Generate unique filename
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            with open(file_path, "wb") as f:
                f.write(content)

            kwargs["avatar_url"] = f"/uploads/avatars/{unique_filename}"

        profile = await self.repository.update(user_id, **kwargs)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        await self.db.commit()
        return profile

    async def soft_delete(self, user_id: UUID) -> Profile:
        profile = await self.repository.soft_delete(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        await self.db.commit()
        return profile

    async def restore_account(self, email: str) -> Profile:
        profile = await self.repository.get_by_email(email)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        restored = await self.repository.restore(profile.id)
        await self.db.commit()
        return restored

    async def get_plan(self, user_id: UUID) -> dict:
        profile = await self.get_profile(user_id)
        
        # Mock limits based on plan
        limits = {
            "max_prompts": 100 if profile.plan == "pro" else 20,
            "max_templates": 50 if profile.plan == "pro" else 5,
        }
        return {
            "plan": profile.plan,
            "limits": limits
        }

    async def update_onboarding(self, user_id: UUID, onboarding_completed: bool) -> Profile:
        profile = await self.repository.update(user_id, onboarding_completed=onboarding_completed)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        await self.db.commit()
        return profile

    async def get_stats(self, user_id: UUID) -> dict:
        profile = await self.get_profile(user_id)
        
        # Query total prompts count
        prompt_query = select(func.count()).select_from(Prompt).where(Prompt.user_id == user_id)
        prompt_res = await self.db.execute(prompt_query)
        total_prompts = prompt_res.scalar() or 0

        # Query total templates count (global)
        template_query = select(func.count()).select_from(Template)
        template_res = await self.db.execute(template_query)
        total_templates = template_res.scalar() or 0

        return {
            "total_prompts": total_prompts,
            "total_templates": total_templates,
            "total_chains": 0,
            "total_optimizations": total_prompts, # mock
            "plan": profile.plan,
            "member_since": profile.created_at
        }

    async def get_activity(self, user_id: UUID) -> dict:
        profile = await self.get_profile(user_id)
        
        # Return mock list of activities for now
        activities = [
            {
                "action": "profile_creation",
                "description": "Account created successfully.",
                "timestamp": profile.created_at
            }
        ]
        return {
            "activities": activities,
            "total_count": len(activities)
        }

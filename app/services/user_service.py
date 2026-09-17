import os
import uuid
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, UserSettings, Prompt, Template, PromptVersion
from app.repositories.user import ProfileRepository, SettingsRepository
from app.services.badge_service import BadgeService
from app.utils.validators import is_valid_avatar_extension, sanitize_display_name
from app.core.constants import MAX_AVATAR_FILE_SIZE

# Content types accepted for avatar uploads (VULN-011).
ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _is_supported_image(content: bytes) -> bool:
    """Confirm the actual bytes are a supported image (VULN-011).

    The filename extension and the client-declared content type can both be
    spoofed, so we sniff the leading magic bytes before persisting the file.
    """
    if len(content) < 12:
        return False
    # JPEG: FF D8 FF
    if content[:3] == b"\xFF\xD8\xFF":
        return True
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    # GIF: "GIF87a" / "GIF89a"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return True
    # WEBP: "RIFF" <4 bytes> "WEBP"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return True
    return False


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
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> Profile:
        # Create profile
        profile = await self.repository.create(
            user_id=user_id,
            email=email,
            display_name=display_name,
            full_name=full_name,
            avatar_url=avatar_url,
        )
        # Create default settings
        await self.settings_repository.create_defaults(user_id)
        return profile

    async def update_profile(
        self,
        user_id: UUID,
        display_name: Optional[str] = None,
        role: Optional[str] = None,
        avatar_file: Optional[UploadFile] = None,
    ) -> Profile:
        kwargs = {}
        if display_name is not None:
            kwargs["display_name"] = sanitize_display_name(display_name)
            kwargs["full_name"] = sanitize_display_name(display_name)
        if role is not None:
            kwargs["role"] = role.lower()

        if avatar_file is not None:
            filename = avatar_file.filename or ""
            if not is_valid_avatar_extension(filename):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid avatar file extension. Allowed: jpg, jpeg, png, gif, webp"
                )

            # Reject anything not declared as an allowed image type (VULN-011).
            if avatar_file.content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid avatar content type. Allowed: JPEG, PNG, GIF, WEBP"
                )

            # Read size
            content = await avatar_file.read()
            if len(content) > MAX_AVATAR_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail="Avatar file size exceeds the 5MB limit."
                )

            # Verify the real bytes are an image; extension/content-type alone
            # are spoofable, so this blocks disguised payloads (VULN-011).
            if not _is_supported_image(content):
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file is not a valid image."
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
        from datetime import date, timedelta

        # Query all non-deleted prompts for user
        prompt_query = select(Prompt).where(Prompt.user_id == user_id).where(Prompt.deleted_at == None)
        prompt_res = await self.db.execute(prompt_query)
        prompts = list(prompt_res.scalars().all())
        total_prompts = len(prompts)

        # Compute average enhanced score
        scored = [
            p.new_analysis["overall_score"]
            for p in prompts
            if p.new_analysis and isinstance(p.new_analysis, dict) and "overall_score" in p.new_analysis
        ]
        average_score = round(sum(scored) / len(scored), 1) if scored else 0.0

        # Compute activity_calendar, streak_days, and longest_streak
        today = date.today()
        streak = 0
        longest_streak = 0
        activity_calendar: dict[str, int] = {}
        for p in prompts:
            if p.created_at:
                d_str = p.created_at.strftime("%Y-%m-%d")
                activity_calendar[d_str] = activity_calendar.get(d_str, 0) + 1

        prompt_dates_asc = sorted(
            set(p.created_at.date() for p in prompts if p.created_at)
        )
        total_active_days = len(prompt_dates_asc)

        # Compute longest consecutive streak
        current_run = 0
        prev_d = None
        for d in prompt_dates_asc:
            if prev_d is None or d == prev_d + timedelta(days=1):
                current_run += 1
            else:
                current_run = 1
            if current_run > longest_streak:
                longest_streak = current_run
            prev_d = d

        # Compute current active streak (valid if active today or yesterday)
        if prompt_dates_asc:
            yesterday = today - timedelta(days=1)
            rev_dates = list(reversed(prompt_dates_asc))
            if rev_dates[0] == today or rev_dates[0] == yesterday:
                curr = rev_dates[0]
                streak = 1
                for next_date in rev_dates[1:]:
                    if next_date == curr - timedelta(days=1):
                        streak += 1
                        curr = next_date
                    else:
                        break

        # Compute 7-day frequency sparkline: [today-6, today-5, ..., today]
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        day_counts = {d: 0 for d in last_7_days}
        for p in prompts:
            if p.created_at:
                p_date = p.created_at.date()
                if p_date in day_counts:
                    day_counts[p_date] += 1
        frequency_7d = [day_counts[d] for d in last_7_days]

        # Extract user raw prompt scores (evaluates raw prompt score before enhancement)
        user_raw_scores: list[float] = []
        for p in prompts:
            score = None
            if p.old_analysis and isinstance(p.old_analysis, dict):
                val = p.old_analysis.get("overall_score")
                if isinstance(val, (int, float)):
                    score = float(val)
            if score is None and p.new_analysis and isinstance(p.new_analysis, dict):
                val = p.new_analysis.get("before_score")
                if isinstance(val, (int, float)):
                    score = float(val)
            if score is not None:
                user_raw_scores.append(score)
        user_max_score = max(user_raw_scores) if user_raw_scores else 0.0

        # Query total templates (global)
        template_query = select(func.count()).select_from(Template)
        template_res = await self.db.execute(template_query)
        total_templates = template_res.scalar() or 0

        # Query user's custom templates count
        user_tpl_stmt = select(func.count()).select_from(Template).where(Template.user_id == user_id)
        user_tpl_res = await self.db.execute(user_tpl_stmt)
        custom_templates = user_tpl_res.scalar() or 0

        # Inbuilt templates used
        inbuilt_templates_used = sum(1 for p in prompts if p.template_id is not None)

        # Max versions for a single prompt
        max_versions = 0
        if prompts:
            prompt_ids = [p.id for p in prompts]
            ver_stmt = (
                select(PromptVersion.prompt_id, func.count(PromptVersion.id))
                .where(PromptVersion.prompt_id.in_(prompt_ids))
                .group_by(PromptVersion.prompt_id)
            )
            ver_res = await self.db.execute(ver_stmt)
            counts = [row[1] for row in ver_res.all()]
            max_versions = max(counts) if counts else 1

        # Unique AI models targeted
        models_set = set()
        for p in prompts:
            if p.target_model and p.target_model.strip():
                models_set.add(p.target_model.strip().lower())
        unique_models = len(models_set)

        # Unique styles / modes used
        modes_set = set()
        tpl_ids = [p.template_id for p in prompts if p.template_id]
        if tpl_ids:
            mode_stmt = select(Template.mode).where(Template.id.in_(tpl_ids))
            mode_res = await self.db.execute(mode_stmt)
            for m in mode_res.scalars().all():
                if m and m.strip():
                    modes_set.add(m.strip().lower())
        for p in prompts:
            if p.tool_recommendations and isinstance(p.tool_recommendations, dict):
                m = p.tool_recommendations.get("mode")
                if m and str(m).strip():
                    modes_set.add(str(m).strip().lower())
        unique_modes = len(modes_set)

        # Evaluate all 29 gamified badges
        badges = BadgeService.evaluate_badges(
            total_prompts=total_prompts,
            user_raw_scores=user_raw_scores,
            streak_days=streak,
            inbuilt_templates_used=inbuilt_templates_used,
            custom_templates=custom_templates,
            max_versions=max_versions,
            unique_models=unique_models,
            unique_modes=unique_modes,
        )
        unlocked_count = sum(1 for b in badges if b["unlocked"])

        return {
            "total_prompts": total_prompts,
            "total_templates": total_templates,
            "total_chains": 0,
            "total_optimizations": total_prompts,
            "average_score": average_score,
            "streak_days": streak,
            "longest_streak": longest_streak,
            "total_active_days": total_active_days,
            "activity_calendar": activity_calendar,
            "plan": profile.plan,
            "member_since": profile.created_at,
            "frequency_7d": frequency_7d,
            "user_max_score": user_max_score,
            "unlocked_badge_count": unlocked_count,
            "total_badge_count": len(badges),
            "badges": badges,
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

    async def get_user_prompts(self, user_id: UUID) -> list[Prompt]:
        await self.get_profile(user_id)
        query = select(Prompt).where(Prompt.user_id == user_id)
        res = await self.db.execute(query)
        return list(res.scalars().all())

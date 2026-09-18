"""Activity & Achievement Ledger Service.

Provides immutable persistence for user daily enhancement activity (heatmaps & streaks)
and permanent badge unlocks. Decouples telemetry and achievements from Vault/Prompt
deletions.
"""
from datetime import date, datetime, timezone
import logging
from typing import Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Prompt, UserDailyActivity, UserUnlockedBadge

logger = logging.getLogger("promptiq.activity_service")


class ActivityService:
    @staticmethod
    async def record_daily_activity(
        session: AsyncSession,
        user_id: UUID | str,
        activity_date: Optional[date] = None,
        score: Optional[float] = None,
    ) -> None:
        """Upsert daily activity count for user on the given date (defaults to today)."""
        uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id
        target_date = activity_date or date.today()

        stmt = (
            insert(UserDailyActivity)
            .values(
                user_id=uid,
                activity_date=target_date,
                count=1,
                highest_score=score,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_user_daily_activities_user_date",
                set_={
                    "count": UserDailyActivity.count + 1,
                    "highest_score": func.coalesce(
                        func.greatest(UserDailyActivity.highest_score, score),
                        score,
                        UserDailyActivity.highest_score,
                    ),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
        )
        await session.execute(stmt)

    @staticmethod
    async def get_daily_activities(
        session: AsyncSession,
        user_id: UUID | str,
    ) -> List[UserDailyActivity]:
        """Fetch all daily activity ledger entries for user in chronological order."""
        uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id
        query = (
            select(UserDailyActivity)
            .where(UserDailyActivity.user_id == uid)
            .order_by(UserDailyActivity.activity_date.asc())
        )
        res = await session.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_unlocked_badges(
        session: AsyncSession,
        user_id: UUID | str,
    ) -> Dict[str, datetime]:
        """Returns a mapping of {badge_id: unlocked_at} for all permanently earned badges."""
        uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id
        query = select(UserUnlockedBadge).where(UserUnlockedBadge.user_id == uid)
        res = await session.execute(query)
        return {row.badge_id: row.unlocked_at for row in res.scalars().all()}

    @staticmethod
    async def persist_newly_unlocked_badges(
        session: AsyncSession,
        user_id: UUID | str,
        badge_ids: List[str],
    ) -> None:
        """Atomically persist any newly earned badges to the permanent unlock ledger."""
        if not badge_ids:
            return
        uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id
        now = datetime.now(timezone.utc)
        for badge_id in badge_ids:
            stmt = (
                insert(UserUnlockedBadge)
                .values(
                    user_id=uid,
                    badge_id=badge_id,
                    unlocked_at=now,
                )
                .on_conflict_do_nothing(
                    constraint="uq_user_unlocked_badges_user_badge"
                )
            )
            await session.execute(stmt)

    @staticmethod
    async def ensure_user_backfilled(
        session: AsyncSession,
        user_id: UUID | str,
    ) -> None:
        """Self-healing backfill: if user has no daily activity records yet,

        populates them from historical prompt creation dates so existing users
        never lose their historical heatmap, streak, or badges.
        """
        uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id
        # Check if user already has activity records
        count_stmt = (
            select(func.count(UserDailyActivity.id))
            .where(UserDailyActivity.user_id == uid)
        )
        res = await session.execute(count_stmt)
        existing_count = res.scalar() or 0
        if existing_count > 0:
            return

        # Query all existing prompts created by this user
        prompt_stmt = (
            select(Prompt.created_at, Prompt.new_analysis, Prompt.old_analysis)
            .where(Prompt.user_id == uid)
        )
        prompt_res = await session.execute(prompt_stmt)
        prompts = prompt_res.all()
        if not prompts:
            return

        logger.info("Backfilling daily activity ledger for user %s (%d prompts found)", uid, len(prompts))
        date_counts: Dict[date, int] = {}
        date_scores: Dict[date, Optional[float]] = {}

        for row in prompts:
            p_created = row[0]
            if not p_created:
                continue
            d = p_created.date()
            date_counts[d] = date_counts.get(d, 0) + 1

            # Extract score if available
            score = None
            old_an = row[2]
            new_an = row[1]
            if old_an and isinstance(old_an, dict):
                val = old_an.get("overall_score")
                if isinstance(val, (int, float)):
                    score = float(val)
            if score is None and new_an and isinstance(new_an, dict):
                val = new_an.get("before_score") or new_an.get("overall_score")
                if isinstance(val, (int, float)):
                    score = float(val)
            if score is not None:
                curr_max = date_scores.get(d)
                date_scores[d] = max(curr_max, score) if curr_max is not None else score

        # Batch insert into user_daily_activities
        now = datetime.now(timezone.utc)
        for act_date, count in date_counts.items():
            max_sc = date_scores.get(act_date)
            stmt = (
                insert(UserDailyActivity)
                .values(
                    user_id=uid,
                    activity_date=act_date,
                    count=count,
                    highest_score=max_sc,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(
                    constraint="uq_user_daily_activities_user_date"
                )
            )
            await session.execute(stmt)
        await session.commit()

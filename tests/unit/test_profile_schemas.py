"""
Unit tests — Profile schema validation.
"""

import pytest
from pydantic import ValidationError

from app.modules.users.schemas import (
    ActivityResponse,
    OnboardingUpdate,
    PlanResponse,
    ProfileResponse,
    ProfileUpdate,
    StatsResponse,
)


class TestProfileUpdate:
    """Tests for ProfileUpdate schema."""

    def test_valid_display_name(self):
        update = ProfileUpdate(display_name="Shiv Patel")
        assert update.display_name == "Shiv Patel"

    def test_empty_update(self):
        update = ProfileUpdate()
        assert update.display_name is None

    def test_display_name_max_length(self):
        """Display name should not exceed 100 characters."""
        with pytest.raises(ValidationError):
            ProfileUpdate(display_name="x" * 101)

    def test_display_name_at_limit(self):
        update = ProfileUpdate(display_name="x" * 100)
        assert len(update.display_name) == 100


class TestOnboardingUpdate:
    """Tests for OnboardingUpdate schema."""

    def test_default_true(self):
        update = OnboardingUpdate()
        assert update.onboarding_completed is True

    def test_set_false(self):
        update = OnboardingUpdate(onboarding_completed=False)
        assert update.onboarding_completed is False


class TestPlanResponse:
    """Tests for PlanResponse schema."""

    def test_valid_plan(self):
        plan = PlanResponse(plan="free", limits={"prompts_per_day": 10})
        assert plan.plan == "free"
        assert plan.limits["prompts_per_day"] == 10


class TestStatsResponse:
    """Tests for StatsResponse schema."""

    def test_default_zeros(self):
        from datetime import datetime, timezone

        stats = StatsResponse(
            plan="free",
            member_since=datetime.now(timezone.utc),
        )
        assert stats.total_prompts == 0
        assert stats.total_templates == 0
        assert stats.total_chains == 0
        assert stats.total_optimizations == 0


class TestActivityResponse:
    """Tests for ActivityResponse schema."""

    def test_empty_activity(self):
        activity = ActivityResponse()
        assert activity.activities == []
        assert activity.total_count == 0

    def test_with_activities(self):
        from datetime import datetime, timezone
        from app.modules.users.schemas import ActivityItem

        items = [
            ActivityItem(
                action="test",
                description="Test action",
                timestamp=datetime.now(timezone.utc),
            )
        ]
        activity = ActivityResponse(activities=items, total_count=1)
        assert len(activity.activities) == 1

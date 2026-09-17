"""Unit tests for BadgeService and gamification logic."""
import pytest
from app.services.badge_service import BadgeService


def test_badge_service_evaluates_all_29_badges():
    badges = BadgeService.evaluate_badges(
        total_prompts=0,
        user_raw_scores=[],
        streak_days=0,
        inbuilt_templates_used=0,
        custom_templates=0,
        max_versions=0,
        unique_models=0,
        unique_modes=0,
    )
    assert len(badges) == 29
    assert all(not b["unlocked"] for b in badges)


def test_volume_milestones():
    # exactly > 10, > 100, > 250, > 500, > 1000
    badges_10 = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(10, [], 0, 0, 0, 0, 0, 0)}
    assert not badges_10["prompt-pioneer"]

    badges_11 = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(11, [], 0, 0, 0, 0, 0, 0)}
    assert badges_11["prompt-pioneer"]
    assert not badges_11["centurion-crafter"]

    badges_101 = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(101, [], 0, 0, 0, 0, 0, 0)}
    assert badges_101["centurion-crafter"]
    assert not badges_101["high-volume-architect"]

    badges_251 = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(251, [], 0, 0, 0, 0, 0, 0)}
    assert badges_251["high-volume-architect"]
    assert not badges_251["industrial-synthesizer"]

    badges_501 = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(501, [], 0, 0, 0, 0, 0, 0)}
    assert badges_501["industrial-synthesizer"]
    assert not badges_501["grandmaster-scribe"]

    badges_1001 = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(1001, [], 0, 0, 0, 0, 0, 0)}
    assert badges_1001["grandmaster-scribe"]


def test_raw_user_score_milestones():
    # 60+, 70+, 3x80+, 88+, 92+
    badges = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(1, [59.0], 0, 0, 0, 0, 0, 0)}
    assert not badges["quality-foundationalist"]

    badges = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(1, [60.0], 0, 0, 0, 0, 0, 0)}
    assert badges["quality-foundationalist"]
    assert not badges["articulate-thinker"]

    badges = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(1, [75.0], 0, 0, 0, 0, 0, 0)}
    assert badges["articulate-thinker"]
    assert not badges["master-of-precision"]

    # 3 prompts with 80+
    badges = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(3, [82.0, 85.0], 0, 0, 0, 0, 0, 0)}
    assert not badges["master-of-precision"]

    badges = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(3, [82.0, 85.0, 80.0], 0, 0, 0, 0, 0, 0)}
    assert badges["master-of-precision"]
    assert not badges["perfectionist"]

    badges = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(3, [88.0], 0, 0, 0, 0, 0, 0)}
    assert badges["perfectionist"]
    assert not badges["sovereign-wordsmith"]

    badges = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(3, [92.5], 0, 0, 0, 0, 0, 0)}
    assert badges["sovereign-wordsmith"]


def test_streak_milestones():
    # 7, 14, 30, 60, 100, 200, 500, 1000
    streaks = [
        (6, "7-day-spark", False),
        (7, "7-day-spark", True),
        (13, "fortnight-fortitude", False),
        (14, "fortnight-fortitude", True),
        (29, "monthly-devotion", False),
        (30, "monthly-devotion", True),
        (59, "habitual-craftsman", False),
        (60, "habitual-craftsman", True),
        (99, "century-of-consistency", False),
        (100, "century-of-consistency", True),
        (199, "iron-discipline", False),
        (200, "iron-discipline", True),
        (499, "the-500-club", False),
        (500, "the-500-club", True),
        (999, "millennial-legend", False),
        (1000, "millennial-legend", True),
    ]
    for days, badge_id, expected in streaks:
        b_map = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(0, [], days, 0, 0, 0, 0, 0)}
        assert b_map[badge_id] == expected, f"Failed for {badge_id} at {days} days"


def test_template_and_iteration_mastery():
    # Inbuilt template >= 10
    b_map = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(0, [], 0, 9, 0, 0, 0, 0)}
    assert not b_map["template-apprentice"]
    b_map = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(0, [], 0, 10, 0, 0, 0, 0)}
    assert b_map["template-apprentice"]

    # Custom templates >= 5
    b_map = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(0, [], 0, 0, 4, 0, 0, 0)}
    assert not b_map["blueprint-architect"]
    b_map = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(0, [], 0, 0, 5, 0, 0, 0)}
    assert b_map["blueprint-architect"]

    # Iteration specialist >= 3
    b_map = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(0, [], 0, 0, 0, 2, 0, 0)}
    assert not b_map["iteration-specialist"]
    b_map = {b["id"]: b["unlocked"] for b in BadgeService.evaluate_badges(0, [], 0, 0, 0, 3, 0, 0)}
    assert b_map["iteration-specialist"]

"""Unit tests for app/services/ranking_service.py.

``rank_candidates`` decides which retrieved template actually gets used, so its
tie-breaking order is the whole behaviour. The tests below drive each level of the
hierarchy in isolation: everything except the field under test is held equal, so a
failure names the exact rung that broke.

Templates are built unsaved by ``tests.factories`` — no session, no database.
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

import pytest

from app.db.models import Template
from app.services.ranking_service import RankingService
from tests.factories import make_template

pytestmark = pytest.mark.unit

TARGET_ROLE = "creator"
TARGET_MODE = "general"

# One shared parent id: rank_candidates never touches the relationship, and this
# keeps the builders from inventing an AI model per template.
AI_MODEL_ID = uuid4()


@pytest.fixture
def ranker() -> RankingService:
    return RankingService()


def template(
    *,
    role: Optional[str] = TARGET_ROLE,
    mode: Optional[str] = TARGET_MODE,
    is_featured: bool = False,
    use_count: int = 0,
    title: str = "candidate",
) -> Template:
    return make_template(
        ai_model_id=AI_MODEL_ID,
        role=role,
        mode=mode,
        is_featured=is_featured,
        use_count=use_count,
        title=title,
    )


def rank(ranker: RankingService, candidates: list[tuple[Template, float]]) -> list[Template]:
    return [item["template"] for item in ranker.rank_candidates(candidates, TARGET_ROLE, TARGET_MODE)]


# ─────────────────────────────────────────────────────────────────────────────
# The hierarchy, one rung at a time
# ─────────────────────────────────────────────────────────────────────────────


def test_similarity_dominates_every_other_signal(ranker: RankingService) -> None:
    """A better semantic match wins even when it loses on all four tie-breakers."""
    weak_but_privileged = template(
        role=TARGET_ROLE, mode=TARGET_MODE, is_featured=True, use_count=9_999
    )
    strong = template(role="other", mode="other", is_featured=False, use_count=0)

    assert rank(ranker, [(weak_but_privileged, 0.50), (strong, 0.51)])[0] is strong


def test_mode_match_breaks_a_similarity_tie(ranker: RankingService) -> None:
    """Mode outranks featured and use_count — the second rung of the hierarchy."""
    wrong_mode = template(mode="coding", is_featured=True, use_count=9_999)
    right_mode = template(mode=TARGET_MODE, is_featured=False, use_count=0)

    assert rank(ranker, [(wrong_mode, 0.80), (right_mode, 0.80)])[0] is right_mode


def test_featured_breaks_a_tie_once_mode_is_equal(ranker: RankingService) -> None:
    plain = template(use_count=9_999)
    featured = template(is_featured=True, use_count=0)

    assert rank(ranker, [(plain, 0.80), (featured, 0.80)])[0] is featured


def test_use_count_breaks_a_tie_once_featured_is_equal(ranker: RankingService) -> None:
    unpopular = template(use_count=1, role="other")
    popular = template(use_count=2, role="other")

    assert rank(ranker, [(unpopular, 0.80), (popular, 0.80)])[0] is popular


def test_role_match_is_the_last_tie_breaker(ranker: RankingService) -> None:
    """Role sits *below* use_count, which is worth pinning explicitly.

    A heavily-used template for the wrong role therefore beats an unused one for
    the right role. That ordering is deliberate in the docstring of the service,
    but it is surprising enough to deserve a test of its own.
    """
    wrong_role_but_used = template(role="analyst", use_count=1)
    right_role_unused = template(role=TARGET_ROLE, use_count=0)

    ordered = rank(ranker, [(right_role_unused, 0.80), (wrong_role_but_used, 0.80)])
    assert ordered[0] is wrong_role_but_used

    # With use_count equal, the role match finally decides it.
    tied_wrong = template(role="analyst", use_count=0)
    tied_right = template(role=TARGET_ROLE, use_count=0)
    assert rank(ranker, [(tied_wrong, 0.80), (tied_right, 0.80)])[0] is tied_right


def test_the_full_hierarchy_orders_a_mixed_field(ranker: RankingService) -> None:
    best = template(title="best")
    second = template(title="second", mode=TARGET_MODE, is_featured=True)
    third = template(title="third", mode=TARGET_MODE, is_featured=False)
    fourth = template(title="fourth", mode="coding", is_featured=True)

    ordered = rank(
        ranker,
        [(third, 0.70), (best, 0.90), (fourth, 0.70), (second, 0.70)],
    )

    assert [t.title for t in ordered] == ["best", "second", "third", "fourth"]


def test_equal_candidates_keep_their_input_order(ranker: RankingService) -> None:
    """``sorted`` is stable and ``reverse=True`` does not reverse ties.

    So retrieval order (pgvector distance order) survives a full tie, rather than
    being silently inverted.
    """
    first = template(title="first")
    second = template(title="second")

    ordered = rank(ranker, [(first, 0.80), (second, 0.80)])

    assert [t.title for t in ordered] == ["first", "second"]


# ─────────────────────────────────────────────────────────────────────────────
# Matching semantics
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "stored",
    ["creator", "CREATOR", "Creator", "  creator  ", "\tCreator\n"],
    ids=["exact", "upper", "title", "padded", "padded-mixed"],
)
def test_role_matching_ignores_case_and_surrounding_whitespace(
    ranker: RankingService, stored: str
) -> None:
    (item,) = ranker.rank_candidates([(template(role=stored), 0.5)], TARGET_ROLE, TARGET_MODE)

    assert item["exact_role_match"] is True


@pytest.mark.parametrize(
    "stored", ["general", "GENERAL", "  General  "], ids=["exact", "upper", "padded"]
)
def test_mode_matching_ignores_case_and_surrounding_whitespace(
    ranker: RankingService, stored: str
) -> None:
    (item,) = ranker.rank_candidates([(template(mode=stored), 0.5)], TARGET_ROLE, TARGET_MODE)

    assert item["exact_mode_match"] is True


def test_the_target_is_normalised_too(ranker: RankingService) -> None:
    """Both sides are stripped and lower-cased, so a padded target still matches."""
    (item,) = ranker.rank_candidates(
        [(template(role="creator", mode="general"), 0.5)], "  CREATOR ", " General  "
    )

    assert item["exact_role_match"] is True
    assert item["exact_mode_match"] is True


def test_a_partial_role_is_not_a_match(ranker: RankingService) -> None:
    """Equality, not substring — ``content creator`` must not match ``creator``."""
    (item,) = ranker.rank_candidates(
        [(template(role="content creator"), 0.5)], TARGET_ROLE, TARGET_MODE
    )

    assert item["exact_role_match"] is False


@pytest.mark.parametrize("missing", [None, ""], ids=["null", "empty"])
def test_a_template_without_a_role_or_mode_does_not_crash(
    ranker: RankingService, missing: Optional[str]
) -> None:
    """``templates.role`` and ``templates.mode`` are both nullable in the schema,
    and the falsy guard is what keeps ``.strip()`` off ``None``."""
    (item,) = ranker.rank_candidates(
        [(template(role=missing, mode=missing), 0.5)], TARGET_ROLE, TARGET_MODE
    )

    assert item["exact_role_match"] is False
    assert item["exact_mode_match"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Shape of the result
# ─────────────────────────────────────────────────────────────────────────────


def test_each_result_carries_the_scoring_components(ranker: RankingService) -> None:
    """``enhance_prompt`` reads ``similarity_score`` off the top item and stores it
    on the prompt row, so these keys are part of the service's contract."""
    candidate = template(is_featured=True, use_count=7)

    (item,) = ranker.rank_candidates([(candidate, 0.42)], TARGET_ROLE, TARGET_MODE)

    assert item == {
        "template": candidate,
        "similarity_score": 0.42,
        "exact_mode_match": True,
        "is_featured": True,
        "use_count": 7,
        "exact_role_match": True,
    }
    assert item["template"] is candidate, "the Template must be passed through, not copied"


def test_an_empty_candidate_list_returns_an_empty_list(ranker: RankingService) -> None:
    """The log line dereferences ``ranked[0]``, so the ``if ranked`` guard is the
    only thing keeping this from raising IndexError."""
    assert ranker.rank_candidates([], TARGET_ROLE, TARGET_MODE) == []


def test_the_input_list_is_not_reordered(ranker: RankingService) -> None:
    """``sorted`` returns a new list; the caller's candidate list stays as-is."""
    low, high = template(title="low"), template(title="high")
    candidates = [(low, 0.10), (high, 0.90)]

    ranker.rank_candidates(candidates, TARGET_ROLE, TARGET_MODE)

    assert [t.title for t, _ in candidates] == ["low", "high"]


def test_every_candidate_survives_ranking(ranker: RankingService) -> None:
    """Ranking reorders; it must never filter. Threshold filtering happens
    upstream in ``TemplateRetrievalService``."""
    candidates = [(template(title=f"t{i}"), i / 10) for i in range(5)]

    ranked = ranker.rank_candidates(candidates, TARGET_ROLE, TARGET_MODE)

    assert len(ranked) == 5
    assert {item["template"].title for item in ranked} == {f"t{i}" for i in range(5)}


def test_negative_and_zero_similarities_are_ranked_not_dropped(
    ranker: RankingService,
) -> None:
    """Cosine similarity can legitimately be <= 0, and the service applies no
    floor of its own."""
    negative, zero = template(title="negative"), template(title="zero")

    ordered = rank(ranker, [(negative, -0.4), (zero, 0.0)])

    assert [t.title for t in ordered] == ["zero", "negative"]

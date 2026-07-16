"""Unit tests for the deck-scoring functions — no database, no HTTP.

TEACHING NOTE — this is the payoff of keeping services/matching.py pure:
the "algorithm" is tested with plain objects and numbers. The API-level
ranking behavior is covered separately in test_swipes.py.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Posting, PostingCategory, PostingKind
from app.services.matching import (
    freshness_score,
    jaccard,
    proximity_score,
    rank_candidates,
    score_candidate,
    tokens,
)

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
WEIGHTS = (0.4, 0.3, 0.2, 0.1)


def posting(
    id: int,
    title: str,
    tags: list[str] | None = None,
    *,
    owner: str = "owner@example.com",
    kind: PostingKind = PostingKind.OFFER,
    age_days: float = 0.0,
) -> Posting:
    """An UNPERSISTED model instance — plain attribute bag for scoring."""
    return Posting(
        id=id,
        owner_email=owner,
        kind=kind,
        category=PostingCategory.GOODS,
        title=title,
        tags=tags or [],
        city="Berlin",
        latitude=52.5,
        longitude=13.4,
        created_at=NOW - timedelta(days=age_days),
    )


# --- ingredients -------------------------------------------------------------
def test_tokens_merge_title_and_tags_lowercased_without_stopwords():
    p = posting(1, "Looking for a Mountain Bike", ["Outdoors", " Sports "])
    assert tokens(p) == {"looking", "mountain", "bike", "outdoors", "sports"}


def test_jaccard_bounds_and_empty_sets():
    assert jaccard(frozenset({"bike"}), frozenset({"bike"})) == 1.0
    assert jaccard(frozenset({"bike"}), frozenset({"sofa"})) == 0.0
    assert jaccard(frozenset(), frozenset({"bike"})) == 0.0  # silence ≠ signal
    assert jaccard(frozenset({"a", "b"}), frozenset({"b", "c"})) == pytest.approx(1 / 3)


def test_proximity_decays_with_distance():
    assert proximity_score(0) == 1.0
    assert proximity_score(5) == 0.5
    assert proximity_score(5) > proximity_score(20) > proximity_score(100) > 0


def test_freshness_decays_with_age():
    assert freshness_score(0) == 1.0
    assert freshness_score(30) == 0.5
    assert freshness_score(-3) == 1.0  # clock skew must not over-boost


def test_score_blends_with_weights():
    score = score_candidate(
        candidate_tokens=frozenset({"bike"}),
        owner_need_tokens=frozenset({"guitar"}),
        my_need_tokens=frozenset({"bike"}),
        my_offer_tokens=frozenset({"guitar"}),
        distance_km=0.0,
        age_days=0.0,
        weights=WEIGHTS,
    )
    # Every ingredient maxed → score is exactly the sum of the weights.
    assert score == pytest.approx(1.0)


# --- ranking ------------------------------------------------------------------
def test_reciprocal_candidates_outrank_irrelevant_ones():
    """The acceptance scenario: same distance, same age — the offer that
    matches my need AND whose owner needs my offer must come first."""
    my_needs = [posting(100, "Mountain bike", ["bike"], kind=PostingKind.NEED)]
    my_offers = [posting(101, "Guitar lessons", ["guitar", "music"])]

    perfect = posting(1, "Hardtail mountain bike", ["bike"], owner="fit@example.com")
    tag_only = posting(2, "City bike", ["bike"], owner="oneway@example.com")
    unrelated = posting(3, "Old sofa", ["furniture"], owner="sofa@example.com")

    owner_needs = {
        # The perfect candidate's owner needs exactly what I offer.
        "fit@example.com": [
            posting(200, "Guitar teacher wanted", ["guitar"], kind=PostingKind.NEED)
        ],
        "oneway@example.com": [],
        "sofa@example.com": [],
    }

    ranked = rank_candidates(
        candidates=[unrelated, tag_only, perfect],
        distances_km={1: 3.0, 2: 3.0, 3: 3.0},
        my_needs=my_needs,
        my_offers=my_offers,
        owner_needs=owner_needs,
        now=NOW,
        weights=WEIGHTS,
    )
    assert [p.id for p in ranked] == [1, 2, 3]


def test_equal_scores_keep_incoming_order():
    """Stable sort: ties preserve SQL's nearest-first ordering."""
    a = posting(1, "Sofa", ["furniture"])
    b = posting(2, "Sofa", ["furniture"])
    ranked = rank_candidates(
        candidates=[a, b],
        distances_km={1: 2.0, 2: 2.0},
        my_needs=[],
        my_offers=[],
        owner_needs={},
        now=NOW,
        weights=WEIGHTS,
    )
    assert [p.id for p in ranked] == [1, 2]

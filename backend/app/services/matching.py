"""Deck scoring — the "sophisticated algorithm" behind the swipe deck.

TEACHING NOTE — this module is a PURE FUNCTION library: no database, no
HTTP, no clock reads (the caller passes `now`). That's what makes the
scoring directly unit-testable — feed postings in, get an ordering out —
and swappable the day tag overlap gives way to embeddings.

A candidate offer is scored on four ingredients:
- need_overlap:  does it look like something I NEED?
- reciprocity:   does its owner NEED something I OFFER? (both sides
                 benefiting is what makes a barter actually close)
- proximity:     decays with distance — local first.
- freshness:     mild boost for recent postings.
The blend weights live in configuration (core/config.py), not code.
"""

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone

from app.models import Posting

# Words too generic to signal a real overlap ("looking for a nice bike"
# should match on "bike", never on "nice").
_STOPWORDS = frozenset(
    "a an and are for from in my nice new of old on or some the to used with".split()
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(posting: Posting) -> frozenset[str]:
    """Normalized token set of a posting: its tags plus its title words."""
    words = set(_TOKEN_RE.findall(posting.title.lower()))
    tags = {tag.strip().lower() for tag in posting.tags}
    return frozenset((words | tags) - _STOPWORDS - {""})


def union_tokens(postings: Iterable[Posting]) -> frozenset[str]:
    result: frozenset[str] = frozenset()
    for posting in postings:
        result |= tokens(posting)
    return result


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Set overlap in [0, 1]: |A ∩ B| / |A ∪ B|. Empty sets score 0 —
    "we both said nothing" is not a signal."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def proximity_score(distance_km: float) -> float:
    """1 at zero distance, 0.5 at 5 km, long tail after — walkable beats
    a drive, but a great match further out still surfaces."""
    return 1.0 / (1.0 + distance_km / 5.0)


def freshness_score(age_days: float) -> float:
    """1 for brand new, 0.5 at 30 days. Freshness carries the smallest
    weight — it's a tiebreaker, not a ranking."""
    return 1.0 / (1.0 + max(age_days, 0.0) / 30.0)


def _age_days(created_at: datetime, now: datetime) -> float:
    # SQLite hands back naive datetimes even for TIMESTAMPTZ columns;
    # they were stored as UTC, so pin them back before subtracting.
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (now - created_at).total_seconds() / 86400.0


def score_candidate(
    *,
    candidate_tokens: frozenset[str],
    owner_need_tokens: frozenset[str],
    my_need_tokens: frozenset[str],
    my_offer_tokens: frozenset[str],
    distance_km: float,
    age_days: float,
    weights: tuple[float, float, float, float],
) -> float:
    """Blend the four ingredients; each is already in [0, 1]."""
    w_need, w_reciprocity, w_proximity, w_freshness = weights
    return (
        w_need * jaccard(my_need_tokens, candidate_tokens)
        + w_reciprocity * jaccard(my_offer_tokens, owner_need_tokens)
        + w_proximity * proximity_score(distance_km)
        + w_freshness * freshness_score(age_days)
    )


def rank_candidates(
    *,
    candidates: Sequence[Posting],
    distances_km: Mapping[int, float],
    my_needs: Sequence[Posting],
    my_offers: Sequence[Posting],
    owner_needs: Mapping[str, Sequence[Posting]],
    now: datetime,
    weights: tuple[float, float, float, float],
) -> list[Posting]:
    """Order candidate offers best-match-first for one caller.

    TEACHING NOTE — the caller's token sets are computed ONCE, outside
    the loop; per-candidate work is two set intersections and two
    divisions. With the candidate pool bounded upstream (the nearby
    query's radius + limit), plain Python is comfortably fast — resist
    precomputing scores into the database until measurement says so.
    """
    my_need_tokens = union_tokens(my_needs)
    my_offer_tokens = union_tokens(my_offers)
    owner_need_tokens = {
        owner: union_tokens(needs) for owner, needs in owner_needs.items()
    }

    def score(posting: Posting) -> float:
        return score_candidate(
            candidate_tokens=tokens(posting),
            owner_need_tokens=owner_need_tokens.get(
                posting.owner_email, frozenset()
            ),
            my_need_tokens=my_need_tokens,
            my_offer_tokens=my_offer_tokens,
            distance_km=distances_km.get(posting.id, math.inf),
            age_days=_age_days(posting.created_at, now),
            weights=weights,
        )

    # Stable sort: equal scores keep the nearest-first order from SQL.
    return sorted(candidates, key=score, reverse=True)

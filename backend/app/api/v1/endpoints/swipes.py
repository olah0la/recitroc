"""Swipe endpoints — the deck, verdicts, and the rewind.

The deck is a QUEUE, not a page: consuming it (swiping) is what advances
it, so there is no offset parameter — just "give me the next N nearby
offers I haven't judged yet".
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app import crud
from app.api.deps import AsyncDbSession, CurrentUser
from app.core.config import settings
from app.models import PostingKind, SwipeDirection
from app.schemas import PostingNearbyRead, PostingRead, SwipeCreate, SwipeResult
from app.services.geo import haversine_km
from app.services.matching import rank_candidates

router = APIRouter(prefix="/swipes", tags=["swipes"])

PostingId = Annotated[int, Path(ge=1, description="Numeric ID of the posting")]

_NO_LOCATION = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Set your location first (PUT /users/me/location).",
)


@router.get(
    "/deck",
    response_model=list[PostingNearbyRead],
    summary="The next nearby offers to swipe on",
)
async def get_deck(
    current_user: CurrentUser,
    db: AsyncDbSession,
    radius_km: Annotated[
        float, Query(gt=0, le=500, description="Search radius in kilometers")
    ] = 10,
    limit: Annotated[int, Query(ge=1, le=50, description="Deck size")] = 10,
) -> list[PostingNearbyRead]:
    """Nearby active OFFERS the caller hasn't swiped yet, best match first.

    Two stages:
    1. SQL narrows to a bounded candidate pool — active, in radius, not
       mine, not yet swiped (see crud.posting.list_nearby).
    2. Python ranks that pool with the matching score: need overlap,
       reciprocity, proximity, freshness (see services/matching.py).
    Already-judged postings never reappear — that's the deck's contract.
    """
    if current_user.latitude is None or current_user.longitude is None:
        raise _NO_LOCATION
    candidates, _ = await crud.posting.list_nearby(
        db,
        latitude=current_user.latitude,
        longitude=current_user.longitude,
        radius_km=radius_km,
        exclude_owner=current_user.email,
        limit=settings.DECK_CANDIDATE_POOL,
        offset=0,
        kind=PostingKind.OFFER,
        exclude_swiped_by=current_user.email,
    )

    distances = {
        p.id: haversine_km(
            current_user.latitude, current_user.longitude, p.latitude, p.longitude
        )
        for p in candidates
    }
    my_postings, _ = await crud.posting.list_by_owner(
        db, current_user.email, limit=settings.DECK_CANDIDATE_POOL, offset=0
    )
    candidate_owner_needs = await crud.posting.list_active_needs_by_owners(
        db, list({p.owner_email for p in candidates})
    )
    needs_by_owner: dict[str, list] = {}
    for need in candidate_owner_needs:
        needs_by_owner.setdefault(need.owner_email, []).append(need)

    ranked = rank_candidates(
        candidates=candidates,
        distances_km=distances,
        my_needs=[p for p in my_postings if p.kind == PostingKind.NEED],
        my_offers=[p for p in my_postings if p.kind == PostingKind.OFFER],
        owner_needs=needs_by_owner,
        now=datetime.now(timezone.utc),
        weights=settings.MATCH_WEIGHTS,
    )

    return [
        PostingNearbyRead(
            **PostingRead.model_validate(p).model_dump(),
            distance_km=round(distances[p.id], 2),
        )
        for p in ranked[:limit]
    ]


@router.post(
    "",
    response_model=SwipeResult,
    status_code=status.HTTP_201_CREATED,
    summary="Record a verdict on a posting",
)
async def create_swipe(
    payload: SwipeCreate, current_user: CurrentUser, db: AsyncDbSession
) -> SwipeResult:
    """Like or pass on a posting. Swiping again just updates the verdict.

    A LIKE that completes a mutual like creates a Match and returns
    `matched: true` — exactly once per pair; liking further postings of
    an already-matched partner stays `matched: false` so the client
    never re-celebrates an old match.
    """
    posting = await crud.posting.get(db, payload.posting_id)
    # Paused and nonexistent postings look identical here, same rule as
    # the public read path.
    if posting is None or not posting.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Posting not found"
        )
    if posting.owner_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot swipe on your own posting.",
        )
    await crud.swipe.upsert(
        db,
        swiper_email=current_user.email,
        posting_id=payload.posting_id,
        direction=payload.direction,
    )

    if payload.direction != SwipeDirection.LIKE:
        return SwipeResult(matched=False, match_id=None)

    # Mutual-like check: has the posting's owner already liked one of MY
    # active postings? (The unique constraint on the pair backstops the
    # race where both sides like simultaneously.)
    their_liked_posting = await crud.swipe.find_liked_posting_of(
        db, liker_email=posting.owner_email, owner_email=current_user.email
    )
    if their_liked_posting is None:
        return SwipeResult(matched=False, match_id=None)
    if await crud.match.get_for_pair(db, current_user.email, posting.owner_email):
        return SwipeResult(matched=False, match_id=None)

    match = await crud.match.create(
        db,
        email1=current_user.email,
        posting_of_1=their_liked_posting.id,  # mine, which they liked
        email2=posting.owner_email,
        posting_of_2=posting.id,  # theirs, which I just liked
    )
    return SwipeResult(matched=True, match_id=match.id)


@router.delete(
    "/{posting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Rewind: withdraw my verdict on a posting",
)
async def delete_swipe(
    posting_id: PostingId, current_user: CurrentUser, db: AsyncDbSession
) -> None:
    """Remove the caller's swipe so the posting re-enters their deck.

    Addressed by POSTING id, not swipe id: the client never sees swipe
    row ids, and "my verdict on posting X" is unambiguous thanks to the
    unique constraint.
    """
    swipe = await crud.swipe.get(db, current_user.email, posting_id)
    if swipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not swiped on this posting.",
        )
    await crud.swipe.delete(db, swipe)

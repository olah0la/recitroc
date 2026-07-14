"""Swipe endpoints — the deck, verdicts, and the rewind.

The deck is a QUEUE, not a page: consuming it (swiping) is what advances
it, so there is no offset parameter — just "give me the next N nearby
offers I haven't judged yet".
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app import crud
from app.api.deps import AsyncDbSession, CurrentUser
from app.models import PostingKind
from app.schemas import PostingNearbyRead, PostingRead, SwipeCreate, SwipeResult
from app.services.geo import haversine_km

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
    """Nearby active OFFERS the caller hasn't swiped yet, nearest first.

    This is the /postings/nearby query plus one extra filter: an
    anti-join against the caller's swipes (see crud.posting.list_nearby).
    Already-judged postings never reappear — that's the deck's contract.
    """
    if current_user.latitude is None or current_user.longitude is None:
        raise _NO_LOCATION
    postings, _ = await crud.posting.list_nearby(
        db,
        latitude=current_user.latitude,
        longitude=current_user.longitude,
        radius_km=radius_km,
        exclude_owner=current_user.email,
        limit=limit,
        offset=0,
        kind=PostingKind.OFFER,
        exclude_swiped_by=current_user.email,
    )
    return [
        PostingNearbyRead(
            **PostingRead.model_validate(p).model_dump(),
            distance_km=round(
                haversine_km(
                    current_user.latitude,
                    current_user.longitude,
                    p.latitude,
                    p.longitude,
                ),
                2,
            ),
        )
        for p in postings
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

    `matched` is always false for now — the matching engine is RT-5; the
    response shape is already the final contract.
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
    return SwipeResult(matched=False, match_id=None)


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

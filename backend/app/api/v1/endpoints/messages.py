"""Message endpoints — chat inside a match (RT-6).

REST + polling, deliberately: the client re-fetches the open thread with
an `after_id` cursor every few seconds. WebSocket push is a follow-up
ticket; the polling protocol here (cursor + composite index) is cheap
enough to ship first and simple enough to reason about.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app import crud
from app.api.deps import AsyncDbSession, CurrentUser
from app.models import Match
from app.schemas import MessageCreate, MessageRead

router = APIRouter(prefix="/matches", tags=["messages"])

MatchId = Annotated[int, Path(ge=1, description="Numeric ID of the match")]


async def get_my_match(
    match_id: MatchId, current_user: CurrentUser, db: AsyncDbSession
) -> Match:
    """Load the match and prove the caller belongs to it.

    TEACHING NOTE — authorization as a DEPENDENCY: every route in this
    file declares MyMatch, so the participant check exists in exactly one
    place and cannot be forgotten on a new route. 404 for a missing
    match, 403 for someone else's — you may know it exists, you may not
    read it.
    """
    match = await crud.match.get(db, match_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        )
    if current_user.email not in (match.user_a_email, match.user_b_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not part of this match.",
        )
    return match


MyMatch = Annotated[Match, Depends(get_my_match)]


@router.get(
    "/{match_id}/messages",
    response_model=list[MessageRead],
    summary="Fetch the conversation (incrementally)",
)
async def list_messages(
    match: MyMatch,
    db: AsyncDbSession,
    after_id: Annotated[
        int, Query(ge=0, description="Return only messages with id greater than this")
    ] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description="Max messages")] = 100,
) -> list[MessageRead]:
    """Messages oldest-first. Poll with `after_id` = the last id you have;
    the first fetch (after_id=0) returns the thread from the beginning."""
    messages = await crud.message.list_after(
        db, match.id, after_id=after_id, limit=limit
    )
    return [MessageRead.model_validate(m) for m in messages]


@router.post(
    "/{match_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message",
)
async def send_message(
    payload: MessageCreate,
    match: MyMatch,
    current_user: CurrentUser,
    db: AsyncDbSession,
) -> MessageRead:
    message = await crud.message.create(
        db, match_id=match.id, sender_email=current_user.email, body=payload.body
    )
    return MessageRead.model_validate(message)


@router.post(
    "/{match_id}/read",
    summary="Mark the partner's messages in this match as read",
)
async def mark_read(
    match: MyMatch, current_user: CurrentUser, db: AsyncDbSession
) -> dict[str, int]:
    """Idempotent: marking an already-read thread is a no-op returning 0."""
    count = await crud.message.mark_read(db, match.id, current_user.email)
    return {"marked_read": count}

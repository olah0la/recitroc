"""Matches endpoints — who you've mutually liked.

Matches are created as a side effect of swiping (see swipes.py); this
router only reads them. Messaging within a match arrives with RT-6.
"""

from fastapi import APIRouter

from app import crud
from app.api.deps import AsyncDbSession, CurrentUser, Pagination
from app.models import Match
from app.schemas import MatchRead, Page, PostingRead, UserRead

router = APIRouter(prefix="/matches", tags=["matches"])


def _as_read(match: Match, viewer_email: str) -> MatchRead:
    """Reshape the symmetric pair row into the viewer's perspective."""
    i_am_a = match.user_a_email == viewer_email
    partner = match.user_b if i_am_a else match.user_a
    my_posting = match.posting_a if i_am_a else match.posting_b
    their_posting = match.posting_b if i_am_a else match.posting_a
    return MatchRead(
        id=match.id,
        status=match.status,
        created_at=match.created_at,
        partner=UserRead.model_validate(partner),
        my_posting=PostingRead.model_validate(my_posting) if my_posting else None,
        their_posting=(
            PostingRead.model_validate(their_posting) if their_posting else None
        ),
    )


@router.get("", response_model=Page[MatchRead], summary="List my matches")
async def list_matches(
    current_user: CurrentUser, db: AsyncDbSession, page: Pagination
) -> Page[MatchRead]:
    """The caller's matches, newest first, shaped from their side."""
    matches, total = await crud.match.list_for_user(
        db, current_user.email, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[_as_read(m, current_user.email) for m in matches],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )

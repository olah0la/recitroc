"""CRUD operations for swipes (async stack)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Posting, Swipe, SwipeDirection


async def get(db: AsyncSession, swiper_email: str, posting_id: int) -> Swipe | None:
    """One user's verdict on one posting, if any.

    Looked up by the natural pair, not the surrogate id — callers think
    in terms of "my swipe on posting 7", never in swipe row numbers.
    """
    stmt = select(Swipe).where(
        Swipe.swiper_email == swiper_email, Swipe.posting_id == posting_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def upsert(
    db: AsyncSession, *, swiper_email: str, posting_id: int, direction: SwipeDirection
) -> Swipe:
    """Record a verdict, replacing any previous one.

    TEACHING NOTE — read-then-write upsert: simple and readable, and the
    UNIQUE constraint on (swiper_email, posting_id) backstops the race
    where two concurrent requests both find nothing (one INSERT then
    fails loudly instead of silently duplicating). The lock-free
    alternative — postgres `INSERT ... ON CONFLICT DO UPDATE` — is the
    upgrade path if swiping ever becomes contended, at the price of
    dialect-specific SQL.
    """
    swipe = await get(db, swiper_email, posting_id)
    if swipe is None:
        swipe = Swipe(
            swiper_email=swiper_email, posting_id=posting_id, direction=direction
        )
        db.add(swipe)
    else:
        swipe.direction = direction
    await db.commit()
    await db.refresh(swipe)
    return swipe


async def delete(db: AsyncSession, swipe: Swipe) -> None:
    await db.delete(swipe)
    await db.commit()


async def find_liked_posting_of(
    db: AsyncSession, *, liker_email: str, owner_email: str
) -> Posting | None:
    """One ACTIVE posting of owner_email that liker_email has LIKEd, if any.

    This is the reciprocity probe behind matching: after I like YOUR
    posting, the question is "have you already liked one of MINE?" — a
    non-None answer completes the mutual like. The returned posting
    becomes the match's other half.
    """
    stmt = (
        select(Posting)
        .join(Swipe, Swipe.posting_id == Posting.id)
        .where(
            Posting.owner_email == owner_email,
            Posting.is_active,
            Swipe.swiper_email == liker_email,
            Swipe.direction == SwipeDirection.LIKE,
        )
        .order_by(Swipe.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()

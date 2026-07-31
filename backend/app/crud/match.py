"""CRUD operations for matches (async stack)."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Match


def _ordered_pair(email1: str, email2: str) -> tuple[str, str]:
    """Canonical storage order — see the CHECK constraint on the model."""
    return (email1, email2) if email1 < email2 else (email2, email1)


async def get(db: AsyncSession, match_id: int) -> Match | None:
    return await db.get(Match, match_id)


async def get_for_pair(db: AsyncSession, email1: str, email2: str) -> Match | None:
    user_a, user_b = _ordered_pair(email1, email2)
    stmt = select(Match).where(
        Match.user_a_email == user_a, Match.user_b_email == user_b
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    email1: str,
    posting_of_1: int | None,
    email2: str,
    posting_of_2: int | None,
) -> Match:
    """Create the match for a pair, normalizing the storage order.

    Callers pass each user WITH their own posting; this function sorts
    both consistently so posting_a always belongs to user_a.
    """
    if email1 < email2:
        user_a, posting_a, user_b, posting_b = email1, posting_of_1, email2, posting_of_2
    else:
        user_a, posting_a, user_b, posting_b = email2, posting_of_2, email1, posting_of_1
    match = Match(
        user_a_email=user_a,
        user_b_email=user_b,
        posting_a_id=posting_a,
        posting_b_id=posting_b,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def list_for_user(
    db: AsyncSession, email: str, *, limit: int, offset: int
) -> tuple[list[Match], int]:
    """A user's matches, newest first, with both users and postings loaded.

    TEACHING NOTE — the caller may be on EITHER side of the pair, hence
    the OR. The selectinload options prefetch everything MatchRead needs;
    without them, serializing N matches would fire 4·N lazy queries.
    """
    stmt = select(Match).where(
        or_(Match.user_a_email == email, Match.user_b_email == email)
    )

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    stmt = (
        stmt.options(
            selectinload(Match.user_a),
            selectinload(Match.user_b),
            selectinload(Match.posting_a),
            selectinload(Match.posting_b),
        )
        .order_by(Match.created_at.desc(), Match.id.desc())
        .limit(limit)
        .offset(offset)
    )
    matches = list((await db.execute(stmt)).scalars().all())
    return matches, total

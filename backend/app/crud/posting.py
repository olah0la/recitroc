"""CRUD operations for postings — the ASYNC counterpart of crud/user.py.

TEACHING NOTE — compare this file side by side with crud/user.py:
the queries are IDENTICAL. Only three things change in async SQLAlchemy:
1. functions are `async def`,
2. every database round-trip is `await`ed (execute/commit/refresh/get),
3. the session type is AsyncSession.
Building the SELECT statement itself is pure Python — no I/O — so that
part needs no await. The await marks exactly where the event loop may
switch to serving another request.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Posting, PostingKind
from app.schemas import PostingCreate


async def get(db: AsyncSession, posting_id: int) -> Posting | None:
    return await db.get(Posting, posting_id)


async def list_by_owner(
    db: AsyncSession,
    owner_email: str,
    *,
    limit: int,
    offset: int,
    kind: PostingKind | None = None,
) -> tuple[list[Posting], int]:
    """One owner's postings — ALL of them, including paused ones.

    This backs GET /postings/mine, where the caller IS the owner; the
    active-only filtering that protects other users' paused postings
    happens in the public read paths, not here.
    """
    stmt = select(Posting).where(Posting.owner_email == owner_email)
    if kind is not None:
        stmt = stmt.where(Posting.kind == kind)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    stmt = stmt.order_by(Posting.id).limit(limit).offset(offset)
    postings = list((await db.execute(stmt)).scalars().all())
    return postings, total


async def create(
    db: AsyncSession,
    data: PostingCreate,
    *,
    owner_email: str,
    latitude: float,
    longitude: float,
    country: str | None,
) -> Posting:
    # Coordinates arrive as explicit keyword args, not inside `data`:
    # they were resolved by the geocoding service, not sent by the client.
    # Same for owner_email — it comes from the bearer token.
    posting = Posting(
        **data.model_dump(),
        owner_email=owner_email,
        latitude=latitude,
        longitude=longitude,
        country=country,
    )
    db.add(posting)  # add() is sync — it only stages the object in memory
    await db.commit()
    await db.refresh(posting)
    return posting


async def update(db: AsyncSession, posting: Posting, values: dict) -> Posting:
    """Apply pre-validated field values (PATCH semantics).

    Takes a plain dict (not the Update schema) because the endpoint may
    enrich the payload — e.g. a city change also updates lat/lon/country.
    """
    for field, value in values.items():
        setattr(posting, field, value)
    await db.commit()
    await db.refresh(posting)
    return posting


async def delete(db: AsyncSession, posting: Posting) -> None:
    await db.delete(posting)
    await db.commit()

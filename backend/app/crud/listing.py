"""CRUD operations for listings — the ASYNC counterpart of crud/user.py.

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

from app.models import Listing
from app.schemas import ListingCreate


async def get(db: AsyncSession, listing_id: int) -> Listing | None:
    return await db.get(Listing, listing_id)


async def list_(
    db: AsyncSession, *, limit: int, offset: int, city: str | None = None
) -> tuple[list[Listing], int]:
    stmt = select(Listing)
    if city:
        # Exact-but-case-insensitive match: "berlin" finds "Berlin".
        stmt = stmt.where(func.lower(Listing.city) == city.lower())

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    stmt = stmt.order_by(Listing.id).limit(limit).offset(offset)
    listings = list((await db.execute(stmt)).scalars().all())
    return listings, total


async def create(
    db: AsyncSession,
    data: ListingCreate,
    *,
    latitude: float,
    longitude: float,
    country: str | None,
) -> Listing:
    # Coordinates arrive as explicit keyword args, not inside `data`:
    # they were resolved by the geocoding service, not sent by the client.
    listing = Listing(
        **data.model_dump(), latitude=latitude, longitude=longitude, country=country
    )
    db.add(listing)  # add() is sync — it only stages the object in memory
    await db.commit()
    await db.refresh(listing)
    return listing


async def update(db: AsyncSession, listing: Listing, values: dict) -> Listing:
    """Apply pre-validated field values (PATCH semantics).

    Takes a plain dict (not the Update schema) because the endpoint may
    enrich the payload — e.g. a city change also updates lat/lon/country.
    """
    for field, value in values.items():
        setattr(listing, field, value)
    await db.commit()
    await db.refresh(listing)
    return listing


async def delete(db: AsyncSession, listing: Listing) -> None:
    await db.delete(listing)
    await db.commit()

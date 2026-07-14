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

import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Posting, PostingKind, Swipe
from app.schemas import PostingCreate

# One degree of latitude is ~111.32 km everywhere; a degree of longitude
# shrinks with the cosine of the latitude.
KM_PER_DEGREE = 111.32


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


async def list_nearby(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    exclude_owner: str,
    limit: int,
    offset: int,
    kind: PostingKind | None = None,
    exclude_swiped_by: str | None = None,
) -> tuple[list[Posting], int]:
    """Active postings within radius_km, nearest first, excluding one owner.

    With `exclude_swiped_by`, postings that user has already swiped are
    filtered out too — this variant IS the swipe deck.

    TEACHING NOTE — proximity search without PostGIS, in two stages:
    1. BOUNDING BOX: convert the radius into degree spans and filter with
       two BETWEENs. These are plain range predicates on the indexed
       latitude/longitude columns — the cheap cut that spares the math
       below from scanning the whole table.
    2. EQUIRECTANGULAR distance: within a city-sized box the Earth is
       flat enough that sqrt(Δlat² + (Δlng·cos(lat))²) is within ~1% of
       the true distance. We compare SQUARED distances (monotonic, so
       ordering and radius checks don't need the sqrt) and — crucially —
       cos(lat) is a Python-computed CONSTANT, so the SQL is pure
       arithmetic and runs identically on postgres and SQLite, whose
       builds often ship without trig functions.
    The exact haversine distance shown to clients is computed in Python
    on the one page of rows returned (services/geo.py haversine_km).
    """
    delta_lat = radius_km / KM_PER_DEGREE
    # cos(lat) → 0 near the poles would make the longitude span explode;
    # clamping keeps the box finite (and nobody swaps sofas at 89.9°N).
    cos_lat = max(math.cos(math.radians(latitude)), 0.01)
    delta_lng = radius_km / (KM_PER_DEGREE * cos_lat)

    # Squared distance in "latitude degrees", comparable against the
    # squared radius in the same unit.
    d_lat = Posting.latitude - latitude
    d_lng = (Posting.longitude - longitude) * cos_lat
    distance_sq = d_lat * d_lat + d_lng * d_lng
    radius_sq = (radius_km / KM_PER_DEGREE) ** 2

    stmt = select(Posting).where(
        Posting.is_active,
        Posting.owner_email != exclude_owner,
        Posting.latitude.between(latitude - delta_lat, latitude + delta_lat),
        Posting.longitude.between(longitude - delta_lng, longitude + delta_lng),
        # The box is square; this trims its corners to the circle.
        distance_sq <= radius_sq,
    )
    if kind is not None:
        stmt = stmt.where(Posting.kind == kind)
    if exclude_swiped_by is not None:
        # TEACHING NOTE — an ANTI-JOIN via NOT EXISTS: "no swipe row of
        # mine points at this posting". The correlated subquery never
        # fetches swipe rows; the database only checks their existence,
        # using the (swiper_email, posting_id) unique index.
        already_swiped = select(Swipe.id).where(
            Swipe.posting_id == Posting.id,
            Swipe.swiper_email == exclude_swiped_by,
        )
        stmt = stmt.where(~already_swiped.exists())

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    stmt = stmt.order_by(distance_sq).limit(limit).offset(offset)
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

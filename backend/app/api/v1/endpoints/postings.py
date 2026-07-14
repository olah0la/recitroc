"""Postings endpoints — the ASYNC stack, now auth-scoped.

Compare with users.py (sync): the FastAPI features are the same; what
changes is `async def` + `await`, the async DB dependency, and calls out
to an external service (geocoding/weather) that make async worthwhile.

Ownership model in one sentence: you create postings as YOURSELF (the
bearer token decides), everyone can read active postings, and only the
owner ever learns that a paused posting exists — hence 404, not 403,
for foreign write attempts.
"""

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Path, Query, status

from app import crud
from app.api.deps import AsyncDbSession, CurrentUser, GeoDep, Pagination
from app.api.utils import resolve_city
from app.models import Posting, PostingKind
from app.schemas import (
    MeetupConditions,
    Page,
    PostingCreate,
    PostingNearbyRead,
    PostingRead,
    PostingUpdate,
)
from app.services.geo import haversine_km

router = APIRouter(prefix="/postings", tags=["postings"])

PostingId = Annotated[int, Path(ge=1, description="Numeric ID of the posting")]


_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Posting not found"
)


async def _get_own_or_404(
    db: AsyncDbSession, posting_id: int, owner_email: str
) -> Posting:
    """Fetch a posting for a WRITE operation by its owner.

    TEACHING NOTE — 404 instead of 403 for someone else's posting: a 403
    would confirm the id exists, letting anyone enumerate other people's
    (possibly paused) postings. "Not yours" and "not there" are the same
    answer on purpose.
    """
    posting = await crud.posting.get(db, posting_id)
    if posting is None or posting.owner_email != owner_email:
        raise _NOT_FOUND
    return posting


@router.post(
    "",
    response_model=PostingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a posting (geocodes the city)",
)
async def create_posting(
    payload: PostingCreate,
    current_user: CurrentUser,
    db: AsyncDbSession,
    geo: GeoDep,
) -> PostingRead:
    """Create a need or an offer, owned by the authenticated user.

    TEACHING NOTE — while this handler awaits Open-Meteo (an eternity in
    CPU terms), the event loop is off serving other requests. A sync
    version would hold a worker thread hostage for the whole round-trip.
    """
    location = await resolve_city(geo, payload.city)
    return await crud.posting.create(
        db,
        payload,
        owner_email=current_user.email,
        latitude=location.latitude,
        longitude=location.longitude,
        country=location.country,
    )


@router.get(
    "/mine",
    response_model=Page[PostingRead],
    summary="List my postings (including paused ones)",
)
async def list_my_postings(
    current_user: CurrentUser,
    db: AsyncDbSession,
    page: Pagination,
    kind: Annotated[
        PostingKind | None, Query(description="Only needs, or only offers")
    ] = None,
) -> Page[PostingRead]:
    """The authenticated user's own postings, optionally filtered by kind.

    NOTE — this route must be declared BEFORE /{posting_id}: routes match
    in order, and "/postings/mine" would otherwise be captured by the
    path parameter and fail as "mine is not an integer".
    """
    postings, total = await crud.posting.list_by_owner(
        db, current_user.email, limit=page.limit, offset=page.offset, kind=kind
    )
    return Page(
        items=[PostingRead.model_validate(p) for p in postings],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/nearby",
    response_model=Page[PostingNearbyRead],
    summary="Postings near me, nearest first",
)
async def list_nearby_postings(
    current_user: CurrentUser,
    db: AsyncDbSession,
    page: Pagination,
    radius_km: Annotated[
        float, Query(gt=0, le=500, description="Search radius in kilometers")
    ] = 10,
    kind: Annotated[
        PostingKind | None, Query(description="Only needs, or only offers")
    ] = None,
) -> Page[PostingNearbyRead]:
    """Active postings within radius_km of MY stored location.

    The caller's own postings are excluded — you can't swap with
    yourself. Requires a location: set one with PUT /users/me/location.
    """
    if current_user.latitude is None or current_user.longitude is None:
        # 409, not 422: the request is perfectly well-formed — it's the
        # account's STATE (no location yet) that blocks it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Set your location first (PUT /users/me/location).",
        )
    postings, total = await crud.posting.list_nearby(
        db,
        latitude=current_user.latitude,
        longitude=current_user.longitude,
        radius_km=radius_km,
        exclude_owner=current_user.email,
        limit=page.limit,
        offset=page.offset,
        kind=kind,
    )
    # The exact, human-facing distance is computed here in Python — only
    # one page of rows ever reaches this loop (see crud list_nearby for
    # why SQL uses an approximation instead).
    items = [
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
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{posting_id}", response_model=PostingRead, summary="Get a posting")
async def get_posting(posting_id: PostingId, db: AsyncDbSession) -> PostingRead:
    """Public read of one ACTIVE posting.

    A paused posting 404s here for everyone — its owner reads it via
    /postings/mine. That keeps this endpoint unauthenticated (browsing
    postings needs no account) without leaking paused inventory.
    """
    posting = await crud.posting.get(db, posting_id)
    if posting is None or not posting.is_active:
        raise _NOT_FOUND
    return posting


@router.patch("/{posting_id}", response_model=PostingRead, summary="Update a posting")
async def update_posting(
    posting_id: PostingId,
    payload: PostingUpdate,
    current_user: CurrentUser,
    db: AsyncDbSession,
    geo: GeoDep,
) -> PostingRead:
    """Partially update one of MY postings; a city change re-geocodes."""
    posting = await _get_own_or_404(db, posting_id, current_user.email)
    values = payload.model_dump(exclude_unset=True)
    if "city" in values:
        location = await resolve_city(geo, values["city"])
        values.update(
            latitude=location.latitude,
            longitude=location.longitude,
            country=location.country,
        )
    return await crud.posting.update(db, posting, values)


@router.delete(
    "/{posting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a posting",
)
async def delete_posting(
    posting_id: PostingId, current_user: CurrentUser, db: AsyncDbSession
) -> None:
    posting = await _get_own_or_404(db, posting_id, current_user.email)
    await crud.posting.delete(db, posting)


@router.get(
    "/{posting_id}/weather",
    response_model=MeetupConditions,
    summary="Live meetup conditions at the posting's location",
)
async def meetup_conditions(
    posting_id: PostingId, db: AsyncDbSession, geo: GeoDep
) -> MeetupConditions:
    """Is today a good day to meet up and swap?

    TEACHING NOTE — asyncio.gather is the payoff of the async stack:
    weather and air quality come from two independent APIs, so we fire
    both requests CONCURRENTLY and await them together. Total latency is
    max(a, b) instead of a + b. Sequential awaits — `await x; await y` —
    would silently serialize them: awaiting one thing at a time is
    correct but concurrent only if you *ask* for it.
    """
    posting = await crud.posting.get(db, posting_id)
    if posting is None or not posting.is_active:
        raise _NOT_FOUND
    try:
        weather, air = await asyncio.gather(
            geo.current_weather(posting.latitude, posting.longitude),
            geo.air_quality(posting.latitude, posting.longitude),
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Weather service is unavailable, try again later.",
        ) from exc

    good_weather = weather.weather_code < 45 and weather.wind_speed_kmh < 35
    good_air = air.european_aqi is None or air.european_aqi <= 60
    verdict = (
        "Great day to meet and swap!"
        if good_weather and good_air
        else "Consider rescheduling the swap."
    )
    return MeetupConditions(
        posting_id=posting.id,
        city=posting.city,
        temperature_c=weather.temperature_c,
        wind_speed_kmh=weather.wind_speed_kmh,
        conditions=weather.conditions,
        european_aqi=air.european_aqi,
        air_quality=air.rating,
        verdict=verdict,
    )

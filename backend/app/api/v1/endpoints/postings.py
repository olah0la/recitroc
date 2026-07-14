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
from app.models import Posting, PostingKind
from app.schemas import (
    MeetupConditions,
    Page,
    PostingCreate,
    PostingRead,
    PostingUpdate,
)
from app.services.geo import GeoLocation

router = APIRouter(prefix="/postings", tags=["postings"])

PostingId = Annotated[int, Path(ge=1, description="Numeric ID of the posting")]


async def _resolve_city(geo: GeoDep, city: str) -> GeoLocation:
    """Geocode a city, translating the two failure modes into HTTP errors.

    TEACHING NOTE — distinguish "you sent nonsense" from "upstream broke":
    - unknown city  -> 422: the request itself cannot be fulfilled,
    - provider down -> 502 Bad Gateway: WE failed, acting as a gateway.
      Never let this surface as a raw 500: a 500 says "bug in our code"
      and hides the real, retryable cause from clients and dashboards.
    """
    try:
        location = await geo.geocode(city)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Geocoding service is unavailable, try again later.",
        ) from exc
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not find a city named {city!r}.",
        )
    return location


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
    location = await _resolve_city(geo, payload.city)
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
        location = await _resolve_city(geo, values["city"])
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

"""Listings endpoints — the ASYNC stack in action.

Compare with users.py/items.py (sync): the FastAPI features are the same;
what changes is `async def` + `await`, the async DB dependency, and calls
out to an external service (geocoding/weather) that make async worthwhile.
"""

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Path, Query, status

from app import crud
from app.api.deps import AsyncDbSession, GeoDep, Pagination
from app.models import Listing
from app.schemas import (
    ListingCreate,
    ListingRead,
    ListingUpdate,
    MeetupConditions,
    Page,
)
from app.services.geo import GeoLocation

router = APIRouter(prefix="/listings", tags=["listings"])

ListingId = Annotated[int, Path(ge=1, description="Numeric ID of the listing")]


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not find a city named {city!r}.",
        )
    return location


async def _get_or_404(db: AsyncDbSession, listing_id: int) -> Listing:
    listing = await crud.listing.get(db, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )
    return listing


@router.post(
    "",
    response_model=ListingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a listing (geocodes the city)",
)
async def create_listing(
    payload: ListingCreate, db: AsyncDbSession, geo: GeoDep
) -> ListingRead:
    """Create a listing, resolving its city to coordinates.

    TEACHING NOTE — while this handler awaits Open-Meteo (an eternity in
    CPU terms), the event loop is off serving other requests. A sync
    version would hold a worker thread hostage for the whole round-trip.
    """
    location = await _resolve_city(geo, payload.city)
    return await crud.listing.create(
        db,
        payload,
        latitude=location.latitude,
        longitude=location.longitude,
        country=location.country,
    )


@router.get("", response_model=Page[ListingRead], summary="List listings")
async def list_listings(
    db: AsyncDbSession,
    page: Pagination,
    city: Annotated[
        str | None, Query(min_length=1, description="Filter by city name")
    ] = None,
) -> Page[ListingRead]:
    listings, total = await crud.listing.list_(
        db, limit=page.limit, offset=page.offset, city=city
    )
    return Page(
        items=[ListingRead.model_validate(listing) for listing in listings],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{listing_id}", response_model=ListingRead, summary="Get a listing")
async def get_listing(listing_id: ListingId, db: AsyncDbSession) -> ListingRead:
    return await _get_or_404(db, listing_id)


@router.patch("/{listing_id}", response_model=ListingRead, summary="Update a listing")
async def update_listing(
    listing_id: ListingId, payload: ListingUpdate, db: AsyncDbSession, geo: GeoDep
) -> ListingRead:
    """Partially update a listing; a city change triggers a re-geocode."""
    listing = await _get_or_404(db, listing_id)
    values = payload.model_dump(exclude_unset=True)
    if "city" in values:
        location = await _resolve_city(geo, values["city"])
        values.update(
            latitude=location.latitude,
            longitude=location.longitude,
            country=location.country,
        )
    return await crud.listing.update(db, listing, values)


@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a listing",
)
async def delete_listing(listing_id: ListingId, db: AsyncDbSession) -> None:
    listing = await _get_or_404(db, listing_id)
    await crud.listing.delete(db, listing)


@router.get(
    "/{listing_id}/weather",
    response_model=MeetupConditions,
    summary="Live meetup conditions at the listing's location",
)
async def meetup_conditions(
    listing_id: ListingId, db: AsyncDbSession, geo: GeoDep
) -> MeetupConditions:
    """Is today a good day to meet up and swap?

    TEACHING NOTE — asyncio.gather is the payoff of the async stack:
    weather and air quality come from two independent APIs, so we fire
    both requests CONCURRENTLY and await them together. Total latency is
    max(a, b) instead of a + b. Sequential awaits — `await x; await y` —
    would silently serialize them: awaiting one thing at a time is
    correct but concurrent only if you *ask* for it.
    """
    listing = await _get_or_404(db, listing_id)
    try:
        weather, air = await asyncio.gather(
            geo.current_weather(listing.latitude, listing.longitude),
            geo.air_quality(listing.latitude, listing.longitude),
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
        listing_id=listing.id,
        city=listing.city,
        temperature_c=weather.temperature_c,
        wind_speed_kmh=weather.wind_speed_kmh,
        conditions=weather.conditions,
        european_aqi=air.european_aqi,
        air_quality=air.rating,
        verdict=verdict,
    )

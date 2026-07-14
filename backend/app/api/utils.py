"""API-layer helpers shared by multiple endpoint modules.

TEACHING NOTE — why this lives under app/api and not app/services:
it raises HTTPException, i.e. it speaks HTTP. The services layer must
stay protocol-agnostic (a CLI or background job can't do anything with
a 502); translating failures into status codes is the API layer's job,
so a helper that does that belongs to the API layer.
"""

import httpx
from fastapi import HTTPException, status

from app.services.geo import GeoClient, GeoLocation


async def resolve_city(geo: GeoClient, city: str) -> GeoLocation:
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

"""Listing schemas.

TEACHING NOTE — input shape != stored shape: the client sends a *city
name*; the API stores *coordinates* it resolved via an external service.
The schemas make that contract explicit: ListingCreate has no lat/lon
(clients can't fake a location), ListingRead exposes what was resolved.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ListingBase(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Espresso machine"])
    description: str | None = Field(default=None, examples=["Trade for a bicycle."])
    city: str = Field(min_length=1, max_length=120, examples=["Berlin"])


class ListingCreate(ListingBase):
    """Payload for POST /listings."""


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    # Changing the city triggers a re-geocode in the endpoint.
    city: str | None = Field(default=None, min_length=1, max_length=120)


class ListingRead(ListingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    country: str | None
    latitude: float
    longitude: float
    created_at: datetime
    updated_at: datetime


class MeetupConditions(BaseModel):
    """Live weather + air quality at a listing's location.

    Composed from TWO concurrent external API calls — see the
    /listings/{id}/weather endpoint for the asyncio.gather demo.
    """

    listing_id: int
    city: str
    temperature_c: float
    wind_speed_kmh: float
    conditions: str = Field(examples=["clear sky"])
    european_aqi: int | None
    air_quality: str = Field(examples=["good"])
    verdict: str = Field(examples=["Great day to meet and swap!"])

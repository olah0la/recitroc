"""Posting schemas.

TEACHING NOTE — input shape != stored shape: the client sends a *city
name*; the API stores *coordinates* it resolved via an external service.
The schemas make that contract explicit: PostingCreate has no lat/lon
(clients can't fake a location), PostingRead exposes what was resolved.
Likewise there is no owner_email on Create — the owner is whoever holds
the bearer token, never a body field.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PostingCategory, PostingKind


class PostingBase(BaseModel):
    # The Python enums double as validators: any value other than
    # "offer"/"need" (resp. "goods"/"service") is an automatic 422, and
    # the allowed values are listed in the OpenAPI docs for free.
    kind: PostingKind
    category: PostingCategory
    title: str = Field(min_length=1, max_length=200, examples=["Espresso machine"])
    description: str | None = Field(default=None, examples=["Trade for a bicycle."])
    tags: list[str] = Field(
        default_factory=list, max_length=10, examples=[["kitchen", "coffee"]]
    )
    city: str = Field(min_length=1, max_length=120, examples=["Berlin"])


class PostingCreate(PostingBase):
    """Payload for POST /postings."""


class PostingUpdate(BaseModel):
    """Payload for PATCH /postings/{id}.

    `kind` is deliberately absent: a need becoming an offer is a different
    posting, not an edit — delete and recreate instead.
    """

    category: PostingCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    tags: list[str] | None = Field(default=None, max_length=10)
    # Changing the city triggers a re-geocode in the endpoint.
    city: str | None = Field(default=None, min_length=1, max_length=120)
    # Pause/resume without deleting (inactive = visible to owner only).
    is_active: bool | None = None


class PostingRead(PostingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_email: str
    country: str | None
    latitude: float
    longitude: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MeetupConditions(BaseModel):
    """Live weather + air quality at a posting's location.

    Composed from TWO concurrent external API calls — see the
    /postings/{id}/weather endpoint for the asyncio.gather demo.
    """

    posting_id: int
    city: str
    temperature_c: float
    wind_speed_kmh: float
    conditions: str = Field(examples=["clear sky"])
    european_aqi: int | None
    air_quality: str = Field(examples=["good"])
    verdict: str = Field(examples=["Great day to meet and swap!"])

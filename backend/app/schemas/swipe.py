"""Swipe schemas."""

from pydantic import BaseModel, Field

from app.models import SwipeDirection


class SwipeCreate(BaseModel):
    """Payload for POST /swipes — a verdict on a posting."""

    posting_id: int = Field(ge=1)
    direction: SwipeDirection


class SwipeResult(BaseModel):
    """Response of POST /swipes.

    TEACHING NOTE — the response is designed for the NEXT feature: the
    client's only question after a like is "did that create a match?".
    Until the matching engine lands (RT-5) the answer is always no, but
    shipping the contract now means the frontend never has to change.
    """

    matched: bool = False
    match_id: int | None = None

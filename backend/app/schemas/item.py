"""Item schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    # min_length=1 turns "" into a validation error — empty titles are a
    # business rule best enforced at the schema boundary.
    title: str = Field(min_length=1, max_length=200, examples=["Vintage lamp"])
    description: str | None = Field(default=None, examples=["Barely used."])


class ItemCreate(ItemBase):
    """Payload for POST /users/{email}/items.

    Note there is no `owner_email` field: the owner comes from the URL
    path. Never let a request body claim a resource belongs to someone
    else when the URL already establishes ownership.
    """


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_email: str
    created_at: datetime

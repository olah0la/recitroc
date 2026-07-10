"""Schemas shared across resources."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A page of results plus the metadata a client needs to paginate.

    TEACHING NOTE — generic response models:
    `Page[UserRead]` and `Page[ItemRead]` reuse this one class. FastAPI
    expands the generic into the OpenAPI schema, so the docs show the
    exact item type of each endpoint. Returning a bare `list[...]` works
    too, but then the client can never know the total count or whether
    more pages exist.
    """

    items: list[T]
    total: int  # total rows matching the query (not just this page)
    limit: int
    offset: int

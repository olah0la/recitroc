"""Listing model — an item offered for a local, in-person swap.

Served by the ASYNC stack (see api/v1/endpoints/listings.py).

TEACHING NOTE — the model itself is identical in style to the sync ones:
ORM models are just table descriptions; sync-vs-async is a property of
the *session* that loads them, not of the model.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    # The client only sends a city name; we resolve it to coordinates via
    # an external geocoding API at write time. Storing the result means we
    # pay the external call ONCE per write, not on every read.
    city: Mapped[str] = mapped_column(String(120), index=True)
    country: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float]
    longitude: Mapped[float]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"Listing(id={self.id!r}, title={self.title!r}, city={self.city!r})"

"""Posting model — the unified need/offer object at the heart of Recitroc.

A posting is something a user NEEDS from the community or OFFERS to it,
either goods or a service. It replaced the two earlier prototypes:
`items` (owned, but no geo) and `listings` (geo, but no owner).

Served by the ASYNC stack (see api/v1/endpoints/postings.py) because
creating one calls the external geocoding service.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


# TEACHING NOTE — domain enums live with the model (the innermost layer),
# so schemas AND crud can import them without any layering violation.
# Inheriting from `str` makes members compare/serialize as plain strings
# ("offer"), which Pydantic and JSON handle natively.
class PostingKind(str, enum.Enum):
    OFFER = "offer"
    NEED = "need"


class PostingCategory(str, enum.Enum):
    GOODS = "goods"
    SERVICE = "service"


# By default SQLAlchemy persists enum NAMES ("OFFER"); values_callable
# switches that to the values ("offer") so the database, the API JSON and
# the Python code all speak the same casing.
def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class Posting(Base):
    __tablename__ = "postings"

    id: Mapped[int] = mapped_column(primary_key=True)

    owner_email: Mapped[str] = mapped_column(
        ForeignKey("users.email", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )

    kind: Mapped[PostingKind] = mapped_column(
        Enum(PostingKind, name="postingkind", values_callable=_enum_values)
    )
    category: Mapped[PostingCategory] = mapped_column(
        Enum(PostingCategory, name="postingcategory", values_callable=_enum_values)
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    # TEACHING NOTE — JSON instead of postgres ARRAY, on purpose: the test
    # suite runs on SQLite, which has no ARRAY type, while JSON exists on
    # both. `with_variant` upgrades the column to JSONB on postgres only —
    # JSONB is the binary, indexable form (a GIN index becomes possible
    # the day tag search needs it).
    tags: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list
    )

    # The client only sends a city name; we resolve it to coordinates via
    # the external geocoding API at write time. Storing the result means
    # we pay the external call ONCE per write, not on every read.
    city: Mapped[str] = mapped_column(String(120), index=True)
    country: Mapped[str | None] = mapped_column(String(120))
    # Indexed for the nearby query's bounding-box range scans
    # (see crud/posting.py list_nearby).
    latitude: Mapped[float] = mapped_column(index=True)
    longitude: Mapped[float] = mapped_column(index=True)

    # Soft on/off switch: pausing a posting (PATCH is_active=false) is not
    # deleting it — inactive postings stay visible to their owner only.
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="postings")

    def __repr__(self) -> str:
        return (
            f"Posting(id={self.id!r}, kind={self.kind!r}, title={self.title!r}, "
            f"owner={self.owner_email!r})"
        )

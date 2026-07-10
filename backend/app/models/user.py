"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# TEACHING NOTE — TYPE_CHECKING avoids a circular import: user.py and
# item.py reference each other's classes, but only in type hints. At
# runtime SQLAlchemy resolves the string "Item" via its class registry.
if TYPE_CHECKING:
    from app.models.item import Item


class User(Base):
    __tablename__ = "users"

    # TEACHING NOTE — SQLAlchemy 2.0 typed declarative style:
    # `Mapped[int]` declares the *Python* type (your IDE/mypy understand it),
    # `mapped_column(...)` declares the *database* column. `Mapped[str | None]`
    # automatically makes the column nullable.
    id: Mapped[int] = mapped_column(primary_key=True)

    # unique=True adds a UNIQUE constraint (enforced by the DATABASE — the
    # only race-proof way to guarantee uniqueness). index=True speeds up the
    # lookup-by-email query in crud/user.py.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))

    # server_default puts the default in the DDL, so rows inserted by *any*
    # client (psql, another service, a data migration) still get a value —
    # a plain Python `default=` would only apply to inserts made through
    # this ORM.
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    # TEACHING NOTE — always store timezone-aware UTC timestamps
    # (DateTime(timezone=True) maps to postgres TIMESTAMPTZ). Let the
    # database clock stamp them (func.now()) so all rows share one clock.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # refreshed automatically on every ORM UPDATE
    )

    # TEACHING NOTE — relationship() is pure ORM: it creates no column.
    # The foreign key lives on items.owner_id; this attribute just lets us
    # navigate user.items / item.owner in Python.
    # cascade="all, delete-orphan" makes deleting a user delete their items
    # at the ORM level (mirrored by ondelete="CASCADE" on the FK for deletes
    # that bypass the ORM).
    items: Mapped[list["Item"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"

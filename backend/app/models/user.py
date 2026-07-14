"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# TEACHING NOTE — TYPE_CHECKING avoids a circular import: user.py and
# posting.py reference each other's classes, but only in type hints. At
# runtime SQLAlchemy resolves the string "Posting" via its class registry.
if TYPE_CHECKING:
    from app.models.posting import Posting


class User(Base):
    __tablename__ = "users"

    # TEACHING NOTE — SQLAlchemy 2.0 typed declarative style:
    # `Mapped[str]` declares the *Python* type (your IDE/mypy understand it),
    # `mapped_column(...)` declares the *database* column. `Mapped[str | None]`
    # automatically makes the column nullable.
    #
    # The email is a NATURAL primary key (an attribute with real-world
    # meaning) rather than a SURROGATE one (an opaque auto-increment id).
    # Trade-off to know: a natural PK is copied into every referencing row
    # (items.owner_email) and changing it means rewriting them all — which
    # is why the FK on items declares onupdate="CASCADE".
    email: Mapped[str] = mapped_column(String(255), primary_key=True)

    # unique=True adds a UNIQUE constraint (enforced by the DATABASE — the
    # only race-proof way to guarantee uniqueness). A nullable unique
    # column is fine: SQL treats NULLs as distinct, so any number of users
    # may leave the username unset.
    username: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))

    # TEACHING NOTE — only the bcrypt HASH is ever stored (see
    # core/security.py); the plaintext password exists solely in the
    # request body of signup/login. This column must never appear in a
    # Read schema — response_model filtering is what keeps it from
    # leaking (see the TEACHING NOTE on list_users in endpoints/users.py).
    hashed_password: Mapped[str] = mapped_column(String(255))

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
    # The foreign key lives on postings.owner_email; this attribute just
    # lets us navigate user.postings / posting.owner in Python.
    # cascade="all, delete-orphan" makes deleting a user delete their
    # postings at the ORM level (mirrored by ondelete="CASCADE" on the FK
    # for deletes that bypass the ORM).
    postings: Mapped[list["Posting"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"User(email={self.email!r}, username={self.username!r})"

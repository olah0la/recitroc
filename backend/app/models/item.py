"""Item model — the "many" side of the User→Item one-to-many."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    # Text = unbounded length; String(n) = VARCHAR(n). Use Text for
    # free-form user content, String for values with a natural size limit.
    description: Mapped[str | None] = mapped_column(Text)

    # TEACHING NOTE — the ForeignKey targets the *table.column* name
    # ("users.id"), not the Python class. ondelete="CASCADE" tells postgres
    # itself to remove orphaned items if a user row is deleted outside the
    # ORM. index=True matters: we filter items by owner constantly, and
    # postgres does NOT index FK columns automatically.
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"Item(id={self.id!r}, title={self.title!r})"

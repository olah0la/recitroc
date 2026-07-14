"""Swipe model — one user's verdict on one posting.

Persisting swipes is what makes the deck real: a posting you have
already judged never comes back (the deck query anti-joins this table),
and a mutual LIKE is the raw material for matching (RT-5).
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SwipeDirection(str, enum.Enum):
    LIKE = "like"
    PASS = "pass"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class Swipe(Base):
    __tablename__ = "swipes"

    # TEACHING NOTE — the UNIQUE constraint is the data model speaking:
    # a user has exactly ONE current verdict per posting. Swiping again
    # (after a rewind, say) is an UPDATE of that verdict, not a second
    # row — the crud layer upserts against this constraint.
    __table_args__ = (
        UniqueConstraint("swiper_email", "posting_id", name="uq_swipes_verdict"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    swiper_email: Mapped[str] = mapped_column(
        ForeignKey("users.email", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    # When a posting is deleted its verdicts are meaningless — cascade
    # them away rather than keeping orphaned judgment rows around.
    posting_id: Mapped[int] = mapped_column(
        ForeignKey("postings.id", ondelete="CASCADE"), index=True
    )

    direction: Mapped[SwipeDirection] = mapped_column(
        Enum(SwipeDirection, name="swipedirection", values_callable=_enum_values)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Swipe(swiper={self.swiper_email!r}, posting_id={self.posting_id!r}, "
            f"direction={self.direction!r})"
        )

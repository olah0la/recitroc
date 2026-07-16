"""Match model — two users who mutually liked each other's postings.

A match is between USERS (one per pair, ever), while remembering which
two postings triggered it. Conversations (RT-6) and exchange completion
(RT-7) hang off this row.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.posting import Posting
    from app.models.user import User


class MatchStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class Match(Base):
    __tablename__ = "matches"

    # TEACHING NOTE — canonical pair ordering: the two participants are
    # always stored with user_a_email < user_b_email (lexicographic), so
    # (ada, bob) and (bob, ada) are the SAME row and the UNIQUE
    # constraint can enforce one-match-per-pair. The CHECK constraint
    # makes the invariant a database guarantee, not a code convention
    # someone can forget.
    __table_args__ = (
        UniqueConstraint("user_a_email", "user_b_email", name="uq_matches_pair"),
        CheckConstraint("user_a_email < user_b_email", name="ordered_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_a_email: Mapped[str] = mapped_column(
        ForeignKey("users.email", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    user_b_email: Mapped[str] = mapped_column(
        ForeignKey("users.email", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )

    # The postings that triggered the match: posting_a is OWNED BY user_a
    # (and was liked by user_b), posting_b vice versa. SET NULL, not
    # CASCADE: deleting a posting must not dissolve the human connection
    # it created — the match (and its future conversation) outlives it.
    posting_a_id: Mapped[int | None] = mapped_column(
        ForeignKey("postings.id", ondelete="SET NULL")
    )
    posting_b_id: Mapped[int | None] = mapped_column(
        ForeignKey("postings.id", ondelete="SET NULL")
    )

    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="matchstatus", values_callable=_enum_values),
        server_default=MatchStatus.ACTIVE.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # TEACHING NOTE — two relationships to the SAME table require
    # `foreign_keys` to disambiguate which FK column each one follows;
    # SQLAlchemy cannot guess.
    user_a: Mapped["User"] = relationship(foreign_keys=[user_a_email])
    user_b: Mapped["User"] = relationship(foreign_keys=[user_b_email])
    posting_a: Mapped["Posting | None"] = relationship(foreign_keys=[posting_a_id])
    posting_b: Mapped["Posting | None"] = relationship(foreign_keys=[posting_b_id])

    def __repr__(self) -> str:
        return (
            f"Match(id={self.id!r}, a={self.user_a_email!r}, "
            f"b={self.user_b_email!r}, status={self.status!r})"
        )

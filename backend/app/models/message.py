"""Message model — chat inside a match.

Messages exist only WITHIN a match (RT-6): you can only talk to someone
you've mutually liked. That single design decision is the product's whole
anti-spam story — there is no cold-contact surface to abuse.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.user import User


class Message(Base):
    __tablename__ = "messages"

    # TEACHING NOTE — the composite (match_id, id) index is the whole cost
    # model of polling: "messages of match M with id > cursor" becomes one
    # index range scan, no matter how big the table grows. The client's
    # after_id cursor and this index are two halves of one design.
    __table_args__ = (Index("ix_messages_match_id_id", "match_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # CASCADE: a match dissolving takes its conversation with it — messages
    # have no meaning outside the pair they were spoken in.
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE")
    )
    sender_email: Mapped[str] = mapped_column(
        ForeignKey("users.email", ondelete="CASCADE", onupdate="CASCADE")
    )

    body: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # NULL = unread by the recipient. One recipient per message (a match is
    # exactly two people), so a single timestamp suffices — no join table.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    match: Mapped["Match"] = relationship()
    sender: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return (
            f"Message(id={self.id!r}, match_id={self.match_id!r}, "
            f"sender={self.sender_email!r})"
        )

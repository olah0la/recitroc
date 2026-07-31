"""CRUD operations for messages (async stack)."""

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message


async def list_after(
    db: AsyncSession, match_id: int, *, after_id: int, limit: int
) -> list[Message]:
    """Messages of a match newer than the cursor, oldest first.

    TEACHING NOTE — cursor pagination, not offset: the client remembers
    the last id it has seen and asks for "everything after". Unlike
    OFFSET, the cursor is stable when new rows arrive mid-poll, and the
    (match_id, id) index answers it with one range scan.
    """
    stmt = (
        select(Message)
        .where(Message.match_id == match_id, Message.id > after_id)
        .order_by(Message.id)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def create(
    db: AsyncSession, *, match_id: int, sender_email: str, body: str
) -> Message:
    message = Message(match_id=match_id, sender_email=sender_email, body=body)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def mark_read(db: AsyncSession, match_id: int, reader_email: str) -> int:
    """Mark the partner's unread messages in a match as read; return how many.

    Only messages the reader did NOT send qualify — you cannot "read"
    your own messages, they are born read from your point of view.
    """
    stmt = (
        update(Message)
        .where(
            Message.match_id == match_id,
            Message.sender_email != reader_email,
            Message.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def preview_for_matches(
    db: AsyncSession, match_ids: Sequence[int], viewer_email: str
) -> dict[int, tuple[Message | None, int]]:
    """Per match: (last message, viewer's unread count) — in bulk.

    TEACHING NOTE — this exists so the matches LIST endpoint stays two
    queries total no matter how many matches it returns. The tempting
    per-match "SELECT ... ORDER BY id DESC LIMIT 1" loop is the N+1
    pattern this module keeps avoiding by hand.
    """
    if not match_ids:
        return {}

    # Latest message id per match, then the rows themselves in one IN().
    last_ids_stmt = (
        select(func.max(Message.id))
        .where(Message.match_id.in_(match_ids))
        .group_by(Message.match_id)
    )
    last_ids = [row for row in (await db.execute(last_ids_stmt)).scalars()]
    last_by_match: dict[int, Message] = {}
    if last_ids:
        rows = (
            (await db.execute(select(Message).where(Message.id.in_(last_ids))))
            .scalars()
            .all()
        )
        last_by_match = {m.match_id: m for m in rows}

    unread_stmt = (
        select(Message.match_id, func.count())
        .where(
            Message.match_id.in_(match_ids),
            Message.sender_email != viewer_email,
            Message.read_at.is_(None),
        )
        .group_by(Message.match_id)
    )
    unread_by_match = dict((await db.execute(unread_stmt)).all())

    return {
        match_id: (last_by_match.get(match_id), unread_by_match.get(match_id, 0))
        for match_id in match_ids
    }

"""CRUD operations for items."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Item
from app.schemas import ItemCreate, ItemUpdate


def get(db: Session, item_id: int) -> Item | None:
    return db.get(Item, item_id)


def list_(
    db: Session,
    *,
    limit: int,
    offset: int,
    owner_id: int | None = None,
    q: str | None = None,
) -> tuple[list[Item], int]:
    """List items with optional filters.

    TEACHING NOTE — composable queries: SQLAlchemy statements are plain
    objects, so we build them up conditionally. Bound parameters (the
    ORM does this for us) mean user input is never interpolated into
    SQL — this is what makes the query injection-safe.
    """
    stmt = select(Item)
    if owner_id is not None:
        stmt = stmt.where(Item.owner_id == owner_id)
    if q:
        # ilike = case-insensitive LIKE (PostgreSQL). Fine for a demo;
        # at scale you would reach for postgres full-text search.
        stmt = stmt.where(Item.title.ilike(f"%{q}%"))

    # Count the *filtered* set by wrapping the same statement in a
    # subquery — keeping the count and the page guaranteed-consistent.
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    stmt = stmt.order_by(Item.id).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return items, total


def create(db: Session, data: ItemCreate, owner_id: int) -> Item:
    # owner_id comes from the URL path (via the endpoint), never from the
    # request body — see the note on ItemCreate.
    item = Item(**data.model_dump(), owner_id=owner_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item: Item, data: ItemUpdate) -> Item:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete(db: Session, item: Item) -> None:
    db.delete(item)
    db.commit()

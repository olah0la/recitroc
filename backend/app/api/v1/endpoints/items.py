"""Items endpoints — optional query-parameter filtering on display here."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import EmailStr

from app import crud
from app.api.deps import DbSession, Pagination
from app.schemas import ItemRead, ItemUpdate, Page

router = APIRouter(prefix="/items", tags=["items"])

ItemId = Annotated[int, Path(ge=1, description="Numeric ID of the item")]


@router.get("", response_model=Page[ItemRead], summary="List items")
def list_items(
    db: DbSession,
    page: Pagination,
    # TEACHING NOTE — optional query params: a `| None = None` default
    # makes the filter opt-in. Try it in the docs UI:
    #   GET /api/v1/items?q=lamp&owner_email=ada@example.com&limit=5
    # `min_length=1` stops `?q=` (empty string) from being treated as a
    # real search term.
    owner_email: Annotated[
        EmailStr | None, Query(description="Only items owned by this user")
    ] = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=200, description="Search in item titles"),
    ] = None,
) -> Page[ItemRead]:
    """List items, optionally filtered by owner and/or a title search."""
    items, total = crud.item.list_(
        db, limit=page.limit, offset=page.offset, owner_email=owner_email, q=q
    )
    return Page(
        items=[ItemRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{item_id}", response_model=ItemRead, summary="Get an item")
def get_item(item_id: ItemId, db: DbSession) -> ItemRead:
    item = crud.item.get(db, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    return item


@router.patch("/{item_id}", response_model=ItemRead, summary="Update an item")
def update_item(item_id: ItemId, payload: ItemUpdate, db: DbSession) -> ItemRead:
    item = crud.item.get(db, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    return crud.item.update(db, item, payload)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item",
)
def delete_item(item_id: ItemId, db: DbSession) -> None:
    item = crud.item.get(db, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    crud.item.delete(db, item)

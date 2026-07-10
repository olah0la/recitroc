"""Users endpoints — a tour of FastAPI's core features.

Concepts on display: path/query/body parameters, response_model,
status codes, HTTPException, dependency injection, nested routes.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app import crud
from app.api.deps import DbSession, Pagination
from app.schemas import (
    ItemCreate,
    ItemRead,
    Page,
    UserCreate,
    UserRead,
    UserReadWithItems,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])

# TEACHING NOTE — Annotated path params: `Path(ge=1)` rejects /users/0 and
# /users/-5 with an automatic 422 before the endpoint even runs, and
# `/users/abc` is already rejected by the `int` type itself.
UserId = Annotated[int, Path(ge=1, description="Numeric ID of the user")]


@router.post(
    "",
    response_model=UserRead,
    # 201 is the correct status for "a resource was created". FastAPI
    # defaults to 200 — always be explicit on writes.
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
def create_user(payload: UserCreate, db: DbSession) -> UserRead:
    """Create a new user.

    TEACHING NOTE — this docstring is user-facing: FastAPI renders it in
    the /docs page for this endpoint.

    Parameter roles are inferred from their types: `payload` is a Pydantic
    model, so FastAPI reads it from the JSON body (and returns a detailed
    422 if validation fails); `db` is a dependency.
    """
    # Check-then-insert is readable, but two requests can pass the check
    # simultaneously — the UNIQUE constraint on users.email is the real
    # guarantee. A production version would also catch IntegrityError.
    if crud.user.get_by_email(db, payload.email):
        # 409 Conflict = "the request is valid but collides with current
        # state". Don't use 400 for everything; status codes are API UX.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {payload.email!r} already exists.",
        )
    return crud.user.create(db, payload)


@router.get("", response_model=Page[UserRead], summary="List users")
def list_users(db: DbSession, page: Pagination) -> Page[UserRead]:
    """List users, paginated.

    TEACHING NOTE — response_model does double duty: it documents the
    response in OpenAPI *and* filters the output. If User grew a
    `hashed_password` column tomorrow, it still could never leak through
    this endpoint, because UserRead doesn't declare it.
    """
    users, total = crud.user.list_(db, limit=page.limit, offset=page.offset)
    return Page(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{user_id}", response_model=UserReadWithItems, summary="Get a user")
def get_user(user_id: UserId, db: DbSession) -> UserReadWithItems:
    """Fetch a single user, including their items."""
    user = crud.user.get_with_items(db, user_id)
    if user is None:
        # The CRUD layer returns None; translating that into an HTTP 404
        # is exactly the API layer's job.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.patch("/{user_id}", response_model=UserRead, summary="Update a user")
def update_user(user_id: UserId, payload: UserUpdate, db: DbSession) -> UserRead:
    """Partially update a user.

    TEACHING NOTE — PATCH vs PUT: PATCH applies only the fields present in
    the request; PUT replaces the whole resource. Partial-update schemas
    (all fields optional) + `exclude_unset` in the CRUD layer implement
    PATCH correctly.
    """
    user = crud.user.get(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if payload.email and payload.email != user.email:
        if crud.user.get_by_email(db, payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user with email {payload.email!r} already exists.",
            )
    return crud.user.update(db, user, payload)


@router.delete(
    "/{user_id}",
    # 204 means "done, and there is nothing to say" — the response has no
    # body, so there is no response_model either.
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user",
)
def delete_user(user_id: UserId, db: DbSession) -> None:
    """Delete a user and (via cascade) all of their items.

    TEACHING NOTE — DELETE is *idempotent* in effect (the row is gone
    either way), but we still 404 on a missing user: it tells clients
    they probably hold a stale ID, which is a bug worth surfacing.
    """
    user = crud.user.get(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    crud.user.delete(db, user)


# ---------------------------------------------------------------------------
# Nested route: items always belong to a user, and the URL encodes that.
# ---------------------------------------------------------------------------
@router.post(
    "/{user_id}/items",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    tags=["items"],  # shown under "items" in the docs despite living here
    summary="Create an item owned by a user",
)
def create_item_for_user(
    user_id: UserId, payload: ItemCreate, db: DbSession
) -> ItemRead:
    """Create an item owned by the given user.

    TEACHING NOTE — path + body together: `user_id` comes from the URL,
    `payload` from the JSON body. The owner is taken from the URL, so a
    client can never create an item on someone else's behalf by lying in
    the body.
    """
    if crud.user.get(db, user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return crud.item.create(db, payload, owner_id=user_id)

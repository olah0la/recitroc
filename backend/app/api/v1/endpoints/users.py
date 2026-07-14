"""Users endpoints — a tour of FastAPI's core features.

Concepts on display: path/query/body parameters, response_model,
status codes, HTTPException, dependency injection, nested routes.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import EmailStr

from app import crud
from app.api.deps import DbSession, Pagination
from app.schemas import Page, UserCreate, UserRead, UserReadWithPostings, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

# TEACHING NOTE — the user's email IS the primary key, so it is also the
# resource identifier in URLs (/users/ada@example.com — the client must
# URL-encode it). Typing the path param as EmailStr rejects /users/junk
# with an automatic 422 before the endpoint even runs.
UserEmail = Annotated[EmailStr, Path(description="Email of the user (URL-encoded)")]


def _ensure_username_free(db: DbSession, username: str | None) -> None:
    """409 if the username is taken. None (no username) is always free —
    the unique constraint ignores NULLs."""
    if username and crud.user.get_by_username(db, username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username {username!r} is already taken.",
        )


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
    # simultaneously — the PRIMARY KEY on users.email and the UNIQUE
    # constraint on username are the real guarantee. A production version
    # would also catch IntegrityError.
    if crud.user.get(db, payload.email):
        # 409 Conflict = "the request is valid but collides with current
        # state". Don't use 400 for everything; status codes are API UX.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {payload.email!r} already exists.",
        )
    _ensure_username_free(db, payload.username)
    return crud.user.create(db, payload)


@router.get("", response_model=Page[UserRead], summary="List users")
def list_users(db: DbSession, page: Pagination) -> Page[UserRead]:
    """List users, paginated.

    TEACHING NOTE — response_model does double duty: it documents the
    response in OpenAPI *and* filters the output. The User model DOES
    carry a `hashed_password` column, yet it can never leak through this
    endpoint, because UserRead doesn't declare it.
    """
    users, total = crud.user.list_(db, limit=page.limit, offset=page.offset)
    return Page(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{email}", response_model=UserReadWithPostings, summary="Get a user")
def get_user(email: UserEmail, db: DbSession) -> UserReadWithPostings:
    """Fetch a single user, including their active postings."""
    user = crud.user.get_with_postings(db, email)
    if user is None:
        # The CRUD layer returns None; translating that into an HTTP 404
        # is exactly the API layer's job.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.patch("/{email}", response_model=UserRead, summary="Update a user")
def update_user(email: UserEmail, payload: UserUpdate, db: DbSession) -> UserRead:
    """Partially update a user.

    TEACHING NOTE — PATCH vs PUT: PATCH applies only the fields present in
    the request; PUT replaces the whole resource. Partial-update schemas
    (all fields optional) + `exclude_unset` in the CRUD layer implement
    PATCH correctly.

    Changing the email here rewrites the user's PRIMARY KEY: the database
    cascades the new value into postings.owner_email (onupdate="CASCADE"),
    and the resource's URL changes — clients should follow the email in
    the response body.
    """
    user = crud.user.get(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if payload.email and payload.email != user.email:
        if crud.user.get(db, payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user with email {payload.email!r} already exists.",
            )
    if payload.username and payload.username != user.username:
        _ensure_username_free(db, payload.username)
    return crud.user.update(db, user, payload)


@router.delete(
    "/{email}",
    # 204 means "done, and there is nothing to say" — the response has no
    # body, so there is no response_model either.
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user",
)
def delete_user(email: UserEmail, db: DbSession) -> None:
    """Delete a user and (via cascade) all of their postings.

    TEACHING NOTE — DELETE is *idempotent* in effect (the row is gone
    either way), but we still 404 on a missing user: it tells clients
    they probably hold a stale identifier, which is a bug worth surfacing.
    """
    user = crud.user.get(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    crud.user.delete(db, user)

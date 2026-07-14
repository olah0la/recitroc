"""User schemas — the API's public contract for the users resource.

TEACHING NOTE — why schemas are separate from ORM models:
The database shape and the API shape are different concerns that evolve at
different speeds. Separate Pydantic schemas let us:
- hide internal columns from responses,
- accept a different shape on input (Create) than we return (Read),
- validate/normalize input before it ever touches the database.
One schema per *operation* is the pattern: Create, Update, Read.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.item import ItemRead


class UserBase(BaseModel):
    """Fields common to reading and writing. Others inherit from this."""

    # EmailStr rejects malformed addresses at the edge with a clear 422,
    # before any business logic runs.
    email: EmailStr
    # Field() attaches validation rules AND documentation — both show up
    # in the generated OpenAPI docs.
    full_name: str | None = Field(
        default=None, max_length=255, examples=["Ada Lovelace"]
    )


class UserCreate(UserBase):
    """Payload for POST /users and /auth/signup. `id`/timestamps are
    server-generated, so a client must not be able to send them — hence
    they don't exist here.

    TEACHING NOTE — the password lives ONLY on the Create schema: it is
    write-only by construction. There is no `password` on UserRead, and
    the model stores only `hashed_password`, so no code path can echo a
    plaintext password back. max_length=72 matches bcrypt's input limit
    (it silently truncates beyond 72 bytes — better to reject up front).
    """

    password: str = Field(min_length=8, max_length=72)
    is_active: bool = True


class UserUpdate(BaseModel):
    """Payload for PATCH /users/{id}.

    TEACHING NOTE — every field is optional: a PATCH sends only what
    changes. In the CRUD layer, `model_dump(exclude_unset=True)` is what
    distinguishes "field omitted" (don't touch it) from "field set to
    None" (clear it).
    """

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class UserRead(UserBase):
    """Shape returned to clients. Server-generated fields appear here."""

    # TEACHING NOTE — from_attributes=True lets Pydantic read data straight
    # from ORM objects (user.id, user.email, ...) instead of requiring a
    # dict. This is what allows endpoints to simply `return db_user` while
    # declaring `response_model=UserRead`.
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserReadWithItems(UserRead):
    """UserRead plus the user's items — used only where we deliberately
    load the relationship (see the GET /users/{id} endpoint)."""

    items: list[ItemRead] = []

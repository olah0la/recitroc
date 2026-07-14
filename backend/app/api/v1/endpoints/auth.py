"""Auth endpoints — signup, login, and "who am I".

TEACHING NOTE — the OAuth2 password flow in three requests:
1. POST /auth/signup   (JSON)  → account created
2. POST /auth/login    (FORM)  → {access_token, token_type}
3. GET  /auth/me       (Authorization: Bearer <token>) → the user

Everything else in the API that needs a user just declares the
CurrentUser dependency (see api/deps.py) — auth concerns live here and
there, never inside business endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.schemas import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
def signup(payload: UserCreate, db: DbSession) -> UserRead:
    """Register a new user.

    Reuses the users CRUD create (which hashes the password), so signup
    and the admin POST /users can never drift apart. The response is
    UserRead — the token is NOT included; the client logs in next. That
    keeps this endpoint idempotent-ish to retry and the login path single.
    """
    if crud.user.get(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {payload.email!r} already exists.",
        )
    if payload.username and crud.user.get_by_username(db, payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username {payload.username!r} is already taken.",
        )
    return crud.user.create(db, payload)


@router.post("/login", response_model=Token, summary="Log in, receive a token")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession
) -> Token:
    """Exchange email + password for a bearer token.

    TEACHING NOTE — OAuth2PasswordRequestForm reads FORM fields (hence the
    python-multipart dependency), and the spec names the identity field
    `username` even though we treat it as an email. One generic 401 covers
    unknown email, wrong password, and deactivated accounts alike — see
    crud.user.authenticate for why.
    """
    user = crud.user.authenticate(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # The subject is the user's email — the primary key — so resolving a
    # token back to a user is a single PK lookup (see deps.get_current_user).
    return Token(access_token=create_access_token(subject=user.email))


@router.get("/me", response_model=UserRead, summary="Get the current user")
def read_me(current_user: CurrentUser) -> UserRead:
    """Return the account behind the presented bearer token.

    The endpoint body is one line — all the work (extract token, verify
    signature, load user, reject stale accounts) happened in the
    CurrentUser dependency.
    """
    return current_user

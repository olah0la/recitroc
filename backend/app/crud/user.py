"""CRUD operations for users."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas import UserCreate, UserUpdate


def get(db: Session, email: str) -> User | None:
    """Fetch one user by primary key (their email).

    TEACHING NOTE — Session.get() is the fastest PK lookup: it can even
    skip the query entirely if the object is already in the session's
    identity map. Since the email IS the primary key, the old separate
    get-by-email query disappeared: identity lookup and email lookup are
    now the same operation. Returning `None` (instead of raising) keeps
    this layer HTTP-agnostic — deciding that "missing" means "404" is
    the API layer's job.
    """
    return db.get(User, email)


def get_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def get_with_items(db: Session, email: str) -> User | None:
    """Fetch one user with their items eagerly loaded.

    TEACHING NOTE — the N+1 problem: lazy loading (the default) would run
    one extra query per user the moment `.items` is touched. selectinload
    fetches all related items in a single second query. Make loading
    explicit where you *know* you need the relationship.
    """
    stmt = select(User).options(selectinload(User.items)).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def list_(db: Session, *, limit: int, offset: int) -> tuple[list[User], int]:
    """Return one page of users plus the total count.

    TEACHING NOTE — never return unbounded lists. A table with a million
    rows will happily OOM your process. LIMIT/OFFSET + a deterministic
    ORDER BY (paging without ordering returns rows in arbitrary,
    unstable order!) is the simplest correct pagination.
    (Named `list_` because `list` would shadow the Python builtin.)
    """
    total = db.execute(select(func.count()).select_from(User)).scalar_one()
    stmt = select(User).order_by(User.email).limit(limit).offset(offset)
    users = list(db.execute(stmt).scalars().all())
    return users, total


def create(db: Session, data: UserCreate) -> User:
    # TEACHING NOTE — the plaintext password is swapped for its hash at
    # the last possible moment before persistence; it never touches the
    # ORM object. `exclude={"password"}` matters: User has no `password`
    # attribute, and passing one would raise a TypeError.
    user = User(
        **data.model_dump(exclude={"password"}),
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    # TEACHING NOTE — commit() writes the transaction; refresh() re-reads
    # the row so server-generated values (created_at from the DB clock,
    # server_default booleans) are populated on our Python object before
    # we return it to the client.
    db.commit()
    db.refresh(user)
    return user


def update(db: Session, user: User, data: UserUpdate) -> User:
    """Partial update (PATCH semantics).

    TEACHING NOTE — exclude_unset=True is the whole trick: it dumps only
    the fields the client actually sent, so `{"first_name": null}` clears
    the name while omitting the key leaves it untouched.
    """
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def delete(db: Session, user: User) -> None:
    # ORM-level delete so the "delete-orphan" cascade on User.items runs.
    db.delete(user)
    db.commit()


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user if email+password are valid, else None.

    TEACHING NOTE — one None for every failure mode (unknown email, wrong
    password, deactivated account). The API layer turns it into a single
    generic 401; distinguishing the cases in the response would let an
    attacker probe which emails have accounts ("user enumeration").
    """
    user = get(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user

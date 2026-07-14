"""Password hashing and JWT access tokens.

TEACHING NOTE — the two halves of stateless auth:
1. *Hashing* (bcrypt): we never store the password, only a one-way hash.
   bcrypt is deliberately slow and embeds a per-password random salt, so
   a leaked database can't be reversed with a rainbow table.
2. *Tokens* (JWT): after a successful login we hand the client a signed
   claim ("user 42, valid until T"). Every later request proves identity
   by presenting it — no server-side session storage needed. The
   signature (HMAC with SECRET_KEY) makes it tamper-proof: change one
   character of the payload and verification fails.

This module is HTTP-agnostic on purpose (it returns None instead of
raising HTTPException) — translating "bad token" into a 401 is the API
layer's job, same rule as the CRUD layer.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    # gensalt() embeds a fresh random salt in every hash — hashing the
    # same password twice yields different strings, and that's correct:
    # checkpw() reads the salt back out of the stored hash.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        # An unparseable stored hash (e.g. the empty string that the
        # add-column migration backfilled for pre-auth rows) can never
        # match — treat it as a failed login, not a server error.
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT whose `sub` claim identifies the user.

    TEACHING NOTE — `sub` must be a *string* per RFC 7519, hence the str
    user id. `exp` must be timezone-aware UTC; pyjwt turns it into a Unix
    timestamp and will refuse expired tokens at decode time automatically.
    """
    if expires_minutes is None:
        expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Return the token's subject, or None if it is invalid or expired.

    TEACHING NOTE — always pass an explicit `algorithms` allowlist. Letting
    the token itself pick the algorithm is the classic JWT vulnerability
    (alg=none / HMAC-vs-RSA confusion attacks).
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        # One except clause covers every failure mode: bad signature,
        # expired, malformed, wrong algorithm. Callers get a single
        # "valid or not" answer and can't accidentally handle one case
        # more leniently than another.
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None

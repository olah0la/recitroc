"""Shared FastAPI dependencies.

TEACHING NOTE — dependency injection is FastAPI's superpower:
Anything an endpoint needs (a DB session, the current user, pagination
params) is declared as a parameter with `Depends(...)`. FastAPI resolves
the graph per request, caches shared dependencies within that request,
and — crucially for testing — lets you swap any dependency with
`app.dependency_overrides[get_db] = fake_db` without touching endpoint
code.
"""

from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request.

    TEACHING NOTE — `yield` dependencies have a setup/teardown lifecycle:
    everything before `yield` runs before the endpoint, everything after
    runs once the response is done — even if the endpoint raised. This
    `finally` guarantees the connection always goes back to the pool;
    leaking sessions is how apps die with "connection pool exhausted" at
    3am.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# TEACHING NOTE — Annotated aliases: instead of repeating
# `db: Session = Depends(get_db)` in every endpoint, define the annotated
# type once and reuse it. Same behavior, less noise, one place to change.
DbSession = Annotated[Session, Depends(get_db)]


@dataclass
class PaginationParams:
    """Reusable, validated pagination query parameters.

    TEACHING NOTE — a *class* used as a dependency: FastAPI reads its
    __init__ signature just like a function's. `Query(ge=..., le=...)`
    both validates (400s a limit of 5000) and documents the parameters
    in the OpenAPI schema. The `le=100` cap is a guardrail: clients
    cannot request unbounded pages no matter what they send.
    """

    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20
    offset: Annotated[int, Query(ge=0, description="Rows to skip")] = 0


Pagination = Annotated[PaginationParams, Depends()]

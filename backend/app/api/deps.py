"""Shared FastAPI dependencies.

TEACHING NOTE — dependency injection is FastAPI's superpower:
Anything an endpoint needs (a DB session, the current user, pagination
params) is declared as a parameter with `Depends(...)`. FastAPI resolves
the graph per request, caches shared dependencies within that request,
and — crucially for testing — lets you swap any dependency with
`app.dependency_overrides[get_db] = fake_db` without touching endpoint
code.
"""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.async_session import AsyncSessionLocal
from app.db.session import SessionLocal
from app.services.geo import GeoClient


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


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async twin of get_db, for `async def` endpoints.

    TEACHING NOTE — `async with` replaces try/finally: the session context
    manager closes the session (returning the asyncpg connection to the
    pool) however the request ends. FastAPI treats async and sync
    dependencies uniformly — endpoints just declare what they need.
    Rule: an `async def` endpoint must use THIS dependency; handing it a
    sync Session would block the event loop on every query.
    """
    async with AsyncSessionLocal() as session:
        yield session


AsyncDbSession = Annotated[AsyncSession, Depends(get_async_db)]


def get_geo_client(request: Request) -> GeoClient:
    """Hand endpoints the shared GeoClient created in the app lifespan.

    TEACHING NOTE — app.state is FastAPI's home for process-wide,
    lifespan-managed objects (shared HTTP clients, ML models, queues).
    Exposing it through a dependency (instead of importing a global)
    keeps endpoints testable: tests override THIS function with a fake
    and never touch the network.
    """
    return request.app.state.geo_client


GeoDep = Annotated[GeoClient, Depends(get_geo_client)]


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

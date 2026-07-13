"""Shared pytest fixtures.

TEACHING NOTE — the testing strategy here:
1. Swap postgres for SQLite — tests run anywhere, in milliseconds, with
   zero setup. (Trade-off: SQLite won't catch postgres-specific behavior;
   a CI job against real postgres via `make test` in the container
   complements this.)
2. Use `app.dependency_overrides` to replace the real dependencies:
   sync DB, async DB, AND the external geo service. The endpoints don't
   change at all — that's the payoff of dependency injection. Note that
   no mocking library appears anywhere in these tests.
3. Give every test a FRESH database so tests can't leak state into each
   other. Order-dependent tests are flaky tests.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.api.deps import get_async_db, get_db, get_geo_client
from app.db.base import Base
from app.main import app
from app.services.geo import AirQuality, CurrentWeather, GeoLocation

# --- sync test database (users/items endpoints) ---------------------------
# StaticPool + check_same_thread=False make one in-memory SQLite database
# shareable across the test and the TestClient's request threads. Without
# StaticPool every connection would get its OWN empty in-memory database.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    # Tests may use create_all because the schema is disposable; the real
    # database's schema is owned by Alembic migrations.
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# --- async test database (listings endpoints) ------------------------------
async def _create_all(async_engine: AsyncEngine) -> None:
    async with async_engine.begin() as conn:
        # run_sync bridges to sync-only APIs like metadata.create_all.
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture()
def async_engine(tmp_path) -> Generator[AsyncEngine, None, None]:
    """A file-based async SQLite engine, unique per test.

    TEACHING NOTE — two traps this setup avoids:
    - aiosqlite connections are bound to the event loop that created
      them. NullPool opens a fresh connection per session, always in the
      *current* loop, so schema setup (one loop) and requests (the
      TestClient's loop) never share a connection.
    - a FILE database (pytest's tmp_path is a fresh temp dir per test)
      is visible to all connections, unlike `:memory:` which is
      per-connection.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db", poolclass=NullPool
    )
    asyncio.run(_create_all(engine))
    yield engine
    asyncio.run(engine.dispose())


# --- fake external service --------------------------------------------------
class FakeGeoClient:
    """In-memory stand-in for services.geo.GeoClient.

    TEACHING NOTE — a hand-written fake beats patching: it implements the
    same interface (same async methods, same return types), so the
    endpoints can't tell the difference, and tests stay readable. It also
    *records* calls so tests can assert behavior like "PATCHing only the
    title must not re-geocode".
    """

    def __init__(self) -> None:
        self.geocode_calls: list[str] = []
        self.fail = False  # set True in a test to simulate provider outage

    def _maybe_fail(self) -> None:
        if self.fail:
            raise httpx.ConnectError("simulated provider outage")

    async def geocode(self, city: str) -> GeoLocation | None:
        self._maybe_fail()
        self.geocode_calls.append(city)
        if city.lower() == "atlantis":  # the city that never resolves
            return None
        return GeoLocation(name=city, country="Testland", latitude=1.25, longitude=2.5)

    async def current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        self._maybe_fail()
        return CurrentWeather(temperature_c=21.0, wind_speed_kmh=10.0, weather_code=2)

    async def air_quality(self, latitude: float, longitude: float) -> AirQuality:
        self._maybe_fail()
        return AirQuality(european_aqi=15)


@pytest.fixture()
def geo() -> FakeGeoClient:
    return FakeGeoClient()


# --- the app client ---------------------------------------------------------
@pytest.fixture()
def client(
    db: Session, async_engine: AsyncEngine, geo: FakeGeoClient
) -> Generator[TestClient, None, None]:
    """A TestClient with every external dependency swapped for a test double."""
    TestingAsyncSessionLocal = async_sessionmaker(
        bind=async_engine, autoflush=False, expire_on_commit=False
    )

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    async def override_get_async_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestingAsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db
    app.dependency_overrides[get_geo_client] = lambda: geo

    # TestClient lets us call the app in-process — no server, no network.
    # Entering the context manager also runs the lifespan (so async
    # endpoints behave exactly as in production).
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

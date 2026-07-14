"""Shared pytest fixtures.

TEACHING NOTE — the testing strategy here:
1. Swap postgres for SQLite — tests run anywhere, in milliseconds, with
   zero setup. (Trade-off: SQLite won't catch postgres-specific behavior;
   a CI job against real postgres via `make test` in the container
   complements this.)
2. ONE database file per test, shared by BOTH stacks. Postings (async
   stack) hold a foreign key to users (sync stack), so the two engines
   must see the same data — exactly like production, where both engines
   point at the same postgres. A file in pytest's tmp_path (unique per
   test) is visible to every connection, unlike `:memory:` which is
   per-connection; a fresh file per test also guarantees isolation.
3. Use `app.dependency_overrides` to replace the real dependencies:
   sync DB, async DB, AND the external geo service. The endpoints don't
   change at all — that's the payoff of dependency injection. Note that
   no mocking library appears anywhere in these tests.
"""

from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.api.deps import get_async_db, get_db, get_geo_client
from app.db.base import Base
from app.main import app
from app.services.geo import AirQuality, CurrentWeather, GeoLocation


@pytest.fixture()
def sync_engine(tmp_path) -> Generator[Engine, None, None]:
    """A file-based SQLite engine, unique per test; owns the schema setup."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    # Tests may use create_all because the schema is disposable; the real
    # database's schema is owned by Alembic migrations.
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(sync_engine: Engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(
        bind=sync_engine, autoflush=False, expire_on_commit=False
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def async_session_factory(tmp_path) -> async_sessionmaker[AsyncSession]:
    """Async sessions on the SAME database file as the sync engine.

    TEACHING NOTE — a trap this setup avoids: aiosqlite connections are
    bound to the event loop that created them. NullPool opens a fresh
    connection per session, always in the *current* loop, so no
    connection ever crosses between event loops.
    """
    async_engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db", poolclass=NullPool
    )
    return async_sessionmaker(
        bind=async_engine, autoflush=False, expire_on_commit=False
    )


# --- fake external service --------------------------------------------------
# Real coordinates for a few cities so proximity tests measure REAL
# distances: Potsdam is ~27 km from Berlin, Hamburg ~255 km.
FAKE_CITIES = {
    "berlin": GeoLocation("Berlin", "Germany", 52.52437, 13.41053),
    "potsdam": GeoLocation("Potsdam", "Germany", 52.39886, 13.06566),
    "hamburg": GeoLocation("Hamburg", "Germany", 53.55073, 9.99302),
}


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
        if city.lower() in FAKE_CITIES:
            return FAKE_CITIES[city.lower()]
        return GeoLocation(name=city, country="Testland", latitude=1.25, longitude=2.5)

    async def current_weather(
        self, latitude: float, longitude: float
    ) -> CurrentWeather:
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
    db: Session,
    async_session_factory: async_sessionmaker[AsyncSession],
    geo: FakeGeoClient,
) -> Generator[TestClient, None, None]:
    """A TestClient with every external dependency swapped for a test double."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    async def override_get_async_db() -> AsyncGenerator[AsyncSession, None]:
        # The long-lived sync session may hold pending state and stale
        # caches; committing before and expiring after keeps the two
        # stacks agreeing on what the shared database file contains.
        db.commit()
        async with async_session_factory() as session:
            yield session
        db.expire_all()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db
    app.dependency_overrides[get_geo_client] = lambda: geo

    # TestClient lets us call the app in-process — no server, no network.
    # Entering the context manager also runs the lifespan (so async
    # endpoints behave exactly as in production).
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

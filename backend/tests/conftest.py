"""Shared pytest fixtures.

TEACHING NOTE — the testing strategy here:
1. Swap postgres for an in-memory SQLite database — tests run anywhere,
   in milliseconds, with zero setup. (Trade-off: SQLite won't catch
   postgres-specific behavior; a CI job against real postgres via
   `make test` in the container complements this.)
2. Use `app.dependency_overrides` to replace the real `get_db` dependency.
   The endpoints don't change at all — that's the payoff of dependency
   injection.
3. Give every test a FRESH schema (create_all/drop_all) so tests can't
   leak state into each other. Order-dependent tests are flaky tests.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app

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


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    """A TestClient whose DB dependency is overridden to use SQLite."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    # TestClient lets us call the app in-process — no server, no network.
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

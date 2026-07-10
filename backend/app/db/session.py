"""Database engine and session factory (synchronous).

TEACHING NOTE — engine vs. session:
- The *engine* is created once per process. It owns a pool of TCP
  connections to PostgreSQL.
- A *session* is short-lived: one per request. It checks a connection out
  of the pool, wraps your work in a transaction, and returns the
  connection when closed.
Never share one session across requests — sessions are not thread-safe.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    # pool_pre_ping issues a lightweight "SELECT 1" before reusing a pooled
    # connection, transparently replacing connections the database closed
    # (e.g. after a postgres restart). Cheap insurance in long-running apps.
    pool_pre_ping=True,
    # echo=True,  # uncomment to log every SQL statement — great for learning!
)

# TEACHING NOTE — sessionmaker is a *factory*: calling SessionLocal() gives
# a new Session. autoflush=False means SQLAlchemy only writes pending
# changes when we explicitly flush/commit, which makes behavior predictable.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

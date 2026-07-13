"""Async database engine and session factory.

TEACHING NOTE — sync vs async, when does async actually help?
A sync endpoint HOLDS ITS WORKER THREAD hostage while waiting on I/O
(FastAPI runs `def` endpoints in a threadpool, default ~40 threads).
An async endpoint *releases the event loop* at every `await`, so one
process can juggle thousands of concurrent waits. Async wins when the
work is I/O-bound and concurrent (calling external APIs, many slow
queries); it does NOT make CPU-bound work faster — and one accidental
blocking call (e.g. `requests.get`, `time.sleep`) inside an `async def`
freezes the ENTIRE event loop for everyone. That is the trade you make.

Both stacks coexist in this app on purpose:
  sync:  api -> crud.user/item  -> Session      (psycopg2 pool)
  async: api -> crud.listing    -> AsyncSession (asyncpg pool)
Pick per-resource, never mix inside one request.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_pre_ping=True,
)

# Same knobs as the sync factory (see db/session.py). expire_on_commit=False
# matters even more here: with it on, touching an attribute after commit
# would trigger a lazy refresh — which in async raises MissingGreenlet
# instead of silently querying.
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, autoflush=False, expire_on_commit=False
)

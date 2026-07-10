"""Application entry point.

Layered architecture, dependencies pointing inward only:

    api (HTTP)  ->  crud (data access)  ->  models (ORM)  ->  db (engine)
         \\----------  schemas (contracts)  ----------/

`main.py` only assembles the app; it contains no business logic.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook.

    TEACHING NOTE — everything before `yield` runs once at startup,
    everything after runs at shutdown (close clients, flush queues...).
    Note what we do NOT do here: no `Base.metadata.create_all()`. The
    schema is owned by Alembic migrations (`alembic upgrade head` runs
    before the server starts — see compose.yaml). create_all can only
    add tables; it can never alter or migrate existing ones.
    """
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    # root_path tells FastAPI it lives behind a proxy that strips /api,
    # so the interactive docs at http://recitroc.localhost/api/docs work.
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
)

# All resource routes live under a version prefix: /v1/users, /v1/items...
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Health is also exposed unversioned (/health): infrastructure probes
# (compose healthchecks, load balancers) shouldn't break on an API bump.
app.include_router(health.router, include_in_schema=False)

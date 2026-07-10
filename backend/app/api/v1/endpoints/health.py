"""Health endpoints — used by humans, load balancers, and compose healthchecks."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    """Cheap check that the process is up. Deliberately touches nothing."""
    return {"status": "ok"}


@router.get("/health/db", summary="Readiness probe")
def health_db(db: DbSession) -> dict[str, str]:
    """Verify we can actually reach the database.

    TEACHING NOTE — liveness vs readiness: "the process runs" and "the
    process can do useful work" are different questions. Orchestrators
    use the second to decide whether to route traffic to you.
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}

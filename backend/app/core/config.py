"""Application configuration.

TEACHING NOTE — 12-factor config:
Configuration (DB credentials, hostnames, feature flags) must come from the
*environment*, never be hardcoded. `pydantic-settings` reads environment
variables (and optionally a `.env` file), validates their types, and fails
fast at startup if something required is missing or malformed. A typo in
DATABASE_URL should crash the app at boot — not at the first query.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `env_file` is a convenience for running outside Docker; inside Docker
    # the variables come from compose.yaml. Real env vars always win over
    # the .env file. `extra="ignore"` lets the same .env hold frontend vars.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Recitroc API"

    # nginx-proxy strips the `/api` prefix before forwarding to us
    # (VIRTUAL_PATH=/api/ + VIRTUAL_DEST=/). ROOT_PATH tells FastAPI it is
    # served *behind* that prefix so the generated OpenAPI docs build
    # correct URLs (http://recitroc.localhost/api/docs).
    ROOT_PATH: str = "/api"

    # Versioning the API in the path (/v1/...) lets us ship breaking changes
    # later under /v2 while old clients keep working.
    API_V1_PREFIX: str = "/v1"

    # TEACHING NOTE — the URL scheme selects the driver:
    # "postgresql+psycopg2://" = synchronous driver (this project),
    # "postgresql+asyncpg://"  = what you would use for an async stack.
    # `db` is the hostname of the postgres service on the compose network.
    DATABASE_URL: str = "postgresql+psycopg2://recitroc:recitroc@db:5432/recitroc"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    TEACHING NOTE — `lru_cache` makes this a lazy singleton: the environment
    is parsed once, and everyone shares the same object. Wrapping it in a
    function (instead of a module-level `settings = Settings()`) also lets
    tests override configuration cleanly via `get_settings.cache_clear()`
    or FastAPI dependency overrides.
    """
    return Settings()


# Convenience module-level handle for non-FastAPI code (e.g. alembic/env.py).
settings = get_settings()

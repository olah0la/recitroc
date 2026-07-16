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
    # "postgresql+psycopg2://" = synchronous driver,
    # "postgresql+asyncpg://"  = asynchronous driver.
    # `db` is the hostname of the postgres service on the compose network.
    DATABASE_URL: str = "postgresql+psycopg2://recitroc:recitroc@db:5432/recitroc"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """The same database, addressed through the async driver.

        TEACHING NOTE — deriving instead of duplicating: one env var
        configures both stacks, so they can never point at different
        databases by accident.
        """
        return self.DATABASE_URL.replace("+psycopg2", "+asyncpg")

    # --- Auth ---
    # TEACHING NOTE — the SECRET_KEY signs every JWT: whoever knows it can
    # mint a token for ANY user. The default below exists only so `make dev`
    # works out of the box; any real deployment MUST override it via the
    # environment (generate one with: openssl rand -hex 32). Rotating the
    # key instantly invalidates all outstanding tokens — sometimes that's
    # a feature.
    SECRET_KEY: str = "dev-only-secret-do-not-use-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day; short-lived by design

    # --- Deck scoring (services/matching.py) ---
    # Weights are CONFIG, not code: tuning the ranking must never need a
    # deploy. They should sum to ~1.0 so scores stay comparable over time.
    MATCH_WEIGHT_NEED_OVERLAP: float = 0.4
    MATCH_WEIGHT_RECIPROCITY: float = 0.3
    MATCH_WEIGHT_PROXIMITY: float = 0.2
    MATCH_WEIGHT_FRESHNESS: float = 0.1
    # How many nearby candidates are scored per deck fetch (the SQL
    # prefilter's LIMIT). Bounds the Python scoring work per request.
    DECK_CANDIDATE_POOL: int = 100

    @property
    def MATCH_WEIGHTS(self) -> tuple[float, float, float, float]:
        return (
            self.MATCH_WEIGHT_NEED_OVERLAP,
            self.MATCH_WEIGHT_RECIPROCITY,
            self.MATCH_WEIGHT_PROXIMITY,
            self.MATCH_WEIGHT_FRESHNESS,
        )

    # External services the app talks to. URLs are configuration, not
    # code: staging can point at a mock, and no deploy is needed if a
    # provider changes hosts. Open-Meteo is free and needs no API key.
    GEOCODING_API_URL: str = "https://geocoding-api.open-meteo.com/v1"
    WEATHER_API_URL: str = "https://api.open-meteo.com/v1"
    AIR_QUALITY_API_URL: str = "https://air-quality-api.open-meteo.com/v1"


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

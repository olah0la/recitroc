"""Alembic environment — the glue between Alembic and our application."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base

# TEACHING NOTE — this import looks unused, but it is load-bearing:
# importing app.models registers every table on Base.metadata. Without it,
# autogenerate sees an "empty" application and emits drop_table for
# everything. (The `# noqa: F401` tells the linter it's intentional.)
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the database URL from the application settings (i.e. from the
# environment) so alembic.ini never holds credentials.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# The metadata autogenerate compares against the live database.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """'Offline' mode: emit the SQL as a script instead of executing it.

    TEACHING NOTE — `alembic upgrade head --sql` uses this path. Handy when
    a DBA must review/apply the SQL manually in a locked-down production.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """'Online' mode: connect to the database and run migrations in place."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # compare_type=True makes autogenerate also detect column TYPE
            # changes (e.g. String(50) -> String(255)), not just
            # added/removed tables and columns.
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

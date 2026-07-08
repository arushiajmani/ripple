"""Alembic migration runtime — connects ORM models to the migration engine.

When you run `alembic upgrade head` or `alembic revision --autogenerate`:
  1. This file loads `Base.metadata` (all tables from app.db.models)
  2. Overrides the placeholder URL in alembic.ini with `settings.database_url`
  3. Runs migrations online (live DB connection) or offline (SQL script only)

The `import app.db.models` line is required even though the symbol is unused:
it registers every table on `Base.metadata` before Alembic inspects it.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base
from app.db import models  # noqa: F401 — register ORM tables on Base.metadata

config = context.config
# Real URL comes from env; alembic.ini only holds a placeholder
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (alembic upgrade head --sql)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live PostgreSQL database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

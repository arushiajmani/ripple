"""Unit tests for the ORM schema definition (no live database required).

These tests verify that SQLAlchemy metadata matches the SRS table list and
that key constraints (foreign keys, composite primary keys) are wired correctly.
They do NOT run migrations — use `alembic upgrade head` against Postgres for that.
"""

from sqlalchemy import inspect

from app.database import Base
from app.db.models import SCHEMA_TABLES


def test_schema_tables_registered() -> None:
    """Every SRS table is registered on Base.metadata — nothing missing or extra."""
    assert set(Base.metadata.tables) == set(SCHEMA_TABLES)


def test_schema_foreign_keys() -> None:
    """Spot-check FK targets and cycle_members composite PK match the SRS."""
    tables = Base.metadata.tables

    jobs_fks = {fk.target_fullname for fk in tables["analysis_jobs"].foreign_keys}
    assert jobs_fks == {"repositories.id"}

    files_fks = {fk.target_fullname for fk in tables["files"].foreign_keys}
    assert files_fks == {"analysis_jobs.id"}

    deps_fks = {fk.target_fullname for fk in tables["dependencies"].foreign_keys}
    assert deps_fks == {"analysis_jobs.id", "files.id"}

    cycle_member_pks = {col.name for col in inspect(tables["cycle_members"]).primary_key}
    assert cycle_member_pks == {"cycle_id", "position"}

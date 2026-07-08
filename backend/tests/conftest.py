"""Shared pytest fixtures for database-backed tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.main import app
from app.pipeline.store import AnalysisStore


def _postgres_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_available() -> bool:
    return _postgres_available()


@pytest.fixture
def db_session(postgres_available: bool) -> Generator[Session, None, None]:
    if not postgres_available:
        pytest.skip("PostgreSQL not available (start with: docker compose up -d db)")

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def ingestion_base_dir(tmp_path: Path) -> Path:
    return tmp_path / "ripple"


@pytest.fixture
def client(ingestion_base_dir: Path, db_session: Session) -> Generator[TestClient, None, None]:
    from app.database import get_db

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.state.ingestion_base_dir = ingestion_base_dir
    app.state.analysis_store = AnalysisStore()
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
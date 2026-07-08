"""SQLAlchemy engine, session factory, and FastAPI dependency.

This is the low-level database wiring layer:
  - `engine` / `SessionLocal` — create DB connections and ORM sessions
  - `Base` — declarative base that all ORM models in `app.db.models` inherit
  - `get_db` — FastAPI dependency that yields a session per request and closes it

Alembic imports `Base.metadata` from here to diff models against the live DB.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared metadata registry for every table defined in app.db.models."""


def get_db() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session per HTTP request (use via Depends(get_db))."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

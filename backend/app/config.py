"""Application settings loaded from environment variables.

Reads a `.env` file (if present) and exposes a single `settings` object used
across the backend. Docker Compose sets `DATABASE_URL`, `TEMP_DIR`, and
`MAX_REPO_SIZE_MB` for the backend service; local dev falls back to defaults
below when those vars are unset.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # PostgreSQL connection string — overridden by docker-compose / .env
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://ripple:ripple@localhost:5432/ripple",
    )
    # Scratch space for zip extraction and git clones during ingestion
    temp_dir: str = os.getenv("TEMP_DIR", "/tmp/ripple")
    max_repo_size_mb: int = int(os.getenv("MAX_REPO_SIZE_MB", "100"))


# Import as `from app.config import settings` — one shared config instance
settings = Settings()

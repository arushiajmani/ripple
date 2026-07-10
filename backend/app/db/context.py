"""Metadata for persisting an analysis run to PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass

import uuid


@dataclass(frozen=True)
class RepositoryPersistContext:
    """Identity fields for the ``repositories`` row tied to one analyze request."""

    source: str  # "zip" | "github"
    name: str
    owner: str | None = None
    repo_name: str | None = None
    branch: str | None = None
    file_hash: str | None = None


@dataclass(frozen=True)
class PersistResult:
    """IDs returned after writing a completed analysis to PostgreSQL."""

    repository_id: uuid.UUID
    job_id: uuid.UUID

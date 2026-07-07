"""Ingestion service interface."""

from __future__ import annotations

from typing import Protocol

from app.ingestion.models import RepositoryHandle


class IngestionServiceProtocol(Protocol):
    """Contract for bringing external sources onto local disk for analysis."""

    def ingest_zip_bytes(
        self,
        data: bytes,
        *,
        job_id: str | None = None,
    ) -> RepositoryHandle:
        """Materialize an uploaded zip archive to a job directory."""
        ...

    def ingest_github(
        self,
        github_url: str,
        *,
        job_id: str | None = None,
    ) -> RepositoryHandle:
        """Clone a public GitHub repository to a job directory."""
        ...

    def cleanup(self, job: RepositoryHandle | str) -> None:
        """Remove the on-disk job directory."""
        ...

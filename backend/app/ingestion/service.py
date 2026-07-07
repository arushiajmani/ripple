"""Unified ingestion facade — zip uploads and GitHub clones to temp job dirs.

Every ingestion path returns a :class:`~app.ingestion.models.RepositoryHandle`
whose ``local_path`` is the directory the analysis pipeline should consume.
How that directory was produced is invisible to downstream stages.
"""

from __future__ import annotations

from pathlib import Path

from app.ingestion.github import GitCloner, GitHubIngestion, GitRemoteChecker
from app.ingestion.models import IngestionResult, RepositoryHandle
from app.ingestion.protocol import IngestionServiceProtocol
from app.ingestion.zip import ZipIngestion

DEFAULT_BASE_DIR = Path("/tmp/ripple")


class IngestionService:
    """Bring external sources (zip archives, GitHub URLs) onto local disk."""

    def __init__(
        self,
        base_dir: Path | str = DEFAULT_BASE_DIR,
        *,
        remote_checker: GitRemoteChecker | None = None,
        cloner: GitCloner | None = None,
    ) -> None:
        root = Path(base_dir)
        self._zip = ZipIngestion(root)
        self._github = GitHubIngestion(
            root,
            remote_checker=remote_checker,
            cloner=cloner,
        )

    def ingest_zip(
        self,
        zip_path: str | Path,
        *,
        job_id: str | None = None,
    ) -> RepositoryHandle:
        """Extract ``zip_path`` to ``{base_dir}/{job_id}/`` and return the job paths."""
        return self._zip.ingest_path(zip_path, job_id=job_id)

    def ingest_zip_bytes(
        self,
        data: bytes,
        *,
        job_id: str | None = None,
        name: str = "",
    ) -> RepositoryHandle:
        """Extract zip bytes (e.g. from an HTTP upload) to a new job directory."""
        return self._zip.ingest_bytes(data, job_id=job_id, name=name)

    def ingest_github(
        self,
        github_url: str,
        *,
        job_id: str | None = None,
    ) -> RepositoryHandle:
        """Clone a public GitHub repository to a new job directory."""
        return self._github.ingest(github_url, job_id=job_id)

    def cleanup(self, job: RepositoryHandle | str) -> None:
        """Remove the on-disk job directory."""
        job_id = job.job_id if isinstance(job, RepositoryHandle) else job
        self._zip.cleanup(job_id)
        self._github.cleanup(job_id)


__all__ = [
    "DEFAULT_BASE_DIR",
    "IngestionResult",
    "IngestionService",
    "IngestionServiceProtocol",
    "RepositoryHandle",
]

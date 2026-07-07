"""GitHub repository cloning."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Protocol

from app.ingestion.exceptions import CloneError, RepositoryNotFoundError
from app.ingestion.models import RepositoryHandle
from app.ingestion.validation import ParsedGitHubUrl, parse_github_url

DEFAULT_CLONE_TIMEOUT_SECONDS = 300


class GitRemoteChecker(Protocol):
    """Check whether a remote repository is reachable."""

    def repo_exists(self, clone_url: str) -> bool:
        ...


class GitCloner(Protocol):
    """Clone a remote repository to a local directory."""

    def clone(self, clone_url: str, dest: Path) -> None:
        ...


class SubprocessGitRemoteChecker:
    """Use ``git ls-remote`` to verify a public repository exists."""

    def repo_exists(self, clone_url: str) -> bool:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", clone_url],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0


class SubprocessGitCloner:
    """Shallow-clone a repository with ``git clone --depth 1``."""

    def __init__(self, *, timeout_seconds: int = DEFAULT_CLONE_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds

    def clone(self, clone_url: str, dest: Path) -> None:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(dest)],
            capture_output=True,
            text=True,
            timeout=self._timeout_seconds,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "git clone failed").strip()
            raise CloneError(detail)


class GitHubIngestion:
    """Clone public GitHub repositories to ``{base_dir}/{job_id}/``."""

    def __init__(
        self,
        base_dir: Path,
        *,
        remote_checker: GitRemoteChecker | None = None,
        cloner: GitCloner | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._remote_checker = remote_checker or SubprocessGitRemoteChecker()
        self._cloner = cloner or SubprocessGitCloner()

    def ingest(
        self,
        github_url: str,
        *,
        job_id: str | None = None,
    ) -> RepositoryHandle:
        parsed = parse_github_url(github_url)
        if not self._remote_checker.repo_exists(parsed.clone_url):
            raise RepositoryNotFoundError(
                f"GitHub repository not found or not accessible: {parsed.display_name}"
            )

        job = job_id or str(uuid.uuid4())
        dest = self._job_dir(job)
        dest.mkdir(parents=True, exist_ok=False)

        try:
            self._cloner.clone(parsed.clone_url, dest)
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            raise

        return RepositoryHandle(
            job_id=job,
            local_path=dest,
            source="github",
            name=parsed.display_name,
        )

    def cleanup(self, job_id: str) -> None:
        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)

    def _job_dir(self, job_id: str) -> Path:
        return self._base_dir / job_id

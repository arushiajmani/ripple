"""GitHub ingestion tests — URL validation, mocked clone, and one live integration test.

Run from backend/:
    PYTHONPATH=. pytest tests/test_github_ingestion.py -v
    PYTHONPATH=. pytest tests/test_github_ingestion.py -v -m integration
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.ingestion import (
    CloneError,
    IngestionService,
    InvalidGitHubUrlError,
    RepositoryNotFoundError,
    parse_github_url,
)
from app.ingestion.github import GitHubIngestion
from app.pipeline import AnalysisPipeline

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"
INTEGRATION_REPO_URL = "https://github.com/pypa/sampleproject"
INTEGRATION_REPO_PYTHON_FILE = "src/sample/__init__.py"


class FakeRemoteChecker:
    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists
        self.checked_urls: list[str] = []

    def repo_exists(self, clone_url: str) -> bool:
        self.checked_urls.append(clone_url)
        return self.exists


class FakeCloner:
    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir
        self.calls: list[tuple[str, Path]] = []

    def clone(self, clone_url: str, dest: Path) -> None:
        self.calls.append((clone_url, dest))
        shutil.copytree(self.source_dir, dest, dirs_exist_ok=True)


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path / "ripple"


@pytest.fixture
def fake_checker() -> FakeRemoteChecker:
    return FakeRemoteChecker(exists=True)


@pytest.fixture
def fake_cloner() -> FakeCloner:
    return FakeCloner(FIXTURE_ROOT)


@pytest.fixture
def github_service(
    base_dir: Path,
    fake_checker: FakeRemoteChecker,
    fake_cloner: FakeCloner,
) -> IngestionService:
    return IngestionService(
        base_dir=base_dir,
        remote_checker=fake_checker,
        cloner=fake_cloner,
    )


@pytest.mark.parametrize(
    ("url", "owner", "repo"),
    [
        ("https://github.com/octocat/Hello-World", "octocat", "Hello-World"),
        ("https://github.com/octocat/Hello-World.git", "octocat", "Hello-World"),
        ("github.com/octocat/Hello-World", "octocat", "Hello-World"),
        ("https://www.github.com/psf/requests", "psf", "requests"),
    ],
)
def test_parse_github_url_accepts_common_forms(
    url: str, owner: str, repo: str
) -> None:
    parsed = parse_github_url(url)
    assert parsed.owner == owner
    assert parsed.repo == repo
    assert parsed.clone_url == f"https://github.com/{owner}/{repo}.git"
    assert parsed.display_name == f"{owner}/{repo}"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://gitlab.com/owner/repo",
        "https://github.com/only-owner",
        "ftp://github.com/owner/repo",
        "https://github.com/",
        "https://example.com/owner/repo",
    ],
)
def test_parse_github_url_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidGitHubUrlError):
        parse_github_url(url)


def test_ingest_github_clones_to_job_directory(
    github_service: IngestionService,
    base_dir: Path,
    fake_checker: FakeRemoteChecker,
    fake_cloner: FakeCloner,
) -> None:
    result = github_service.ingest_github(
        "https://github.com/example/mini-repo",
        job_id="gh-job",
    )

    assert result.job_id == "gh-job"
    assert result.local_path == base_dir / "gh-job"
    assert result.source == "github"
    assert result.name == "example/mini-repo"
    assert fake_checker.checked_urls == ["https://github.com/example/mini-repo.git"]
    assert fake_cloner.calls == [
        ("https://github.com/example/mini-repo.git", base_dir / "gh-job")
    ]
    assert "myapp/models.py" in result.python_files


def test_ingest_github_rejects_missing_repository(
    base_dir: Path, fake_cloner: FakeCloner
) -> None:
    service = IngestionService(
        base_dir=base_dir,
        remote_checker=FakeRemoteChecker(exists=False),
        cloner=fake_cloner,
    )

    with pytest.raises(RepositoryNotFoundError, match="not found"):
        service.ingest_github("https://github.com/missing/norepo")

    assert not base_dir.exists() or not any(base_dir.iterdir())
    assert fake_cloner.calls == []


def test_ingest_github_removes_partial_directory_on_clone_failure(
    base_dir: Path,
) -> None:
    class FailingCloner:
        def clone(self, clone_url: str, dest: Path) -> None:
            (dest / "partial.txt").write_text("partial")
            raise CloneError("clone failed")

    service = IngestionService(
        base_dir=base_dir,
        remote_checker=FakeRemoteChecker(exists=True),
        cloner=FailingCloner(),
    )

    with pytest.raises(CloneError, match="clone failed"):
        service.ingest_github("https://github.com/example/repo", job_id="partial")

    assert not (base_dir / "partial").exists()


def test_ingested_github_repo_runs_through_pipeline(
    github_service: IngestionService,
) -> None:
    result = github_service.ingest_github("https://github.com/example/mini-repo")
    try:
        pipeline_result = AnalysisPipeline().run(result.local_path)
        assert len(pipeline_result.analyses) == 4
        assert pipeline_result.cycles.has_cycles is True
    finally:
        github_service.cleanup(result)


def test_cleanup_removes_github_job_directory(
    github_service: IngestionService,
) -> None:
    result = github_service.ingest_github(
        "https://github.com/example/mini-repo",
        job_id="cleanup-gh",
    )
    assert result.local_path.is_dir()

    github_service.cleanup(result)
    assert not result.local_path.exists()


@pytest.mark.integration
def test_ingest_github_integration_clones_public_repository(
    base_dir: Path,
) -> None:
    """Live clone against pypa/sampleproject (small public Python repo)."""
    service = IngestionService(base_dir=base_dir)
    result = service.ingest_github(INTEGRATION_REPO_URL, job_id="live-clone")
    try:
        assert result.source == "github"
        assert result.name == "pypa/sampleproject"
        assert (result.local_path / INTEGRATION_REPO_PYTHON_FILE).is_file()
        assert INTEGRATION_REPO_PYTHON_FILE in result.python_files
    finally:
        service.cleanup(result)

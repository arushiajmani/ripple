"""IngestionService tests — zip extract to temp job dirs.

Run from backend/:
    PYTHONPATH=. pytest tests/test_ingestion.py -v
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.ingestion import IngestionResult, IngestionService, UnsafeArchiveError
from app.pipeline import AnalysisPipeline

from tests.support import write_mini_repo_zip, write_zip


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path / "ripple"


@pytest.fixture
def service(base_dir: Path) -> IngestionService:
    return IngestionService(base_dir=base_dir)


def test_ingest_zip_extracts_to_job_directory(
    service: IngestionService, base_dir: Path, tmp_path: Path
) -> None:
    zpath = tmp_path / "repo.zip"
    write_mini_repo_zip(zpath)

    result = service.ingest_zip(zpath, job_id="job-1")

    assert isinstance(result, IngestionResult)
    assert result.job_id == "job-1"
    assert result.local_path == base_dir / "job-1"
    assert result.local_path.is_dir()
    assert (result.local_path / "mini_repo" / "myapp" / "models.py").is_file()
    assert "mini_repo/myapp/models.py" in result.python_files


def test_ingest_zip_bytes(service: IngestionService, tmp_path: Path) -> None:
    zpath = tmp_path / "repo.zip"
    write_mini_repo_zip(zpath)
    data = zpath.read_bytes()

    result = service.ingest_zip_bytes(data, job_id="bytes-job")

    assert result.job_id == "bytes-job"
    assert "mini_repo/myapp/auth.py" in result.python_files


def test_ingest_zip_generates_job_id_when_omitted(
    service: IngestionService, tmp_path: Path
) -> None:
    zpath = tmp_path / "repo.zip"
    write_zip(zpath, {"main.py": b"print('hi')\n"})

    result = service.ingest_zip(zpath)

    assert result.job_id
    assert result.local_path.name == result.job_id
    assert result.python_files == {"main.py"}


def test_ingest_zip_missing_file_raises(service: IngestionService) -> None:
    with pytest.raises(FileNotFoundError, match="Zip file not found"):
        service.ingest_zip("/no/such/archive.zip")


def test_ingest_zip_rejects_zip_slip(
    service: IngestionService, base_dir: Path, tmp_path: Path
) -> None:
    zpath = tmp_path / "evil.zip"
    write_zip(zpath, {"../escape.py": b"x = 1\n"})

    with pytest.raises(UnsafeArchiveError, match="Unsafe path"):
        service.ingest_zip(zpath, job_id="slip")

    assert not (base_dir / "slip").exists()


def test_failed_extract_removes_partial_directory(
    service: IngestionService, base_dir: Path, tmp_path: Path
) -> None:
    zpath = tmp_path / "bad.zip"
    zpath.write_bytes(b"not a zip")

    with pytest.raises(zipfile.BadZipFile):
        service.ingest_zip(zpath, job_id="partial")

    assert not (base_dir / "partial").exists()


def test_cleanup_removes_job_directory(service: IngestionService, tmp_path: Path) -> None:
    zpath = tmp_path / "repo.zip"
    write_zip(zpath, {"pkg/mod.py": b""})

    result = service.ingest_zip(zpath, job_id="cleanup-me")
    assert result.local_path.is_dir()

    service.cleanup(result)
    assert not result.local_path.exists()

    service.cleanup("cleanup-me")  # idempotent


def test_ingested_repo_runs_through_pipeline(service: IngestionService, tmp_path: Path) -> None:
    zpath = tmp_path / "repo.zip"
    write_mini_repo_zip(zpath)

    result = service.ingest_zip(zpath, job_id="pipeline")
    try:
        pipeline_result = AnalysisPipeline().run(result.local_path)
        assert len(pipeline_result.analyses) == 4
        assert pipeline_result.cycles.has_cycles is True
        assert len(pipeline_result.scores.scores) == 4
    finally:
        service.cleanup(result)

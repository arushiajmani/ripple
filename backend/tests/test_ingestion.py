"""IngestionService tests.

Run from backend/:
    PYTHONPATH=. pytest tests/test_ingestion.py -v
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.ingestion import IngestionResult, IngestionService
from app.pipeline import AnalysisPipeline

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


def _make_zip(root: Path, files: dict[str, str]) -> Path:
    """Write ``files`` (archive path → content) into a zip under ``root``."""
    zip_path = root / "repo.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return zip_path


def test_ingest_zip_extracts_to_job_directory(tmp_path: Path) -> None:
    base = tmp_path / "ripple"
    zip_path = _make_zip(
        tmp_path,
        {
            "myapp/__init__.py": "",
            "myapp/models.py": "from myapp.utils import helper\n",
            "myapp/utils.py": "helper = 1\n",
        },
    )
    service = IngestionService(base_dir=base)

    result = service.ingest_zip(zip_path, job_id="test-job")

    assert isinstance(result, IngestionResult)
    assert result.job_id == "test-job"
    assert result.local_path == base / "test-job"
    assert (result.local_path / "myapp/models.py").is_file()
    assert result.python_files == {"myapp/__init__.py", "myapp/models.py", "myapp/utils.py"}


def test_ingest_zip_bytes(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.py", "x = 1\n")
    service = IngestionService(base_dir=tmp_path / "ripple")

    result = service.ingest_zip_bytes(buffer.getvalue(), job_id="bytes-job")

    assert result.local_path.is_dir()
    assert (result.local_path / "main.py").read_text(encoding="utf-8") == "x = 1\n"


def test_ingest_fixture_zip_runs_pipeline(tmp_path: Path) -> None:
    zip_path = tmp_path / "mini_repo.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in FIXTURE_ROOT.rglob("*.py"):
            rel = path.relative_to(FIXTURE_ROOT).as_posix()
            archive.write(path, f"mini_repo/{rel}")

    service = IngestionService(base_dir=tmp_path / "ripple")
    result = service.ingest_zip(zip_path)

    pipeline_result = AnalysisPipeline().run(result.local_path / "mini_repo")

    assert len(pipeline_result.graph.nodes) == 4
    assert pipeline_result.cycles.has_cycles is True


def test_ingest_zip_rejects_zip_slip(tmp_path: Path) -> None:
    zip_path = _make_zip(tmp_path, {"../escape.py": "bad\n"})
    service = IngestionService(base_dir=tmp_path / "ripple")

    with pytest.raises(ValueError, match="Unsafe path"):
        service.ingest_zip(zip_path)


def test_ingest_zip_missing_file(tmp_path: Path) -> None:
    service = IngestionService(base_dir=tmp_path / "ripple")

    with pytest.raises(FileNotFoundError):
        service.ingest_zip(tmp_path / "missing.zip")


def test_cleanup_removes_job_directory(tmp_path: Path) -> None:
    base = tmp_path / "ripple"
    zip_path = _make_zip(tmp_path, {"a.py": "pass\n"})
    service = IngestionService(base_dir=base)
    result = service.ingest_zip(zip_path, job_id="cleanup-me")

    assert result.local_path.is_dir()
    service.cleanup(result)
    assert not result.local_path.exists()


def test_ingest_zip_rolls_back_on_bad_archive(tmp_path: Path) -> None:
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"not a zip")
    base = tmp_path / "ripple"
    service = IngestionService(base_dir=base)

    with pytest.raises(zipfile.BadZipFile):
        service.ingest_zip(bad_zip, job_id="rollback")

    assert not (base / "rollback").exists()

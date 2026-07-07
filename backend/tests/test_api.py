"""API integration tests — zip upload through ingest → pipeline → cleanup.

Run from backend/:
    PYTHONPATH=. pytest tests/test_api.py -v
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


def _mini_repo_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for py_file in FIXTURE_ROOT.rglob("*.py"):
            rel = py_file.relative_to(FIXTURE_ROOT.parent).as_posix()
            archive.write(py_file, rel)
    return buffer.getvalue()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


@pytest.fixture
def ingestion_base_dir(tmp_path: Path) -> Path:
    return tmp_path / "ripple"


@pytest.fixture
def client(ingestion_base_dir: Path) -> TestClient:
    app.state.ingestion_base_dir = ingestion_base_dir
    return TestClient(app)


def test_analyze_zip_returns_complete_result(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": ("mini_repo.zip", _mini_repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["job_id"]
    assert body["repository"] == {"name": "mini_repo", "source": "zip"}
    assert body["summary"]["file_count"] == 4
    assert body["analysis"]["cycles"]["has_cycles"] is True
    assert len(body["analysis"]["scores"]) == 4
    auth = next(v for k, v in body["files"].items() if k.endswith("auth.py"))
    assert auth["imports"][0]["display"] == "import os"


def test_analyze_zip_cleans_up_temp_directory(
    client: TestClient, ingestion_base_dir: Path
) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": ("mini_repo.zip", _mini_repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert not (ingestion_base_dir / job_id).exists()


def test_analyze_zip_rejects_empty_upload(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": ("empty.zip", b"", "application/zip")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Empty upload"


def test_analyze_zip_rejects_invalid_zip(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": ("bad.zip", b"not-a-zip", "application/zip")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid zip file"


def test_analyze_zip_rejects_archive_without_python_files(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        files={
            "file": (
                "readme.zip",
                _zip_bytes({"README.md": b"# no python here"}),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No Python files found in uploaded archive"


def test_analyze_zip_rejects_zip_slip(
    client: TestClient, ingestion_base_dir: Path
) -> None:
    response = client.post(
        "/api/analyze",
        files={
            "file": (
                "slip.zip",
                _zip_bytes({"../escape.py": b"x = 1\n"}),
                "application/zip",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsafe path" in response.json()["detail"]
    assert not any(ingestion_base_dir.iterdir())

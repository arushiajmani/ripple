"""API integration tests — zip upload through ingest → pipeline → cleanup.

Run from backend/:
    PYTHONPATH=. pytest tests/test_api.py -v
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ingestion import IngestionService
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


def test_analyze_requires_zip_or_github_url(client: TestClient) -> None:
    response = client.post("/api/analyze", data={})

    assert response.status_code == 400
    assert "zip file upload or a github_url" in response.json()["detail"]


def test_analyze_rejects_both_zip_and_github_url(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        data={"github_url": "https://github.com/octocat/Hello-World"},
        files={"file": ("mini_repo.zip", _mini_repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 400
    assert "not both" in response.json()["detail"]


def test_analyze_github_url_with_mocked_clone(
    client: TestClient,
    ingestion_base_dir: Path,
) -> None:
    from app.api.deps import get_ingestion_service

    class FakeRemoteChecker:
        def repo_exists(self, clone_url: str) -> bool:
            return True

    class FakeCloner:
        def clone(self, clone_url: str, dest: Path) -> None:
            shutil.copytree(FIXTURE_ROOT, dest, dirs_exist_ok=True)

    def fake_get_ingestion_service():
        return IngestionService(
            base_dir=ingestion_base_dir,
            remote_checker=FakeRemoteChecker(),
            cloner=FakeCloner(),
        )

    app.dependency_overrides[get_ingestion_service] = fake_get_ingestion_service
    try:
        response = client.post(
            "/api/analyze",
            data={"github_url": "https://github.com/example/mini-repo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["repository"] == {"name": "example/mini-repo", "source": "github"}
    assert body["summary"]["file_count"] == 4
    assert not (ingestion_base_dir / body["job_id"]).exists()


def test_analyze_github_url_rejects_invalid_url(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        data={"github_url": "https://gitlab.com/owner/repo"},
    )

    assert response.status_code == 400
    assert "github.com" in response.json()["detail"]


def test_analyze_github_url_returns_404_for_missing_repo(
    client: TestClient,
    ingestion_base_dir: Path,
) -> None:
    from app.api.deps import get_ingestion_service

    class MissingRemoteChecker:
        def repo_exists(self, clone_url: str) -> bool:
            return False

    def fake_get_ingestion_service():
        return IngestionService(
            base_dir=ingestion_base_dir,
            remote_checker=MissingRemoteChecker(),
        )

    app.dependency_overrides[get_ingestion_service] = fake_get_ingestion_service
    try:
        response = client.post(
            "/api/analyze",
            data={"github_url": "https://github.com/missing/norepo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

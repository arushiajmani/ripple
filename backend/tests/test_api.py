"""API integration tests — zip upload through ingest → pipeline → cleanup.

Run from backend/:
    PYTHONPATH=. pytest tests/test_api.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ingestion import IngestionService
from app.main import app

from tests.support import (
    FIXTURE_ROOT,
    FailingCloner,
    StubCloner,
    StubRemoteChecker,
    mini_repo_zip_bytes,
    zip_bytes,
)


def test_analyze_zip_returns_complete_result(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    body = response.json()
    keys = list(body.keys())
    assert keys[:3] == ["job_id", "repo_id", "status"]
    assert body["status"] == "complete"
    assert body["job_id"]
    assert body["repo_id"]
    assert body["repo_id"] != body["job_id"]
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
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert not (ingestion_base_dir / job_id).exists()


@pytest.mark.parametrize(
    ("filename", "content", "expected_detail"),
    [
        ("empty.zip", b"", "Empty upload"),
        ("bad.zip", b"not-a-zip", "Invalid zip file"),
        (
            "readme.zip",
            zip_bytes({"README.md": b"# no python here"}),
            "No Python files found in uploaded archive",
        ),
    ],
    ids=["empty", "invalid_zip", "no_python_files"],
)
def test_analyze_zip_rejects_bad_uploads(
    client: TestClient, filename: str, content: bytes, expected_detail: str
) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": (filename, content, "application/zip")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail


def test_analyze_zip_rejects_zip_slip(
    client: TestClient, ingestion_base_dir: Path
) -> None:
    response = client.post(
        "/api/analyze",
        files={
            "file": (
                "slip.zip",
                zip_bytes({"../escape.py": b"x = 1\n"}),
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
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 400
    assert "not both" in response.json()["detail"]


def test_analyze_github_url_with_mocked_clone(
    client: TestClient,
    ingestion_base_dir: Path,
) -> None:
    from app.api.deps import get_ingestion_service

    def fake_get_ingestion_service():
        return IngestionService(
            base_dir=ingestion_base_dir,
            remote_checker=StubRemoteChecker(),
            cloner=StubCloner(FIXTURE_ROOT),
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


def test_analyze_github_url_returns_502_on_clone_failure(
    client: TestClient,
    ingestion_base_dir: Path,
) -> None:
    from app.api.deps import get_ingestion_service

    def fake_get_ingestion_service():
        return IngestionService(
            base_dir=ingestion_base_dir,
            remote_checker=StubRemoteChecker(),
            cloner=FailingCloner("git clone failed"),
        )

    app.dependency_overrides[get_ingestion_service] = fake_get_ingestion_service
    try:
        response = client.post(
            "/api/analyze",
            data={"github_url": "https://github.com/example/repo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "clone failed" in response.json()["detail"]


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

    def fake_get_ingestion_service():
        return IngestionService(
            base_dir=ingestion_base_dir,
            remote_checker=StubRemoteChecker(exists=False),
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


def test_separate_analyze_endpoints_create_new_job_per_request(
    client: TestClient,
) -> None:
    payload = {"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")}
    legacy = client.post("/api/analyze", files=payload)
    repos = client.post("/api/repos/analyze", files=payload)

    assert legacy.status_code == 200
    assert repos.status_code == 200
    assert legacy.json()["repo_id"] == repos.json()["repo_id"]
    assert legacy.json()["job_id"] != repos.json()["job_id"]


def test_repos_analyze_returns_slim_response(client: TestClient) -> None:
    response = client.post(
        "/api/repos/analyze",
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["repository"] == {"name": "mini_repo", "source": "zip"}
    assert list(body.keys())[:3] == ["job_id", "repo_id", "status"]
    assert set(body) == {"repo_id", "job_id", "status", "repository"}


def test_repos_analyze_reuses_repository_on_same_zip(client: TestClient) -> None:
    payload = {"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")}
    first = client.post("/api/repos/analyze", files=payload)
    second = client.post("/api/repos/analyze", files=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["repo_id"] == second.json()["repo_id"]
    assert first.json()["job_id"] != second.json()["job_id"]


def test_get_repos_lists_analyzed_repository(client: TestClient) -> None:
    analyze = client.post(
        "/api/repos/analyze",
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )
    assert analyze.status_code == 200
    repo_id = analyze.json()["repo_id"]

    response = client.get("/api/repos")
    assert response.status_code == 200
    repos = response.json()
    match = next(item for item in repos if item["repo_id"] == repo_id)
    assert match["name"] == "mini_repo"
    assert match["source"] == "zip"
    assert match["status"] == "complete"
    assert match["summary"]["file_count"] == 4


def test_get_repo_detail_returns_latest_completed_job(client: TestClient) -> None:
    analyze = client.post(
        "/api/repos/analyze",
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )
    assert analyze.status_code == 200
    body = analyze.json()

    response = client.get(f"/api/repos/{body['repo_id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["repo_id"] == body["repo_id"]
    assert detail["job_id"] == body["job_id"]
    assert detail["repository"] == {"name": "mini_repo", "source": "zip"}
    assert detail["summary"]["node_count"] == 4
    assert detail["statistics"]["class_count"] >= 0


def test_get_repo_returns_404_for_unknown_repository(client: TestClient) -> None:
    response = client.get(
        "/api/repos/99999999-9999-4999-8999-999999999999",
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_repo_returns_404_for_invalid_uuid(client: TestClient) -> None:
    response = client.get("/api/repos/not-a-uuid")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def _analyze_repo(client: TestClient) -> str:
    analyze = client.post(
        "/api/repos/analyze",
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )
    assert analyze.status_code == 200
    return analyze.json()["repo_id"]


def test_get_repo_graph_returns_nodes_edges_cycles(client: TestClient) -> None:
    repo_id = _analyze_repo(client)

    response = client.get(f"/api/repos/{repo_id}/graph")
    assert response.status_code == 200
    body = response.json()
    assert body["repo_id"] == repo_id
    assert len(body["nodes"]) == 4
    assert all({"source", "target", "type"} <= set(edge) for edge in body["edges"])
    assert body["cycles"]["has_cycles"] is True
    assert body["cycles"]["cycle_count"] >= 1


def test_get_repo_scores_returns_ranked_scores(client: TestClient) -> None:
    repo_id = _analyze_repo(client)

    response = client.get(f"/api/repos/{repo_id}/scores")
    assert response.status_code == 200
    body = response.json()
    assert body["repo_id"] == repo_id
    scores = body["scores"]
    assert len(scores) == 4
    criticalities = [s["criticality"] for s in scores]
    assert criticalities == sorted(criticalities, reverse=True)
    assert {"file_path", "pagerank", "betweenness", "criticality", "in_degree", "out_degree"} <= set(scores[0])


def test_get_repo_impact_returns_dependents(client: TestClient) -> None:
    repo_id = _analyze_repo(client)

    response = client.get(
        f"/api/repos/{repo_id}/impact",
        params={"file": "mini_repo/myapp/models.py"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["target"]["file"] == "mini_repo/myapp/models.py"
    assert "mini_repo/myapp/utils.py" in body["direct_dependents"]
    assert body["summary"]["total"] >= 1
    assert body["summary"]["files_affected_percentage"] > 0.0
    assert "score" in body["target"]
    assert "file_path" not in body["target"]["score"]
    assert body["layers"][0]["depth"] == 1
    assert body["layers"][0]["files"] == body["direct_dependents"]


def test_get_repo_impact_rejects_job_id_in_url(client: TestClient) -> None:
    analyze = client.post(
        "/api/repos/analyze",
        files={"file": ("mini_repo.zip", mini_repo_zip_bytes(), "application/zip")},
    )
    assert analyze.status_code == 200
    job_id = analyze.json()["job_id"]

    response = client.get(
        f"/api/repos/{job_id}/impact",
        params={"file": "mini_repo/myapp/models.py"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_repo_impact_returns_404_for_unknown_repo(client: TestClient) -> None:
    response = client.get(
        "/api/repos/99999999-9999-4999-8999-999999999999/impact",
        params={"file": "a.py"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_repo_impact_requires_file_param(client: TestClient) -> None:
    repo_id = _analyze_repo(client)

    response = client.get(f"/api/repos/{repo_id}/impact", params={"file": "  "})
    assert response.status_code == 400
    assert "file" in response.json()["detail"].lower()


def test_get_repo_impact_returns_404_for_file_not_in_graph(client: TestClient) -> None:
    repo_id = _analyze_repo(client)

    response = client.get(
        f"/api/repos/{repo_id}/impact",
        params={"file": "missing.py"},
    )
    assert response.status_code == 404
    assert "not in graph" in response.json()["detail"].lower()


@pytest.mark.parametrize("sub_route", ["graph", "scores"])
def test_repo_sub_routes_return_404_for_unknown_repo(
    client: TestClient, sub_route: str
) -> None:
    response = client.get(
        f"/api/repos/99999999-9999-4999-8999-999999999999/{sub_route}"
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.parametrize("sub_route", ["graph", "scores"])
def test_repo_sub_routes_return_404_for_invalid_uuid(
    client: TestClient, sub_route: str
) -> None:
    response = client.get(f"/api/repos/not-a-uuid/{sub_route}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_repo_graph_loads_from_database_after_store_cleared(client: TestClient) -> None:
    repo_id = _analyze_repo(client)

    app.state.analysis_store = type(app.state.analysis_store)()

    response = client.get(f"/api/repos/{repo_id}/graph")
    assert response.status_code == 200
    assert len(response.json()["nodes"]) == 4

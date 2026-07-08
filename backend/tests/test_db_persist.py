"""Round-trip tests for PipelineResult persistence."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import uuid

import pytest
from sqlalchemy import func, select

from app.db.context import RepositoryPersistContext
from app.db.load import load_pipeline_result
from app.db.models import AnalysisJob, File
from app.db.persist import persist_pipeline_result
from app.pipeline import AnalysisPipeline

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


def _mini_repo_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for py_file in FIXTURE_ROOT.rglob("*.py"):
            rel = py_file.relative_to(FIXTURE_ROOT.parent).as_posix()
            archive.write(py_file, rel)
    return buffer.getvalue()


@pytest.mark.integration
def test_persist_and_load_pipeline_result(db_session) -> None:
    pipeline = AnalysisPipeline()
    result = pipeline.run(FIXTURE_ROOT)

    job_id = "11111111-1111-4111-8111-111111111111"
    context = RepositoryPersistContext(
        source="zip",
        name="mini_repo",
        repo_name="mini_repo",
        file_hash="test-hash-mini-repo",
    )

    persist_pipeline_result(db_session, job_id, result, context)
    db_session.flush()

    loaded = load_pipeline_result(db_session, job_id)
    assert loaded is not None
    assert set(loaded.graph.nodes) == set(result.graph.nodes)
    assert loaded.graph.edges == result.graph.edges
    assert loaded.cycles.cycle_count == result.cycles.cycle_count
    assert len(loaded.scores.scores) == len(result.scores.scores)
    assert loaded.scores.scores[0].file_path == result.scores.scores[0].file_path


@pytest.mark.integration
def test_analyze_api_persists_rows(client, db_session) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": ("mini_repo.zip", _mini_repo_zip_bytes(), "application/zip")},
    )
    assert response.status_code == 200
    job_id = uuid.UUID(response.json()["job_id"])

    job = db_session.get(AnalysisJob, job_id)
    assert job is not None
    assert job.status == "complete"
    file_count = db_session.scalar(
        select(func.count()).select_from(File).where(File.job_id == job.id)
    )
    assert file_count == 4


@pytest.mark.integration
def test_impact_loads_from_database_after_store_cleared(client) -> None:
    from app.main import app

    analyze = client.post(
        "/api/analyze",
        files={"file": ("mini_repo.zip", _mini_repo_zip_bytes(), "application/zip")},
    )
    assert analyze.status_code == 200
    job_id = analyze.json()["job_id"]

    app.state.analysis_store = type(app.state.analysis_store)()

    response = client.get(
        f"/api/impact/{job_id}",
        params={"file": "mini_repo/myapp/models.py"},
    )
    assert response.status_code == 200
    assert response.json()["target"]["file"] == "mini_repo/myapp/models.py"

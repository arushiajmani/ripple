"""Tests for repository and analysis job query helpers."""

from __future__ import annotations

import uuid

import pytest

from app.db.context import RepositoryPersistContext
from app.db.models import Repository
from app.db.persist import persist_pipeline_result
from app.db.queries import (
    get_latest_completed_job,
    get_repository,
    list_repositories_with_latest_job,
)
from app.pipeline import AnalysisPipeline

from tests.support import FIXTURE_ROOT


@pytest.mark.integration
def test_get_latest_completed_job_returns_most_recent_complete(db_session) -> None:
    pipeline = AnalysisPipeline()
    result = pipeline.run(FIXTURE_ROOT)

    context = RepositoryPersistContext(
        source="zip",
        name="mini_repo",
        repo_name="mini_repo",
        file_hash="queries-test-hash",
    )
    first = persist_pipeline_result(
        db_session,
        "22222222-2222-4222-8222-222222222222",
        result,
        context,
    )
    second = persist_pipeline_result(
        db_session,
        "33333333-3333-4333-8333-333333333333",
        result,
        context,
    )
    db_session.flush()

    assert first.repository_id == second.repository_id

    job = get_latest_completed_job(db_session, first.repository_id)
    assert job is not None
    assert job.id == second.job_id


@pytest.mark.integration
def test_get_repository_returns_persisted_repo(db_session) -> None:
    pipeline = AnalysisPipeline()
    result = pipeline.run(FIXTURE_ROOT)
    context = RepositoryPersistContext(
        source="zip",
        name="listed_repo",
        repo_name="listed_repo",
        file_hash="list-test-hash",
    )
    persisted = persist_pipeline_result(
        db_session,
        "44444444-4444-4444-8444-444444444444",
        result,
        context,
    )
    db_session.flush()

    repo = get_repository(db_session, persisted.repository_id)
    assert isinstance(repo, Repository)
    assert repo.repo_name == "listed_repo"


@pytest.mark.integration
def test_get_latest_completed_job_returns_none_for_unknown_repo(db_session) -> None:
    missing = uuid.uuid4()
    assert get_repository(db_session, missing) is None
    assert get_latest_completed_job(db_session, missing) is None


@pytest.mark.integration
def test_list_repositories_with_latest_job_returns_latest_with_statistics(
    db_session,
) -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    context = RepositoryPersistContext(
        source="zip",
        name="pair_repo",
        repo_name="pair_repo",
        file_hash="pair-test-hash",
    )
    first = persist_pipeline_result(
        db_session,
        "55555555-5555-4555-8555-555555555555",
        result,
        context,
    )
    second = persist_pipeline_result(
        db_session,
        "66666666-6666-4666-8666-666666666666",
        result,
        context,
    )
    db_session.flush()

    pairs = list_repositories_with_latest_job(db_session)

    repo, job = next(
        (repo, job) for repo, job in pairs if repo.id == first.repository_id
    )
    # Both jobs belong to the same repo → only the latest is returned.
    assert job.id == second.job_id
    # Statistics are eager-loaded (no N+1); accessible without another query.
    assert job.statistics is not None

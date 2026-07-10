"""Read helpers for repository and analysis job queries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AnalysisJob, Repository


def get_repository(session: Session, repo_id: uuid.UUID) -> Repository | None:
    """Return a repository row or ``None`` if it does not exist."""
    return session.get(Repository, repo_id)


def get_latest_completed_job(
    session: Session,
    repo_id: uuid.UUID,
) -> AnalysisJob | None:
    """Return the most recent complete analysis for a repository."""
    return session.scalar(
        select(AnalysisJob)
        .where(
            AnalysisJob.repo_id == repo_id,
            AnalysisJob.status == "complete",
        )
        .order_by(
            AnalysisJob.completed_at.desc().nullslast(),
            AnalysisJob.created_at.desc(),
        )
        .limit(1)
    )


def list_repositories_with_latest_job(
    session: Session,
) -> list[tuple[Repository, AnalysisJob]]:
    """Return ``(repository, latest completed job)`` pairs, newest repo first.

    Uses one Postgres ``DISTINCT ON (repo)`` query (plus a single eager
    ``selectinload`` for statistics) instead of one job/statistics lookup per
    repository, avoiding an N+1 for the repo list endpoint.
    """
    stmt = (
        select(Repository, AnalysisJob)
        .join(AnalysisJob, AnalysisJob.repo_id == Repository.id)
        .where(AnalysisJob.status == "complete")
        # DISTINCT ON requires the leading ORDER BY to match its column; the
        # rest of the ORDER BY selects which job wins per repository.
        .order_by(
            Repository.id,
            AnalysisJob.completed_at.desc().nullslast(),
            AnalysisJob.created_at.desc(),
        )
        .distinct(Repository.id)
        .options(selectinload(AnalysisJob.statistics))
    )
    rows = session.execute(stmt).all()
    return sorted(
        ((repo, job) for repo, job in rows),
        key=lambda pair: pair[0].created_at,
        reverse=True,
    )

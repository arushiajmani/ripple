"""Write ``PipelineResult`` artifacts into PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.context import PersistResult, RepositoryPersistContext
from app.db.models import (
    AnalysisJob,
    AnalysisStatistics,
    Cycle,
    CycleMember,
    Dependency,
    File,
    NodeScore,
    Repository,
)
from app.pipeline.pipeline import PipelineResult
from app.pipeline.serialize import build_statistics, build_summary


def get_or_create_repository(
    session: Session,
    context: RepositoryPersistContext,
) -> Repository:
    """Find an existing logical repo or insert a new ``repositories`` row."""
    if context.file_hash:
        existing = session.scalar(
            select(Repository).where(Repository.file_hash == context.file_hash)
        )
        if existing is not None:
            return existing

    if context.source == "github" and context.owner and context.repo_name:
        existing = session.scalar(
            select(Repository).where(
                Repository.source == "github",
                Repository.owner == context.owner,
                Repository.repo_name == context.repo_name,
                Repository.branch.is_(context.branch),
            )
        )
        if existing is not None:
            return existing

    repo = Repository(
        source=context.source,
        owner=context.owner,
        repo_name=context.repo_name or context.name,
        branch=context.branch,
        file_hash=context.file_hash,
    )
    session.add(repo)
    session.flush()
    return repo


def persist_pipeline_result(
    session: Session,
    job_id: str,
    result: PipelineResult,
    context: RepositoryPersistContext,
) -> PersistResult:
    """Convert a ``PipelineResult`` into rows across all analysis tables."""
    job_uuid = uuid.UUID(job_id)
    repository = get_or_create_repository(session, context)

    completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    duration_ms = sum(metric.duration_ms for metric in result.metrics) or None

    job = AnalysisJob(
        id=job_uuid,
        repo_id=repository.id,
        status="complete",
        started_at=completed_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
    )
    session.add(job)
    session.flush()

    file_ids = _insert_files(session, job_uuid, result)
    _insert_dependencies(session, job_uuid, result, file_ids)
    _insert_node_scores(session, job_uuid, result, file_ids)
    _insert_cycles(session, job_uuid, result, file_ids)
    _insert_statistics(session, job_uuid, result)

    return PersistResult(repository_id=repository.id, job_id=job_uuid)


def _file_paths(result: PipelineResult) -> list[str]:
    return sorted(set(result.graph.nodes) | set(result.analyses.keys()))


def _insert_files(
    session: Session,
    job_uuid: uuid.UUID,
    result: PipelineResult,
) -> dict[str, uuid.UUID]:
    file_ids: dict[str, uuid.UUID] = {}
    for path in _file_paths(result):
        analysis = result.analyses.get(path)
        row = File(
            job_id=job_uuid,
            file_path=path,
            line_count=analysis.line_count if analysis else None,
            syntax_error=analysis.has_syntax_error if analysis else False,
        )
        session.add(row)
        session.flush()
        file_ids[path] = row.id
    return file_ids


def _insert_dependencies(
    session: Session,
    job_uuid: uuid.UUID,
    result: PipelineResult,
    file_ids: dict[str, uuid.UUID],
) -> None:
    for source, target in result.graph.edges:
        session.add(
            Dependency(
                job_id=job_uuid,
                source_file_id=file_ids[source],
                target_file_id=file_ids[target],
                dependency_type="import",
            )
        )


def _insert_node_scores(
    session: Session,
    job_uuid: uuid.UUID,
    result: PipelineResult,
    file_ids: dict[str, uuid.UUID],
) -> None:
    for score in result.scores.scores:
        session.add(
            NodeScore(
                file_id=file_ids[score.file_path],
                job_id=job_uuid,
                pagerank_score=score.pagerank,
                betweenness_score=score.betweenness,
                composite_score=score.criticality,
                in_degree=score.in_degree,
                out_degree=score.out_degree,
            )
        )


def _insert_cycles(
    session: Session,
    job_uuid: uuid.UUID,
    result: PipelineResult,
    file_ids: dict[str, uuid.UUID],
) -> None:
    for cycle_paths in result.cycles.cycles:
        cycle = Cycle(job_id=job_uuid, length=len(cycle_paths))
        session.add(cycle)
        session.flush()
        for position, path in enumerate(cycle_paths):
            session.add(
                CycleMember(
                    cycle_id=cycle.id,
                    file_id=file_ids[path],
                    position=position,
                )
            )


def _insert_statistics(
    session: Session,
    job_uuid: uuid.UUID,
    result: PipelineResult,
) -> None:
    summary = build_summary(result)
    stats = build_statistics(result)
    node_count = summary["node_count"]
    graph_density: float | None = None
    if node_count > 1:
        graph_density = summary["edge_count"] / (node_count * (node_count - 1))

    session.add(
        AnalysisStatistics(
            job_id=job_uuid,
            file_count=summary["file_count"],
            node_count=node_count,
            edge_count=summary["edge_count"],
            cycle_count=summary["cycle_count"],
            external_dependency_count=stats["external_dependency_count"],
            class_count=stats["class_count"],
            function_count=stats["function_count"],
            graph_density=graph_density,
        )
    )

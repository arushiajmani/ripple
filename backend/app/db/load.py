"""Reconstruct ``PipelineResult`` from PostgreSQL for on-demand queries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AnalysisJob,
    Cycle,
    CycleMember,
    Dependency,
    File,
    NodeScore,
)
from app.graph.models import (
    CircularDependencyResult,
    GraphResult,
    NodeScore as PipelineNodeScore,
    ScoringResult,
)
from app.parser.models import FileAnalysis
from app.pipeline.pipeline import PipelineResult


def load_pipeline_result(session: Session, job_id: str) -> PipelineResult | None:
    """Load a completed analysis job from the database, or ``None`` if missing."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        return None

    job = session.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.id == job_uuid, AnalysisJob.status == "complete")
        .options(
            selectinload(AnalysisJob.files),
            selectinload(AnalysisJob.dependencies),
            selectinload(AnalysisJob.node_scores),
            selectinload(AnalysisJob.cycles).selectinload(Cycle.members),
        )
    )
    if job is None:
        return None

    path_by_file_id = {row.id: row.file_path for row in job.files}
    analyses = _build_analyses(job.files)
    graph = _build_graph(job.files, job.dependencies, path_by_file_id)
    scores = _build_scores(job.node_scores, path_by_file_id)
    cycles = _build_cycles(job.cycles, path_by_file_id)

    return PipelineResult(
        analyses=analyses,
        graph=graph,
        cycles=cycles,
        scores=scores,
        metrics=[],
    )


def _build_analyses(files: list[File]) -> dict[str, FileAnalysis]:
    analyses: dict[str, FileAnalysis] = {}
    for row in files:
        analyses[row.file_path] = FileAnalysis(
            file_path=row.file_path,
            imports=[],
            resolved_deps=[],
            external_deps=[],
            classes=[],
            functions=[],
            methods=[],
            line_count=row.line_count,
            has_syntax_error=row.syntax_error,
        )
    return analyses


def _build_graph(
    files: list[File],
    dependencies: list[Dependency],
    path_by_file_id: dict[uuid.UUID, str],
) -> GraphResult:
    nodes = sorted(row.file_path for row in files)
    edges = [
        (path_by_file_id[dep.source_file_id], path_by_file_id[dep.target_file_id])
        for dep in dependencies
    ]
    edges.sort()
    return GraphResult(nodes=nodes, edges=edges)


def _build_scores(
    node_scores: list[NodeScore],
    path_by_file_id: dict[uuid.UUID, str],
) -> ScoringResult:
    scores = [
        PipelineNodeScore(
            file_path=path_by_file_id[row.file_id],
            pagerank=row.pagerank_score,
            betweenness=row.betweenness_score,
            criticality=row.composite_score,
            in_degree=row.in_degree,
            out_degree=row.out_degree,
        )
        for row in node_scores
    ]
    scores.sort(key=lambda item: (-item.criticality, item.file_path))
    return ScoringResult(scores=scores)


def _build_cycles(
    cycles: list[Cycle],
    path_by_file_id: dict[uuid.UUID, str],
) -> CircularDependencyResult:
    cycle_paths: list[list[str]] = []
    for cycle in cycles:
        members = sorted(cycle.members, key=lambda member: member.position)
        cycle_paths.append([path_by_file_id[member.file_id] for member in members])
    cycle_paths.sort()
    return CircularDependencyResult(cycles=cycle_paths)

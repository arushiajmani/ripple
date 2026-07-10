"""On-demand impact analysis against stored pipeline artifacts."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.load import load_pipeline_result
from app.db.queries import get_latest_completed_job
from app.graph.adapter import GraphAdapter
from app.graph.algorithms.impact import ImpactAnalyzer
from app.graph.models import ImpactAnalysisResult
from app.pipeline.pipeline import PipelineResult
from app.pipeline.store import AnalysisNotFoundError, AnalysisStore


def analyze_file_impact(
    store: AnalysisStore,
    repo_id: str,
    file_path: str,
    *,
    session: Session | None = None,
    analyzer: ImpactAnalyzer | None = None,
) -> ImpactAnalysisResult:
    """Run impact analysis for one file using stored or persisted pipeline artifacts."""
    result = resolve_pipeline_result(store, repo_id, session=session)
    return analyze_file_impact_from_result(
        result,
        file_path,
        analyzer=analyzer,
    )


def resolve_pipeline_result(
    store: AnalysisStore,
    repo_id: str,
    *,
    session: Session | None = None,
) -> PipelineResult:
    """Resolve artifacts by ``repositories.id`` (latest completed job).

    Shared by the impact, graph, and scores endpoints: checks the in-process
    cache first, then loads the latest completed job from PostgreSQL. Raises
    ``AnalysisNotFoundError`` (→ 404) when the id is not a UUID or no completed
    analysis exists.
    """
    cached = store.get(repo_id)
    if cached is not None:
        return cached

    try:
        repo_uuid = uuid.UUID(repo_id)
    except ValueError as exc:
        raise AnalysisNotFoundError(f"Repository analysis not found: {repo_id}") from exc

    if session is not None:
        job = get_latest_completed_job(session, repo_uuid)
        if job is not None:
            loaded = load_pipeline_result(session, str(job.id))
            if loaded is not None:
                store.save(repo_id, loaded)
                return loaded

    raise AnalysisNotFoundError(f"Repository analysis not found: {repo_id}")


def analyze_file_impact_from_result(
    result: PipelineResult,
    file_path: str,
    *,
    analyzer: ImpactAnalyzer | None = None,
) -> ImpactAnalysisResult:
    """Run impact analysis from in-memory pipeline artifacts (no re-parse)."""
    runner = analyzer or ImpactAnalyzer()
    digraph = GraphAdapter().to_digraph(result.graph)
    return runner.analyze(digraph, file_path, scores=result.scores)

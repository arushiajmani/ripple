"""On-demand impact analysis against stored pipeline artifacts."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.load import load_pipeline_result
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
    result = _resolve_pipeline_result(store, repo_id, session=session)
    return analyze_file_impact_from_result(
        result,
        file_path,
        analyzer=analyzer,
    )


def _resolve_pipeline_result(
    store: AnalysisStore,
    repo_id: str,
    *,
    session: Session | None = None,
) -> PipelineResult:
    cached = store.get(repo_id)
    if cached is not None:
        return cached

    if session is not None:
        loaded = load_pipeline_result(session, repo_id)
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

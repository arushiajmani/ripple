"""On-demand impact analysis against stored pipeline artifacts."""

from __future__ import annotations

from app.graph.adapter import GraphAdapter
from app.graph.algorithms.impact import ImpactAnalyzer
from app.graph.models import ImpactAnalysisResult
from app.pipeline.pipeline import PipelineResult
from app.pipeline.store import AnalysisStore


def analyze_file_impact(
    store: AnalysisStore,
    repo_id: str,
    file_path: str,
    *,
    analyzer: ImpactAnalyzer | None = None,
) -> ImpactAnalysisResult:
    """Run impact analysis for one file using a previously stored ``PipelineResult``."""
    result = store.require(repo_id)
    return analyze_file_impact_from_result(
        result,
        file_path,
        analyzer=analyzer,
    )


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

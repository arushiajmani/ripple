"""Analysis pipeline: parse → graph → cycles → scores.

Orchestrates shipped analysis stages without coupling them to the API or DB.
Call AnalysisPipeline().run(repo_path) for a full PipelineResult.

CLI: python -m app.pipeline <repo-path>
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.graph.algorithms.cycles import CycleDetector
from app.graph.algorithms.scoring import AlgorithmEngine
from app.graph.builder import GraphBuilder
from app.graph.models import (
    CircularDependencyResult,
    GraphResult,
    ScoringResult,
)
from app.parser.models import FileAnalysis
from app.parser.repository import parse_repository


@dataclass
class PipelineResult:
    """Full analysis output for one repository root.

    scores: per-file pagerank (depended-on), betweenness (bridge), criticality
    (change-risk rank), in/out degree — see NodeScore / learn.md glossary.
    """

    analyses: dict[str, FileAnalysis]
    graph: GraphResult
    cycles: CircularDependencyResult
    scores: ScoringResult


class AnalysisPipeline:
    """Wire parse_repository → GraphBuilder → CycleDetector → AlgorithmEngine."""

    def __init__(
        self,
        graph_builder: GraphBuilder | None = None,
        cycle_detector: CycleDetector | None = None,
        algorithm_engine: AlgorithmEngine | None = None,
    ) -> None:
        self._graph_builder = graph_builder or GraphBuilder()
        self._cycle_detector = cycle_detector or CycleDetector()
        self._algorithm_engine = algorithm_engine or AlgorithmEngine()

    def run(self, repo_path: str | Path) -> PipelineResult:
        # Paths must be relative to the project root (see analysis root convention).
        analyses = parse_repository(repo_path)
        graph = self._graph_builder.build(analyses)
        cycles = self._cycle_detector.detect(graph)
        scores = self._algorithm_engine.score(graph)
        return PipelineResult(
            analyses=analyses,
            graph=graph,
            cycles=cycles,
            scores=scores,
        )

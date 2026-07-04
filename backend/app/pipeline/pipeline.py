"""Analysis pipeline: parse → graph → cycle detection.

Orchestrates shipped analysis stages without coupling them to the API or DB.
Call AnalysisPipeline().run(repo_path) for a full PipelineResult.

CLI: python -m app.pipeline <repo-path>
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.graph.algorithms.cycles import CycleDetector
from app.graph.builder import GraphBuilder
from app.graph.models import CircularDependencyResult, GraphResult
from app.parser.models import FileAnalysis
from app.parser.repository import parse_repository


@dataclass
class PipelineResult:
    """Full analysis output for one repository root."""

    analyses: dict[str, FileAnalysis]
    graph: GraphResult
    cycles: CircularDependencyResult


class AnalysisPipeline:
    """Wire parse_repository → GraphBuilder → CycleDetector."""

    def __init__(
        self,
        graph_builder: GraphBuilder | None = None,
        cycle_detector: CycleDetector | None = None,
    ) -> None:
        self._graph_builder = graph_builder or GraphBuilder()
        self._cycle_detector = cycle_detector or CycleDetector()

    def run(self, repo_path: str | Path) -> PipelineResult:
        # Paths must be relative to the project root (see analysis root convention).
        analyses = parse_repository(repo_path)
        graph = self._graph_builder.build(analyses)
        cycles = self._cycle_detector.detect(graph)
        return PipelineResult(analyses=analyses, graph=graph, cycles=cycles)

"""Analysis pipeline: parse → graph → cycles → scores.

Orchestrates shipped analysis stages without coupling them to the API or DB.
Call AnalysisPipeline().run(repo_path) for a full PipelineResult.

CLI: python -m app.pipeline <repo-path>
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

    JSON export (lazy-imports serialize helpers to avoid circular imports):
        result.to_dict() / result.to_json() / result.write_json("result.json")
    """

    analyses: dict[str, FileAnalysis]
    graph: GraphResult
    cycles: CircularDependencyResult
    scores: ScoringResult

    def to_dict(
        self,
        *,
        include_files: bool = True,
        generated_at: datetime | None = None,
    ) -> dict:
        """JSON-ready dict (metadata, summary, statistics, graph, analysis, files)."""
        from app.pipeline.serialize import pipeline_result_to_dict

        return pipeline_result_to_dict(
            self,
            include_files=include_files,
            generated_at=generated_at,
        )

    def to_json(
        self,
        *,
        indent: int | None = 2,
        include_files: bool = True,
        generated_at: datetime | None = None,
    ) -> str:
        """Serialize this result to a JSON string."""
        from app.pipeline.serialize import pipeline_result_to_json

        return pipeline_result_to_json(
            self,
            indent=indent,
            include_files=include_files,
            generated_at=generated_at,
        )

    def write_json(
        self,
        path: str | Path,
        *,
        indent: int | None = 2,
        include_files: bool = True,
        generated_at: datetime | None = None,
    ) -> Path:
        """Write analysis JSON to ``path``; returns the resolved path."""
        from app.pipeline.serialize import write_pipeline_json

        return write_pipeline_json(
            self,
            path,
            indent=indent,
            include_files=include_files,
            generated_at=generated_at,
        )


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

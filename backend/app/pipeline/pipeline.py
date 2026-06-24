from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.graph.builder import GraphBuilder
from app.graph.models import GraphResult
from app.parser.models import FileAnalysis
from app.parser.repository import parse_repository


@dataclass
class PipelineResult:
    analyses: dict[str, FileAnalysis]
    graph: GraphResult


class AnalysisPipeline:
    def __init__(self, graph_builder: GraphBuilder | None = None) -> None:
        self._graph_builder = graph_builder or GraphBuilder()

    def run(self, repo_path: str | Path) -> PipelineResult:
        analyses = parse_repository(repo_path)
        graph = self._graph_builder.build(analyses)
        return PipelineResult(analyses=analyses, graph=graph)

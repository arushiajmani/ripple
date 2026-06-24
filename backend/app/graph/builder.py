from __future__ import annotations

from app.graph.models import GraphResult
from app.parser.models import FileAnalysis


class GraphBuilder:
    def build(self, analyses: dict[str, FileAnalysis]) -> GraphResult:
        nodes = sorted(analyses)
        node_set = set(nodes)
        edges: list[tuple[str, str]] = []
        seen_edges: set[tuple[str, str]] = set()

        for file_path, analysis in analyses.items():
            for dep in analysis.resolved_deps:
                if dep not in node_set:
                    continue
                edge = (file_path, dep)
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                edges.append(edge)

        edges.sort()
        return GraphResult(nodes=nodes, edges=edges)

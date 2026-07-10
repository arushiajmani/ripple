"""On-demand change-impact analysis for a single file.

Given one file F in an already-built import graph, answer: which files depend
on F (directly and transitively), the layered blast radius by hop distance, and
how large that radius is relative to the repo. Reuses an existing
``NodeScore`` for F when scores are available — does not recompute criticality.

Edges are importer → imported. Dependents are predecessors in the DiGraph
(reverse-direction reachability), not the forward walk used by PageRank.

Invoke on demand against ``PipelineResult`` artifacts (graph + scores); not
wired into ``AnalysisPipeline`` as a batch stage.

Run tests from backend/:
    PYTHONPATH=. pytest tests/algorithms/test_impact.py -v
"""

from __future__ import annotations

import time

import networkx as nx

from app.graph.models import (
    ImpactAnalysisResult,
    ImpactLayer,
    ImpactSummary,
    ImpactTarget,
    NodeScore,
    ScoringResult,
)
from app.metrics import StageMetric

IMPACT_PERCENT_DECIMALS = 3


class FileNotInGraphError(ValueError):
    """Raised when the target file is not a node in the dependency graph."""


class ImpactAnalyzer:
    """Compute blast-radius dependents for one file in a NetworkX DiGraph."""

    def analyze(
        self,
        digraph: nx.DiGraph,
        target_file: str,
        *,
        scores: ScoringResult | None = None,
    ) -> ImpactAnalysisResult:
        result, _metrics = self.analyze_with_metrics(
            digraph,
            target_file,
            scores=scores,
        )
        return result

    def analyze_with_metrics(
        self,
        digraph: nx.DiGraph,
        target_file: str,
        *,
        scores: ScoringResult | None = None,
    ) -> tuple[ImpactAnalysisResult, list[StageMetric]]:
        if target_file not in digraph:
            raise FileNotInGraphError(f"File not in graph: {target_file}")

        start = time.perf_counter()

        total_files = digraph.number_of_nodes()

        # A single reverse BFS (imported → importer) yields the whole blast
        # radius: hop distance is the blast-radius depth, so depth 1 is the
        # direct importers and depth >= 2 is the indirect importers.
        rev = digraph.reverse(copy=False)
        distances = nx.single_source_shortest_path_length(rev, target_file)

        by_depth: dict[int, list[str]] = {}
        for node, depth in distances.items():
            if depth == 0:
                continue
            by_depth.setdefault(depth, []).append(node)

        layers = [
            ImpactLayer(depth=depth, files=sorted(by_depth[depth]))
            for depth in sorted(by_depth)
        ]

        direct_dependents = sorted(by_depth.get(1, []))
        indirect_dependents = sorted(
            node
            for depth, nodes in by_depth.items()
            if depth >= 2
            for node in nodes
        )

        direct_count = len(direct_dependents)
        indirect_count = len(indirect_dependents)
        total_count = direct_count + indirect_count
        max_depth = max(by_depth) if by_depth else 0

        files_affected_percentage = (
            round(
                (total_count / total_files) * 100.0,
                IMPACT_PERCENT_DECIMALS,
            )
            if total_files
            else 0.0
        )

        target_score = _lookup_score(scores, target_file)

        duration_ms = (time.perf_counter() - start) * 1000.0
        metrics = [
            StageMetric(
                "impact_analysis",
                duration_ms,
                files_processed=total_count,
            )
        ]

        return (
            ImpactAnalysisResult(
                target=ImpactTarget(file=target_file, score=target_score),
                direct_dependents=direct_dependents,
                indirect_dependents=indirect_dependents,
                layers=layers,
                summary=ImpactSummary(
                    direct=direct_count,
                    indirect=indirect_count,
                    total=total_count,
                    max_depth=max_depth,
                    files_affected_percentage=files_affected_percentage,
                ),
            ),
            metrics,
        )


def _lookup_score(
    scores: ScoringResult | None,
    target_file: str,
) -> NodeScore | None:
    if scores is None:
        return None
    for score in scores.scores:
        if score.file_path == target_file:
            return score
    return None

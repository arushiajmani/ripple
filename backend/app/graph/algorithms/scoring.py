"""PageRank, betweenness, and composite criticality scoring.

What each metric means (edges are importer → imported):

* **pagerank** — "How important is this file as a dependency?" Importance
  flows from importers to imported files. Shared modules (models, utils)
  that many files import tend to rank high. Raw scores sum to ~1.0 over
  the graph.

* **betweenness** — "How often is this file a bridge?" Counts how many
  shortest paths between other files pass through this node. High means
  a bottleneck: unrelated parts of the codebase connect through it.

* **criticality** — Ripple's combined risk score for ranking files:
  ``0.6 * normalize(pagerank) + 0.4 * normalize(betweenness)``.
  Min-max normalize each metric to [0, 1] first so scales are comparable.
  Higher criticality ⇒ treat changes more carefully.

* **in_degree** — Count of project files that import this file.
* **out_degree** — Count of project files this file imports.

Wired into AnalysisPipeline as PipelineResult.scores.

Run tests from backend/:
    PYTHONPATH=. pytest tests/algorithms/test_scoring.py -v
"""

from __future__ import annotations

import networkx as nx

from app.graph.algorithms.digraph import graph_result_to_digraph
from app.graph.models import GraphResult, NodeScore, ScoringResult

# How much each metric contributes to criticality (must sum to 1.0).
# Slightly favor "widely depended on" (PageRank) over "bridge" (betweenness).
PAGERANK_WEIGHT = 0.6
BETWEENNESS_WEIGHT = 0.4
# Damping: with probability (1 - alpha) a random walk "teleports" to a random
# node so sink nodes do not absorb all importance.
PAGERANK_ALPHA = 0.85


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Min-max scale values to [0, 1] so PageRank and betweenness are comparable.

    Equal values → all 0.0 (no relative ranking within that metric).
    """
    if not scores:
        return {}
    values = list(scores.values())
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return {node: 0.0 for node in scores}
    span = hi - lo
    return {node: (value - lo) / span for node, value in scores.items()}


class AlgorithmEngine:
    """Compute PageRank, betweenness, degrees, and composite criticality."""

    def __init__(
        self,
        *,
        pagerank_alpha: float = PAGERANK_ALPHA,
        pagerank_weight: float = PAGERANK_WEIGHT,
        betweenness_weight: float = BETWEENNESS_WEIGHT,
    ) -> None:
        self._pagerank_alpha = pagerank_alpha
        self._pagerank_weight = pagerank_weight
        self._betweenness_weight = betweenness_weight

    def run(self, graph: GraphResult) -> ScoringResult:
        if not graph.nodes:
            return ScoringResult(scores=[])

        digraph = graph_result_to_digraph(graph)

        # Importance flows along edges toward files that others import.
        pagerank = nx.pagerank(digraph, alpha=self._pagerank_alpha)
        # Fraction of shortest paths that pass through each node.
        betweenness = nx.betweenness_centrality(digraph)

        # Scale each metric to [0, 1] within this repo before weighting.
        norm_pr = normalize_scores(pagerank)
        norm_bt = normalize_scores(betweenness)

        scores: list[NodeScore] = []
        for node in graph.nodes:
            pr = pagerank[node]
            bt = betweenness[node]
            # Relative risk score for this repo (not an absolute probability).
            criticality = (
                self._pagerank_weight * norm_pr[node]
                + self._betweenness_weight * norm_bt[node]
            )
            scores.append(
                NodeScore(
                    file_path=node,
                    pagerank=pr,
                    betweenness=bt,
                    criticality=criticality,
                    # Direct dependents (who imports me?) / dependencies (who do I import?).
                    in_degree=int(digraph.in_degree(node)),
                    out_degree=int(digraph.out_degree(node)),
                )
            )

        # Highest criticality first; tie-break by path for stable output.
        scores.sort(key=lambda s: (-s.criticality, s.file_path))
        return ScoringResult(scores=scores)

    # Alias matching CycleDetector.detect naming.
    score = run

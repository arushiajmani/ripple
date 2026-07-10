"""AlgorithmEngine unit tests.

Synthetic DiGraph graphs only — no parser, no filesystem.
Pipeline integration of scores is in test_pipeline.py.

Metric meanings (see docs/learn.md#1-what-each-property-means):
  pagerank     — how depended-on (importance flows to shared modules)
  betweenness  — bridge / bottleneck on paths between other files
  criticality  — 0.6 * norm(PR) + 0.4 * norm(BT); relative change-risk
  in_degree    — # of project files that import this file
  out_degree   — # of project files this file imports

Run from backend/:
    PYTHONPATH=. pytest tests/algorithms/test_scoring.py -v

pytest primer: docs/learn.md#introduction-to-pytest
"""

from __future__ import annotations

from typing import Callable

import networkx as nx

from app.graph import AlgorithmEngine, GraphResult, NodeScore
from app.graph.algorithms.scoring import (
    BETWEENNESS_WEIGHT,
    PAGERANK_WEIGHT,
    normalize_scores,
)
from app.parser.models import FileAnalysis

from tests.support import make_file, to_digraph


# --- normalize_scores ---

def test_normalize_scores_empty() -> None:
    assert normalize_scores({}) == {}


def test_normalize_scores_min_max() -> None:
    assert normalize_scores({"a": 1.0, "b": 3.0, "c": 5.0}) == {
        "a": 0.0,
        "b": 0.5,
        "c": 1.0,
    }


def test_normalize_scores_all_equal_are_zero() -> None:
    """No relative ranking when every node has the same raw score."""
    assert normalize_scores({"a": 0.5, "b": 0.5}) == {"a": 0.0, "b": 0.0}


# --- Empty / trivial graphs ---

def test_empty_graph_has_no_scores() -> None:
    result = AlgorithmEngine().score(nx.DiGraph())

    assert result.scores == []
    assert result.top() == []


def test_single_node_has_scores_and_zero_degrees() -> None:
    digraph = nx.DiGraph()
    digraph.add_node("solo.py")

    result = AlgorithmEngine().score(digraph)

    assert len(result.scores) == 1
    node = result.scores[0]
    assert node.file_path == "solo.py"
    assert node.pagerank == 1.0
    assert node.betweenness == 0.0
    assert node.criticality == 0.0  # only one value → normalize to 0
    assert node.in_degree == 0
    assert node.out_degree == 0


# --- Ranking on a fan-in graph (shared dependency) ---

def test_shared_dependency_ranks_higher_than_leaves(
    build_digraph: Callable[[dict[str, FileAnalysis]], nx.DiGraph],
) -> None:
    """Leaves import hub → PageRank flows to hub; hub should top criticality."""
    digraph = build_digraph(
        {
            "hub.py": make_file("hub.py"),
            "a.py": make_file("a.py", resolved_deps=["hub.py"]),
            "b.py": make_file("b.py", resolved_deps=["hub.py"]),
            "c.py": make_file("c.py", resolved_deps=["hub.py"]),
        }
    )

    result = AlgorithmEngine().score(digraph)
    by_path = {s.file_path: s for s in result.scores}

    assert result.scores[0].file_path == "hub.py"
    assert by_path["hub.py"].pagerank > by_path["a.py"].pagerank
    assert by_path["hub.py"].in_degree == 3
    assert by_path["a.py"].out_degree == 1
    assert by_path["a.py"].in_degree == 0


def test_bridge_node_has_high_betweenness(
    build_digraph: Callable[[dict[str, FileAnalysis]], nx.DiGraph],
) -> None:
    """A → bridge → B: bridge lies on the only path between A and B."""
    digraph = build_digraph(
        {
            "a.py": make_file("a.py", resolved_deps=["bridge.py"]),
            "bridge.py": make_file("bridge.py", resolved_deps=["b.py"]),
            "b.py": make_file("b.py"),
        }
    )

    result = AlgorithmEngine().score(digraph)
    by_path = {s.file_path: s for s in result.scores}

    assert by_path["bridge.py"].betweenness > by_path["a.py"].betweenness
    assert by_path["bridge.py"].betweenness > by_path["b.py"].betweenness


def test_criticality_uses_weighted_normalized_metrics() -> None:
    """criticality == 0.6 * norm(pr) + 0.4 * norm(bt) for each node."""
    digraph = to_digraph(
        GraphResult(
            nodes=["hub.py", "a.py", "b.py"],
            edges=[("a.py", "hub.py"), ("b.py", "hub.py")],
        )
    )

    result = AlgorithmEngine().score(digraph)
    pagerank = {s.file_path: s.pagerank for s in result.scores}
    betweenness = {s.file_path: s.betweenness for s in result.scores}
    norm_pr = normalize_scores(pagerank)
    norm_bt = normalize_scores(betweenness)

    for node in result.scores:
        expected = (
            PAGERANK_WEIGHT * norm_pr[node.file_path]
            + BETWEENNESS_WEIGHT * norm_bt[node.file_path]
        )
        assert node.criticality == expected


def test_scores_sorted_by_criticality_then_path(
    build_digraph: Callable[[dict[str, FileAnalysis]], nx.DiGraph],
) -> None:
    digraph = build_digraph(
        {
            "hub.py": make_file("hub.py"),
            "z.py": make_file("z.py", resolved_deps=["hub.py"]),
            "a.py": make_file("a.py", resolved_deps=["hub.py"]),
        }
    )

    result = AlgorithmEngine().score(digraph)
    criticalities = [s.criticality for s in result.scores]

    assert criticalities == sorted(criticalities, reverse=True)
    # Leaves share criticality; path tie-break puts a.py before z.py.
    leaves = [s for s in result.scores if s.file_path != "hub.py"]
    assert [s.file_path for s in leaves] == ["a.py", "z.py"]


def test_top_returns_first_n(
    build_digraph: Callable[[dict[str, FileAnalysis]], nx.DiGraph],
) -> None:
    digraph = build_digraph(
        {
            "hub.py": make_file("hub.py"),
            "a.py": make_file("a.py", resolved_deps=["hub.py"]),
            "b.py": make_file("b.py", resolved_deps=["hub.py"]),
        }
    )

    result = AlgorithmEngine().score(digraph)

    assert len(result.top(2)) == 2
    assert result.top(2)[0].file_path == "hub.py"
    assert result.top(100) == result.scores


def test_run_matches_score() -> None:
    """run() and score() are the same method (alias)."""
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py"],
            edges=[("a.py", "b.py")],
        )
    )
    engine = AlgorithmEngine()

    assert engine.run(digraph) == engine.score(digraph)


def test_node_score_fields_present(
    build_digraph: Callable[[dict[str, FileAnalysis]], nx.DiGraph],
) -> None:
    digraph = build_digraph(
        {
            "a.py": make_file("a.py", resolved_deps=["b.py"]),
            "b.py": make_file("b.py"),
        }
    )

    node = AlgorithmEngine().score(digraph).scores[0]
    assert isinstance(node, NodeScore)
    assert node.file_path
    assert node.pagerank >= 0.0
    assert node.betweenness >= 0.0
    assert node.criticality >= 0.0
    assert node.in_degree >= 0
    assert node.out_degree >= 0


def test_pagerank_warmup_excludes_cold_start_from_metrics() -> None:
    """Untimed warm-up runs before the measured PageRank stage."""
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py"],
            edges=[("a.py", "b.py")],
        )
    )
    engine = AlgorithmEngine()

    _, metrics_with_warmup = engine.run_with_metrics(digraph, warmup_pagerank=True)
    _, metrics_without_warmup = engine.run_with_metrics(digraph, warmup_pagerank=False)

    assert len(metrics_with_warmup) == 3
    assert metrics_with_warmup[0].stage_name == "pagerank_computation"
    assert metrics_with_warmup[0].duration_ms >= 0.0
    assert metrics_without_warmup[0].stage_name == "pagerank_computation"

"""ImpactAnalyzer unit tests.

Synthetic DiGraph graphs only — no parser, no filesystem.
On-demand API integration is in test_api.py.

Edge direction is importer → imported. Dependents are predecessors (reverse
reachability). Layers group dependents by hop distance from the target.
``indirect_dependents`` is indirect only (depth 2+), excluding direct.

Run from backend/:
    PYTHONPATH=. pytest tests/algorithms/test_impact.py -v

pytest primer: docs/learn.md#introduction-to-pytest
"""

from __future__ import annotations

from typing import Callable

import networkx as nx
import pytest

from app.graph import (
    AlgorithmEngine,
    GraphResult,
    ImpactAnalyzer,
    ImpactLayer,
    NodeScore,
)
from app.graph.algorithms.impact import FileNotInGraphError
from app.parser.models import FileAnalysis

from tests.support import make_file, to_digraph


# --- Linear chain ---

def test_linear_chain_direct_vs_indirect_dependents() -> None:
    """A → B → C: targeting C yields B direct and A indirect at depth 2."""
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py", "c.py"],
            edges=[("a.py", "b.py"), ("b.py", "c.py")],
        )
    )

    result = ImpactAnalyzer().analyze(digraph, "c.py")

    assert result.direct_dependents == ["b.py"]
    assert result.indirect_dependents == ["a.py"]
    assert result.layers == [
        ImpactLayer(depth=1, files=["b.py"]),
        ImpactLayer(depth=2, files=["a.py"]),
    ]
    assert result.summary.direct == 1
    assert result.summary.indirect == 1
    assert result.summary.total == 2
    assert result.summary.max_depth == 2
    assert result.summary.files_affected_percentage == pytest.approx(66.667, abs=0.001)


# --- Diamond ---

def test_diamond_no_duplicate_files_across_layers() -> None:
    """D imports B and C; both import A — each dependent appears once."""
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py", "c.py", "d.py"],
            edges=[
                ("b.py", "a.py"),
                ("c.py", "a.py"),
                ("d.py", "b.py"),
                ("d.py", "c.py"),
            ],
        )
    )

    result = ImpactAnalyzer().analyze(digraph, "a.py")

    assert result.direct_dependents == ["b.py", "c.py"]
    assert result.indirect_dependents == ["d.py"]
    assert result.layers == [
        ImpactLayer(depth=1, files=["b.py", "c.py"]),
        ImpactLayer(depth=2, files=["d.py"]),
    ]
    assert result.summary.direct == 2
    assert result.summary.indirect == 1
    assert result.summary.total == 3
    assert result.summary.max_depth == 2

    flat_layers = [f for layer in result.layers for f in layer.files]
    all_affected = sorted(result.direct_dependents + result.indirect_dependents)
    assert flat_layers == all_affected
    assert len(flat_layers) == len(set(flat_layers))


# --- Cycle ---

def test_cycle_ancestors_terminate_and_nodes_impact_each_other() -> None:
    """A ↔ B: each file lists the other as direct only (no indirect)."""
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py"],
            edges=[("a.py", "b.py"), ("b.py", "a.py")],
        )
    )

    impact_a = ImpactAnalyzer().analyze(digraph, "a.py")
    impact_b = ImpactAnalyzer().analyze(digraph, "b.py")

    assert impact_a.direct_dependents == ["b.py"]
    assert impact_a.indirect_dependents == []
    assert impact_a.layers == [ImpactLayer(depth=1, files=["b.py"])]
    assert impact_a.summary.total == 1

    assert impact_b.direct_dependents == ["a.py"]
    assert impact_b.indirect_dependents == []
    assert impact_b.layers == [ImpactLayer(depth=1, files=["a.py"])]
    assert impact_b.summary.total == 1


# --- Leaf node ---

def test_leaf_node_has_empty_impact_and_zero_percent() -> None:
    """Nothing imports the target — empty dependents, 0% impact, no divide-by-zero."""
    digraph = to_digraph(
        GraphResult(
            nodes=["top.py", "base.py"],
            edges=[("top.py", "base.py")],
        )
    )

    result = ImpactAnalyzer().analyze(digraph, "top.py")

    assert result.direct_dependents == []
    assert result.indirect_dependents == []
    assert result.layers == []
    assert result.summary.direct == 0
    assert result.summary.indirect == 0
    assert result.summary.total == 0
    assert result.summary.max_depth == 0
    assert result.summary.files_affected_percentage == 0.0


# --- Missing file ---

def test_missing_file_raises_clear_error() -> None:
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py"],
            edges=[],
        )
    )

    with pytest.raises(FileNotInGraphError, match="missing.py"):
        ImpactAnalyzer().analyze(digraph, "missing.py")


# --- Score lookup ---

def test_reuses_existing_criticality_score_for_target(
    build_digraph: Callable[[dict[str, FileAnalysis]], nx.DiGraph],
) -> None:
    digraph = build_digraph(
        {
            "hub.py": make_file("hub.py"),
            "a.py": make_file("a.py", resolved_deps=["hub.py"]),
        }
    )
    scores = AlgorithmEngine().score(digraph)

    result = ImpactAnalyzer().analyze(digraph, "hub.py", scores=scores)

    assert result.target.score is not None
    assert isinstance(result.target.score, NodeScore)
    assert result.target.file == "hub.py"
    assert result.target.score.file_path == "hub.py"
    assert result.target.score.criticality == scores.scores[0].criticality


def test_target_score_none_when_scores_not_provided() -> None:
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py"],
            edges=[("a.py", "b.py")],
        )
    )

    result = ImpactAnalyzer().analyze(digraph, "b.py")

    assert result.target.score is None
    assert result.target.file == "b.py"


def test_analyze_with_metrics_reports_stage_timing() -> None:
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py"],
            edges=[("a.py", "b.py")],
        )
    )

    _, metrics = ImpactAnalyzer().analyze_with_metrics(digraph, "b.py")

    assert len(metrics) == 1
    assert metrics[0].stage_name == "impact_analysis"
    assert metrics[0].duration_ms >= 0.0
    assert metrics[0].files_processed == 1


def test_files_affected_percentage_rounded_to_three_decimals() -> None:
    """1 of 3 files affected → 33.333%."""
    digraph = to_digraph(
        GraphResult(
            nodes=["a.py", "b.py", "c.py"],
            edges=[("a.py", "c.py")],
        )
    )

    result = ImpactAnalyzer().analyze(digraph, "c.py")

    assert result.summary.total == 1
    assert result.summary.files_affected_percentage == 33.333

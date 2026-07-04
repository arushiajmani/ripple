"""Circular dependency detection on a file import graph.

CycleDetector takes a GraphResult (nodes + directed edges), finds simple cycles
via NetworkX, normalizes each cycle so rotations are treated as the same loop,
and returns CircularDependencyResult.

Not wired into AnalysisPipeline yet — call CycleDetector().detect(graph) directly.

Run tests from backend/:
    PYTHONPATH=. pytest tests/algorithms/test_cycles.py -v
"""

from __future__ import annotations

import networkx as nx

from app.graph.algorithms.digraph import graph_result_to_digraph
from app.graph.models import CircularDependencyResult, GraphResult


def normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Rotate so the cycle always starts at the lexicographically smallest node.

    ["b", "c", "a"] and ["a", "b", "c"] both become ("a", "b", "c"), so the same
    loop is not reported twice under different starting points.
    """
    if not cycle:
        return tuple()
    start = cycle.index(min(cycle))
    rotated = cycle[start:] + cycle[:start]
    return tuple(rotated)


class CycleDetector:
    """Find unique circular dependencies in a GraphResult."""

    def run(self, graph: GraphResult) -> CircularDependencyResult:
        digraph = graph_result_to_digraph(graph)
        seen: set[tuple[str, ...]] = set()
        cycles: list[list[str]] = []

        # NetworkX may yield the same loop starting at different nodes; normalize + seen.
        for cycle in nx.simple_cycles(digraph):
            key = normalize_cycle(cycle)
            if key in seen:
                continue
            seen.add(key)
            cycles.append(list(key))

        # Stable output: shorter cycles first, then lexicographic path order.
        cycles.sort(key=lambda c: (len(c), c))
        return CircularDependencyResult(cycles=cycles)

    # Alias used by tests and callers that prefer "detect" naming.
    detect = run

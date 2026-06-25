from __future__ import annotations

import networkx as nx

from app.graph.algorithms.digraph import graph_result_to_digraph
from app.graph.models import CircularDependencyResult, GraphResult


def normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    if not cycle:
        return tuple()
    start = cycle.index(min(cycle))
    rotated = cycle[start:] + cycle[:start]
    return tuple(rotated)


class CycleDetector:
    def run(self, graph: GraphResult) -> CircularDependencyResult:
        digraph = graph_result_to_digraph(graph)
        seen: set[tuple[str, ...]] = set()
        cycles: list[list[str]] = []

        for cycle in nx.simple_cycles(digraph):
            key = normalize_cycle(cycle)
            if key in seen:
                continue
            seen.add(key)
            cycles.append(list(key))

        cycles.sort(key=lambda c: (len(c), c))
        return CircularDependencyResult(cycles=cycles)

    detect = run

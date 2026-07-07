from __future__ import annotations

from typing import Protocol, TypeVar

import networkx as nx

T = TypeVar("T")


class GraphAlgorithm(Protocol[T]):
    """Contract for graph algorithms that take a NetworkX DiGraph and return a typed result."""

    def run(self, digraph: nx.DiGraph) -> T: ...

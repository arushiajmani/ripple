from __future__ import annotations

from typing import Protocol, TypeVar

from app.graph.models import GraphResult

T = TypeVar("T")


class GraphAlgorithm(Protocol[T]):
    """Contract for graph algorithms that take GraphResult and return a typed result."""

    def run(self, graph: GraphResult) -> T: ...

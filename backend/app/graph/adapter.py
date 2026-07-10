"""Bridge Ripple's domain graph (GraphResult) to NetworkX.

GraphAdapter is the single canonical conversion point between Ripple's
internal graph representation and the NetworkX DiGraph used by algorithms.
Conversion only — no algorithm logic belongs here.

Run tests from backend/:
    PYTHONPATH=. pytest tests/test_adapter.py -v
"""

from __future__ import annotations

import networkx as nx

from app.graph.models import GraphResult


class GraphAdapter:
    """Convert GraphResult into a reusable networkx.DiGraph."""

    def to_digraph(self, graph: GraphResult) -> nx.DiGraph:
        """Build a DiGraph with the same nodes and directed edges as graph."""
        digraph = nx.DiGraph()
        digraph.add_nodes_from(graph.nodes)
        digraph.add_edges_from(graph.edges)
        return digraph

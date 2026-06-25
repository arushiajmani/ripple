from __future__ import annotations

import networkx as nx

from app.graph.models import GraphResult


def graph_result_to_digraph(graph: GraphResult) -> nx.DiGraph:
    digraph = nx.DiGraph()
    digraph.add_nodes_from(graph.nodes)
    digraph.add_edges_from(graph.edges)
    return digraph

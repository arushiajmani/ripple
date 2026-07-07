"""GraphAdapter unit tests.

Run from backend/:
    PYTHONPATH=. pytest tests/test_adapter.py -v
"""

from __future__ import annotations

import networkx as nx

from app.graph import GraphAdapter, GraphBuilder, GraphResult, graph_result_to_digraph
from app.parser.models import FileAnalysis


def test_empty_graph_produces_empty_digraph() -> None:
    graph = GraphResult(nodes=[], edges=[])

    digraph = GraphAdapter().to_digraph(graph)

    assert isinstance(digraph, nx.DiGraph)
    assert digraph.number_of_nodes() == 0
    assert digraph.number_of_edges() == 0


def test_nodes_and_edges_are_copied() -> None:
    graph = GraphResult(
        nodes=["a.py", "b.py", "c.py"],
        edges=[("a.py", "b.py"), ("b.py", "c.py")],
    )

    digraph = GraphAdapter().to_digraph(graph)

    assert list(digraph.nodes) == ["a.py", "b.py", "c.py"]
    assert list(digraph.edges) == [("a.py", "b.py"), ("b.py", "c.py")]


def test_from_graph_builder_output() -> None:
    analyses = {
        "hub.py": FileAnalysis(file_path="hub.py"),
        "a.py": FileAnalysis(file_path="a.py", resolved_deps=["hub.py"]),
    }
    graph = GraphBuilder().build(analyses)

    digraph = GraphAdapter().to_digraph(graph)

    assert list(digraph.nodes) == sorted(analyses)
    assert ("a.py", "hub.py") in digraph.edges


def test_graph_result_to_digraph_wrapper_matches_adapter() -> None:
    graph = GraphResult(
        nodes=["x.py", "y.py"],
        edges=[("x.py", "y.py")],
    )

    wrapper = graph_result_to_digraph(graph)
    adapter = GraphAdapter().to_digraph(graph)

    assert list(wrapper.nodes) == list(adapter.nodes)
    assert list(wrapper.edges) == list(adapter.edges)

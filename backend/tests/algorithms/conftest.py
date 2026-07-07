from __future__ import annotations

import networkx as nx
import pytest

from app.graph import GraphAdapter, GraphBuilder, GraphResult
from app.parser.models import FileAnalysis


@pytest.fixture
def graph_adapter() -> GraphAdapter:
    return GraphAdapter()


@pytest.fixture
def build_graph():
    def _build(analyses: dict[str, FileAnalysis]) -> GraphResult:
        return GraphBuilder().build(analyses)

    return _build


@pytest.fixture
def build_digraph(graph_adapter: GraphAdapter, build_graph):
    def _build(analyses: dict[str, FileAnalysis]) -> nx.DiGraph:
        return graph_adapter.to_digraph(build_graph(analyses))

    return _build

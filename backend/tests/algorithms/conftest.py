from __future__ import annotations

import pytest

from app.graph import GraphBuilder, GraphResult
from app.parser.models import FileAnalysis


@pytest.fixture
def build_graph():
    def _build(analyses: dict[str, FileAnalysis]) -> GraphResult:
        return GraphBuilder().build(analyses)

    return _build

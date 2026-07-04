"""PipelineResult JSON serialization tests.

Run from backend/:
    PYTHONPATH=. pytest tests/test_serialize.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.pipeline import AnalysisPipeline, pipeline_result_to_dict

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"

# Fixed timestamp so dict equality tests are deterministic.
FIXED_AT = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


def _dict(result=None, **kwargs):
    result = result or AnalysisPipeline().run(FIXTURE_ROOT)
    kwargs.setdefault("created_at", FIXED_AT)
    return result.to_dict(**kwargs)


def test_top_level_keys_and_order() -> None:
    data = _dict()

    assert list(data.keys()) == [
        "metadata",
        "summary",
        "graph",
        "analysis",
        "files",
    ]


def test_metadata() -> None:
    data = _dict()

    assert data["metadata"] == {"created_at": "2026-07-04T12:00:00Z"}


def test_summary_stats() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    summary = _dict(result)["summary"]

    assert summary["file_count"] == len(result.analyses)
    assert summary["node_count"] == len(result.graph.nodes)
    assert summary["edge_count"] == len(result.graph.edges)
    assert summary["cycle_count"] == 1
    assert summary["class_count"] >= 1  # User, Helper in mini_repo
    assert summary["function_count"] >= 1
    assert summary["internal_dependency_count"] >= summary["edge_count"]
    assert summary["external_dependency_count"] >= 1


def test_graph_nodes_are_path_strings() -> None:
    """V1 nodes are path strings; rich data lives under files / analysis.scores."""
    data = _dict()
    graph = data["graph"]

    assert set(graph.keys()) == {"nodes", "edges"}
    assert all(isinstance(n, str) for n in graph["nodes"])
    assert "myapp/models.py" in graph["nodes"]


def test_graph_edges_are_lists_not_tuples() -> None:
    data = _dict()

    assert data["graph"]["edges"]
    for edge in data["graph"]["edges"]:
        assert isinstance(edge, list)
        assert len(edge) == 2


def test_analysis_groups_cycles_and_scores() -> None:
    data = _dict(top_n=2)
    analysis = data["analysis"]

    assert set(analysis.keys()) == {"cycles", "scores", "top_critical"}
    assert analysis["cycles"]["has_cycles"] is True
    assert analysis["cycles"]["cycle_count"] == 1
    assert ["myapp/models.py", "myapp/utils.py"] in analysis["cycles"]["cycles"]

    assert len(analysis["scores"]) == 4
    assert len(analysis["top_critical"]) == 2
    score = analysis["scores"][0]
    assert set(score) == {
        "file_path",
        "pagerank",
        "betweenness",
        "criticality",
        "in_degree",
        "out_degree",
    }
    criticalities = [s["criticality"] for s in analysis["scores"]]
    assert criticalities == sorted(criticalities, reverse=True)


def test_files_optional() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)

    with_files = _dict(result, include_files=True)
    without = _dict(result, include_files=False)

    assert "files" in with_files
    assert "myapp/models.py" in with_files["files"]
    assert "files" not in without
    assert list(without.keys()) == ["metadata", "summary", "graph", "analysis"]


def test_files_keep_full_file_analysis() -> None:
    auth = _dict()["files"]["myapp/auth.py"]

    assert auth["file_path"] == "myapp/auth.py"
    assert "myapp/models.py" in auth["resolved_deps"]
    assert "os" in auth["external_deps"]
    assert isinstance(auth["imports"], list)
    assert auth["imports"][0]["display"]
    assert "classes" in auth
    assert "functions" in auth
    assert "methods" in auth
    assert "line_count" in auth
    assert "has_syntax_error" in auth


def test_files_keys_are_sorted() -> None:
    keys = list(_dict()["files"])
    assert keys == sorted(keys)


def test_to_json_round_trip() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    text = result.to_json(created_at=FIXED_AT)
    data = json.loads(text)

    assert data["metadata"]["created_at"] == "2026-07-04T12:00:00Z"
    assert data["analysis"]["cycles"]["cycle_count"] == 1


def test_write_json_creates_file(tmp_path: Path) -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    out = tmp_path / "out" / "result.json"

    written = result.write_json(out, created_at=FIXED_AT)

    assert written == out.resolve()
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["node_count"] == 4
    assert data["graph"]["nodes"]


def test_pipeline_result_to_dict_matches_method() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    assert pipeline_result_to_dict(
        result, created_at=FIXED_AT
    ) == result.to_dict(created_at=FIXED_AT)

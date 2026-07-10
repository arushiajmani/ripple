"""PipelineResult JSON serialization tests.

Run from backend/:
    PYTHONPATH=. pytest tests/test_serialize.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.pipeline import AnalysisPipeline, pipeline_result_to_dict

from tests.support import FIXTURE_ROOT

# Fixed timestamp so dict equality tests are deterministic.
FIXED_AT = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


def _dict(result=None, **kwargs):
    result = result or AnalysisPipeline().run(FIXTURE_ROOT)
    kwargs.setdefault("generated_at", FIXED_AT)
    return result.to_dict(**kwargs)


def test_top_level_keys_and_order() -> None:
    data = _dict()

    assert list(data.keys()) == [
        "metadata",
        "summary",
        "statistics",
        "graph",
        "analysis",
        "files",
    ]


def test_metadata() -> None:
    data = _dict()

    assert data["metadata"] == {"generated_at": "2026-07-04T12:00:00Z"}


def test_summary_is_graph_level() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    summary = _dict(result)["summary"]

    assert set(summary.keys()) == {
        "file_count",
        "node_count",
        "edge_count",
        "cycle_count",
    }
    assert summary["file_count"] == len(result.analyses)
    assert summary["node_count"] == len(result.graph.nodes)
    assert summary["edge_count"] == len(result.graph.edges)
    assert summary["cycle_count"] == 1


def test_statistics_are_parser_level() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    data = _dict(result)
    stats = data["statistics"]

    assert set(stats.keys()) == {
        "class_count",
        "function_count",
        "internal_dependency_count",
        "external_dependency_count",
    }
    assert stats["class_count"] >= 1  # User, Helper in mini_repo
    assert stats["function_count"] >= 1
    # Repo-wide sums of resolved_deps / external_deps list lengths.
    assert stats["internal_dependency_count"] >= data["summary"]["edge_count"]
    assert stats["external_dependency_count"] >= 1


def test_repository_metadata_when_provided() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    data = result.to_dict(
        generated_at=FIXED_AT,
        repository={"name": "mini_repo", "source": "local"},
    )

    assert list(data.keys())[:3] == ["metadata", "repository", "summary"]
    assert data["repository"] == {"name": "mini_repo", "source": "local"}


def test_graph_nodes_are_path_strings() -> None:
    """V1 nodes are path strings; rich data lives under files / analysis.scores."""
    data = _dict()
    graph = data["graph"]

    assert set(graph.keys()) == {"nodes", "edges"}
    assert all(isinstance(n, str) for n in graph["nodes"])
    assert "myapp/models.py" in graph["nodes"]


def test_graph_edges_are_self_describing() -> None:
    """Edges use named fields so clients need not remember [importer, imported]."""
    data = _dict()

    assert data["graph"]["edges"]
    for edge in data["graph"]["edges"]:
        assert set(edge.keys()) == {"source", "target", "type"}
        assert edge["type"] == "imports"
        assert isinstance(edge["source"], str)
        assert isinstance(edge["target"], str)

    assert {
        "source": "myapp/auth.py",
        "target": "myapp/models.py",
        "type": "imports",
    } in data["graph"]["edges"]


def test_analysis_groups_cycles_and_scores() -> None:
    data = _dict()
    analysis = data["analysis"]

    assert set(analysis.keys()) == {"cycles", "scores"}
    assert analysis["cycles"]["has_cycles"] is True
    assert analysis["cycles"]["cycle_count"] == 1
    cycle = analysis["cycles"]["cycles"][0]
    assert cycle["nodes"] == ["myapp/models.py", "myapp/utils.py"]
    assert cycle["length"] == 2
    assert cycle["edges"] == [
        {
            "source": "myapp/models.py",
            "target": "myapp/utils.py",
            "type": "imports",
        },
        {
            "source": "myapp/utils.py",
            "target": "myapp/models.py",
            "type": "imports",
        },
    ]

    assert len(analysis["scores"]) == 4
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
    assert analysis["scores"][0]["pagerank"] == 0.4524
    assert analysis["scores"][0]["betweenness"] == 0.0
    assert analysis["scores"][0]["criticality"] == 0.6


def test_score_floats_rounded_to_four_decimal_places() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    score = _dict(result)["analysis"]["scores"][0]
    for field in ("pagerank", "betweenness", "criticality"):
        text = str(score[field])
        if "." in text:
            assert len(text.split(".")[1]) <= 4


def test_top_n_is_slice_of_scores() -> None:
    """JSON has no top_critical; consumers slice the ranked scores list."""
    from app.pipeline.serialize import node_score_to_dict

    result = AnalysisPipeline().run(FIXTURE_ROOT)
    data = _dict(result)
    assert data["analysis"]["scores"][:2] == [
        node_score_to_dict(s) for s in result.scores.top(2)
    ]


def test_files_optional() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)

    with_files = _dict(result, include_files=True)
    without = _dict(result, include_files=False)

    assert "files" in with_files
    assert "myapp/models.py" in with_files["files"]
    assert "files" not in without
    assert list(without.keys()) == [
        "metadata",
        "summary",
        "statistics",
        "graph",
        "analysis",
    ]


def test_import_serialization_omits_null_fields() -> None:
    from app.parser.models import ImportInfo
    from app.pipeline.serialize import import_info_to_dict

    assert import_info_to_dict(ImportInfo(module="os", type="import")) == {
        "module": "os",
        "type": "import",
        "display": "import os",
    }
    assert import_info_to_dict(
        ImportInfo(module="collections", name="namedtuple", type="from_import")
    ) == {
        "module": "collections",
        "type": "from_import",
        "name": "namedtuple",
        "display": "from collections import namedtuple",
    }
    assert import_info_to_dict(
        ImportInfo(module="numpy", alias="np", type="import")
    ) == {
        "module": "numpy",
        "type": "import",
        "alias": "np",
        "display": "import numpy as np",
    }
    assert import_info_to_dict(
        ImportInfo(
            module="decimal",
            name="Decimal",
            alias="D",
            type="from_import",
        )
    ) == {
        "module": "decimal",
        "type": "from_import",
        "name": "Decimal",
        "alias": "D",
        "display": "from decimal import Decimal as D",
    }


def test_function_serialization_omits_null_parent_class() -> None:
    from app.parser.models import FunctionInfo
    from app.pipeline.serialize import function_info_to_dict

    assert function_info_to_dict(FunctionInfo(name="helper")) == {"name": "helper"}
    assert function_info_to_dict(
        FunctionInfo(name="__init__", parent_class="MockMain")
    ) == {"name": "__init__", "parent_class": "MockMain"}


def test_files_keep_full_file_analysis() -> None:
    auth = _dict()["files"]["myapp/auth.py"]

    assert auth["file_path"] == "myapp/auth.py"
    assert "myapp/models.py" in auth["resolved_deps"]
    assert "os" in auth["external_deps"]
    assert isinstance(auth["imports"], list)
    assert auth["imports"][0] == {
        "module": "os",
        "type": "import",
        "display": "import os",
    }
    assert auth["imports"][1] == {
        "module": "requests",
        "type": "import",
        "display": "import requests",
    }
    assert "name" not in auth["imports"][0]
    assert "alias" not in auth["imports"][0]
    assert auth["functions"]
    assert "parent_class" not in auth["functions"][0]

    models = _dict()["files"]["myapp/models.py"]
    assert models["methods"][0] == {
        "name": "__init__",
        "parent_class": "User",
    }
    assert "parent_class" not in models["functions"][0] if models["functions"] else True
    assert "line_count" in auth
    assert "has_syntax_error" in auth


def test_files_keys_are_sorted() -> None:
    keys = list(_dict()["files"])
    assert keys == sorted(keys)


def test_to_json_round_trip() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    text = result.to_json(generated_at=FIXED_AT)
    data = json.loads(text)

    assert data["metadata"]["generated_at"] == "2026-07-04T12:00:00Z"
    assert data["analysis"]["cycles"]["cycle_count"] == 1


def test_write_json_creates_file(tmp_path: Path) -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    out = tmp_path / "out" / "result.json"

    written = result.write_json(out, generated_at=FIXED_AT)

    assert written == out.resolve()
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["node_count"] == 4
    assert data["graph"]["nodes"]


def test_pipeline_result_to_dict_matches_method() -> None:
    result = AnalysisPipeline().run(FIXTURE_ROOT)
    assert pipeline_result_to_dict(
        result, generated_at=FIXED_AT
    ) == result.to_dict(generated_at=FIXED_AT)

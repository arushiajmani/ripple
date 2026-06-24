from __future__ import annotations

import pytest

from app.graph import GraphBuilder
from app.parser.models import FileAnalysis


@pytest.fixture
def builder() -> GraphBuilder:
    return GraphBuilder()


def make_file(
    file_path: str,
    *,
    resolved_deps: list[str] | None = None,
    external_deps: list[str] | None = None,
    has_syntax_error: bool = False,
) -> FileAnalysis:
    return FileAnalysis(
        file_path=file_path,
        resolved_deps=resolved_deps or [],
        external_deps=external_deps or [],
        has_syntax_error=has_syntax_error,
    )


def test_empty_repository(builder: GraphBuilder) -> None:
    result = builder.build({})

    assert result.nodes == []
    assert result.edges == []


def test_single_file_no_dependencies(builder: GraphBuilder) -> None:
    analyses = {"myapp/models.py": make_file("myapp/models.py")}

    result = builder.build(analyses)

    assert result.nodes == ["myapp/models.py"]
    assert result.edges == []


def test_simple_dependency_graph(builder: GraphBuilder) -> None:
    analyses = {
        "myapp/models.py": make_file("myapp/models.py"),
        "myapp/utils.py": make_file(
            "myapp/utils.py",
            resolved_deps=["myapp/models.py"],
            external_deps=["json"],
        ),
        "myapp/auth.py": make_file(
            "myapp/auth.py",
            resolved_deps=["myapp/models.py", "myapp/utils.py"],
            external_deps=["os", "requests"],
        ),
    }

    result = builder.build(analyses)

    assert result.nodes == ["myapp/auth.py", "myapp/models.py", "myapp/utils.py"]
    assert result.edges == [
        ("myapp/auth.py", "myapp/models.py"),
        ("myapp/auth.py", "myapp/utils.py"),
        ("myapp/utils.py", "myapp/models.py"),
    ]


def test_missing_and_external_dependencies_ignored(builder: GraphBuilder) -> None:
    analyses = {
        "myapp/auth.py": make_file(
            "myapp/auth.py",
            resolved_deps=["myapp/missing.py"],
            external_deps=["requests", "os"],
        ),
        "myapp/utils.py": make_file(
            "myapp/utils.py",
            resolved_deps=[],
            external_deps=["json"],
        ),
    }

    result = builder.build(analyses)

    assert result.nodes == ["myapp/auth.py", "myapp/utils.py"]
    assert result.edges == []


def test_duplicate_resolved_deps_deduplicated(builder: GraphBuilder) -> None:
    analyses = {
        "myapp/models.py": make_file("myapp/models.py"),
        "myapp/auth.py": make_file(
            "myapp/auth.py",
            resolved_deps=["myapp/models.py", "myapp/models.py"],
        ),
    }

    result = builder.build(analyses)

    assert result.edges == [("myapp/auth.py", "myapp/models.py")]


def test_cyclic_imports_preserved(builder: GraphBuilder) -> None:
    analyses = {
        "myapp/a.py": make_file("myapp/a.py", resolved_deps=["myapp/b.py"]),
        "myapp/b.py": make_file("myapp/b.py", resolved_deps=["myapp/c.py"]),
        "myapp/c.py": make_file("myapp/c.py", resolved_deps=["myapp/a.py"]),
    }

    result = builder.build(analyses)

    assert result.nodes == ["myapp/a.py", "myapp/b.py", "myapp/c.py"]
    assert result.edges == [
        ("myapp/a.py", "myapp/b.py"),
        ("myapp/b.py", "myapp/c.py"),
        ("myapp/c.py", "myapp/a.py"),
    ]


def test_self_import_creates_self_loop(builder: GraphBuilder) -> None:
    analyses = {
        "myapp/auth.py": make_file(
            "myapp/auth.py",
            resolved_deps=["myapp/auth.py"],
        ),
    }

    result = builder.build(analyses)

    assert result.nodes == ["myapp/auth.py"]
    assert result.edges == [("myapp/auth.py", "myapp/auth.py")]


def test_dict_key_used_as_node_not_file_path_field(builder: GraphBuilder) -> None:
    analyses = {
        "myapp/auth.py": make_file(
            "wrong/path.py",
            resolved_deps=["myapp/models.py"],
        ),
        "myapp/models.py": make_file("myapp/models.py"),
    }

    result = builder.build(analyses)

    assert result.nodes == ["myapp/auth.py", "myapp/models.py"]
    assert result.edges == [("myapp/auth.py", "myapp/models.py")]


def test_syntax_error_file_still_contributes_nodes_and_edges(
    builder: GraphBuilder,
) -> None:
    analyses = {
        "myapp/broken.py": make_file(
            "myapp/broken.py",
            resolved_deps=["myapp/models.py"],
            has_syntax_error=True,
        ),
        "myapp/models.py": make_file("myapp/models.py"),
    }

    result = builder.build(analyses)

    assert result.nodes == ["myapp/broken.py", "myapp/models.py"]
    assert result.edges == [("myapp/broken.py", "myapp/models.py")]

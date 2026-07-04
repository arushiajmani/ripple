"""AnalysisPipeline tests.

Integration: real parse → graph → cycle detection on temp repos / mini_repo.
Unit-style: one monkeypatch case stubs parse_repository.

Run from backend/:
    PYTHONPATH=. pytest tests/test_pipeline.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.parser.models import FileAnalysis
from app.parser.repository import collect_python_files
from app.pipeline import AnalysisPipeline

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


@pytest.fixture
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline()


def write_repo(root: Path, files: dict[str, str]) -> Path:
    for rel_path, content in files.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def expected_edges(analyses: dict[str, FileAnalysis]) -> list[tuple[str, str]]:
    node_set = set(analyses)
    return sorted(
        {
            (path, dep)
            for path, analysis in analyses.items()
            for dep in analysis.resolved_deps
            if dep in node_set
        }
    )


# --- Acyclic graphs ---

def test_empty_graph(pipeline: AnalysisPipeline, tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()

    result = pipeline.run(repo)

    assert result.analyses == {}
    assert result.graph.nodes == []
    assert result.graph.edges == []
    assert result.cycles.cycles == []
    assert not result.cycles.has_cycles


def test_single_node(pipeline: AnalysisPipeline, tmp_path: Path) -> None:
    repo = write_repo(
        tmp_path / "single",
        {"solo/main.py": "VALUE = 1\n"},
    )

    result = pipeline.run(repo)

    assert result.graph.nodes == ["solo/main.py"]
    assert result.graph.edges == []
    assert not result.cycles.has_cycles


def test_simple_dependency_graph(pipeline: AnalysisPipeline, tmp_path: Path) -> None:
    repo = write_repo(
        tmp_path / "simple",
        {
            "app/__init__.py": "",
            "app/models.py": "class User:\n    pass\n",
            "app/utils.py": "from app.models import User\n",
            "app/auth.py": (
                "from app.models import User\n"
                "from app.utils import User as UtilsUser\n"
            ),
        },
    )

    result = pipeline.run(repo)

    assert result.graph.nodes == sorted(result.analyses)
    assert ("app/auth.py", "app/models.py") in result.graph.edges
    assert ("app/auth.py", "app/utils.py") in result.graph.edges
    assert ("app/utils.py", "app/models.py") in result.graph.edges
    assert result.graph.edges == expected_edges(result.analyses)
    assert not result.cycles.has_cycles


def test_dedup_edges(pipeline: AnalysisPipeline, tmp_path: Path) -> None:
    repo = write_repo(
        tmp_path / "dedup",
        {
            "app/__init__.py": "",
            "app/models.py": "class User:\n    pass\n",
            "app/auth.py": (
                "import app.models\n"
                "from app.models import User\n"
            ),
        },
    )

    result = pipeline.run(repo)

    assert result.graph.edges == [("app/auth.py", "app/models.py")]
    assert not result.cycles.has_cycles


def test_ignore_missing_deps(
    pipeline: AnalysisPipeline,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """resolved_deps pointing outside the analyses dict produce no edges."""
    analyses = {
        "pkg/main.py": FileAnalysis(
            file_path="pkg/main.py",
            resolved_deps=["pkg/missing.py"],
            external_deps=["requests"],
        ),
        "pkg/helper.py": FileAnalysis(
            file_path="pkg/helper.py",
            resolved_deps=[],
            external_deps=["json"],
        ),
    }
    monkeypatch.setattr(
        "app.pipeline.pipeline.parse_repository",
        lambda _path: analyses,
    )

    result = pipeline.run(tmp_path)

    assert result.graph.nodes == ["pkg/helper.py", "pkg/main.py"]
    assert result.graph.edges == []
    assert not result.cycles.has_cycles


def test_deterministic_ordering(pipeline: AnalysisPipeline, tmp_path: Path) -> None:
    repo = write_repo(
        tmp_path / "ordering",
        {
            "z_pkg/__init__.py": "",
            "z_pkg/z.py": "from z_pkg.a import A\n",
            "z_pkg/a.py": "class A:\n    pass\n",
            "m_pkg/__init__.py": "",
            "m_pkg/m.py": "class M:\n    pass\n",
        },
    )

    first = pipeline.run(repo)
    second = pipeline.run(repo)

    assert first.graph.nodes == sorted(first.graph.nodes)
    assert first.graph.edges == sorted(first.graph.edges)
    assert first.graph.nodes == second.graph.nodes
    assert first.graph.edges == second.graph.edges
    assert first.cycles.cycles == second.cycles.cycles
    assert first.graph.nodes == [
        "m_pkg/__init__.py",
        "m_pkg/m.py",
        "z_pkg/__init__.py",
        "z_pkg/a.py",
        "z_pkg/z.py",
    ]


# --- Cycles through the full pipeline ---

def test_small_cycle(pipeline: AnalysisPipeline, tmp_path: Path) -> None:
    """A → B → C → A is preserved in the graph and reported on PipelineResult.cycles."""
    repo = write_repo(
        tmp_path / "cycle",
        {
            "cycle/__init__.py": "",
            "cycle/a.py": "import cycle.b\n",
            "cycle/b.py": "import cycle.c\n",
            "cycle/c.py": "import cycle.a\n",
        },
    )

    result = pipeline.run(repo)

    assert result.graph.nodes == [
        "cycle/__init__.py",
        "cycle/a.py",
        "cycle/b.py",
        "cycle/c.py",
    ]
    assert result.graph.edges == [
        ("cycle/a.py", "cycle/b.py"),
        ("cycle/b.py", "cycle/c.py"),
        ("cycle/c.py", "cycle/a.py"),
    ]
    assert result.cycles.has_cycles
    assert result.cycles.cycle_count == 1
    assert result.cycles.cycles == [
        ["cycle/a.py", "cycle/b.py", "cycle/c.py"],
    ]


def test_run_parses_mini_repo_integration(pipeline: AnalysisPipeline) -> None:
    """mini_repo is intentionally cyclic (models ↔ utils); edges match resolved_deps."""
    result = pipeline.run(FIXTURE_ROOT)

    assert set(result.analyses) == collect_python_files(FIXTURE_ROOT)
    assert result.graph.nodes == sorted(result.analyses)
    assert result.graph.edges == expected_edges(result.analyses)
    assert len(result.graph.edges) > 0
    assert ("myapp/models.py", "myapp/utils.py") in result.graph.edges
    assert ("myapp/utils.py", "myapp/models.py") in result.graph.edges
    assert result.cycles.has_cycles
    assert result.cycles.cycle_count == 1
    assert result.cycles.cycles == [["myapp/models.py", "myapp/utils.py"]]


def test_run_raises_for_non_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "not_a_repo.py"
    file_path.write_text("x = 1\n")

    with pytest.raises(NotADirectoryError):
        AnalysisPipeline().run(file_path)

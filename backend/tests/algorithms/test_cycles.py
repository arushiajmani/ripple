from __future__ import annotations

from typing import Callable

from app.graph import CycleDetector, GraphResult
from app.parser.models import FileAnalysis

from tests.algorithms.helpers import make_file


def test_empty_graph_has_no_cycles() -> None:
    graph = GraphResult(nodes=[], edges=[])

    result = CycleDetector().detect(graph)

    assert result.cycles == []
    assert not result.has_cycles
    assert result.cycle_count == 0


def test_acyclic_repository_has_no_cycles(
    build_graph: Callable[[dict[str, FileAnalysis]], GraphResult],
) -> None:
    graph = build_graph(
        {
            "myapp/models.py": make_file("myapp/models.py"),
            "myapp/utils.py": make_file(
                "myapp/utils.py",
                resolved_deps=["myapp/models.py"],
            ),
            "myapp/auth.py": make_file(
                "myapp/auth.py",
                resolved_deps=["myapp/models.py", "myapp/utils.py"],
            ),
        }
    )

    result = CycleDetector().detect(graph)

    assert result.cycles == []
    assert not result.has_cycles


def test_simple_three_node_cycle(
    build_graph: Callable[[dict[str, FileAnalysis]], GraphResult],
) -> None:
    graph = build_graph(
        {
            "myapp/a.py": make_file("myapp/a.py", resolved_deps=["myapp/b.py"]),
            "myapp/b.py": make_file("myapp/b.py", resolved_deps=["myapp/c.py"]),
            "myapp/c.py": make_file("myapp/c.py", resolved_deps=["myapp/a.py"]),
        }
    )

    result = CycleDetector().detect(graph)

    assert result.has_cycles
    assert result.cycle_count == 1
    assert result.cycles == [["myapp/a.py", "myapp/b.py", "myapp/c.py"]]


def test_self_loop_is_a_cycle(
    build_graph: Callable[[dict[str, FileAnalysis]], GraphResult],
) -> None:
    graph = build_graph(
        {
            "myapp/auth.py": make_file(
                "myapp/auth.py",
                resolved_deps=["myapp/auth.py"],
            ),
        }
    )

    result = CycleDetector().detect(graph)

    assert result.cycles == [["myapp/auth.py"]]
    assert result.cycle_count == 1


def test_two_disjoint_cycles(
    build_graph: Callable[[dict[str, FileAnalysis]], GraphResult],
) -> None:
    graph = build_graph(
        {
            "myapp/a.py": make_file("myapp/a.py", resolved_deps=["myapp/b.py"]),
            "myapp/b.py": make_file("myapp/b.py", resolved_deps=["myapp/a.py"]),
            "myapp/x.py": make_file("myapp/x.py", resolved_deps=["myapp/y.py"]),
            "myapp/y.py": make_file("myapp/y.py", resolved_deps=["myapp/x.py"]),
        }
    )

    result = CycleDetector().detect(graph)

    assert result.cycle_count == 2
    assert ["myapp/a.py", "myapp/b.py"] in result.cycles
    assert ["myapp/x.py", "myapp/y.py"] in result.cycles


def test_cycle_normalized_to_lexicographic_start() -> None:
    graph = GraphResult(
        nodes=["myapp/b.py", "myapp/c.py", "myapp/a.py"],
        edges=[
            ("myapp/a.py", "myapp/b.py"),
            ("myapp/b.py", "myapp/c.py"),
            ("myapp/c.py", "myapp/a.py"),
        ],
    )

    result = CycleDetector().detect(graph)

    assert result.cycles == [["myapp/a.py", "myapp/b.py", "myapp/c.py"]]


def test_detect_deduplicates_rotations() -> None:
    graph = GraphResult(
        nodes=["myapp/a.py", "myapp/b.py"],
        edges=[("myapp/a.py", "myapp/b.py"), ("myapp/b.py", "myapp/a.py")],
    )

    result = CycleDetector().detect(graph)

    assert result.cycle_count == 1
    assert result.cycles == [["myapp/a.py", "myapp/b.py"]]


def test_run_matches_detect() -> None:
    graph = GraphResult(
        nodes=["myapp/a.py", "myapp/b.py"],
        edges=[("myapp/a.py", "myapp/b.py"), ("myapp/b.py", "myapp/a.py")],
    )
    detector = CycleDetector()

    assert detector.run(graph) == detector.detect(graph)

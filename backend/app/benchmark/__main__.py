"""CLI entry: python -m app.benchmark --repo <path>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.metrics import format_metrics_table
from app.pipeline import AnalysisPipeline

RULE = "─" * 64

PERFORMANCE_NOTES = """\
Performance Notes
-----------------

Benchmark measures steady-state algorithm performance.

A single untimed PageRank warm-up is executed to exclude
one-time NetworkX/SciPy backend initialization from the
reported timings."""


def _section(title: str) -> None:
    print()
    print(RULE)
    print(f"  {title}")
    print(RULE)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.benchmark",
        description="Run the analysis pipeline and print per-stage timing.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Project root directory to analyze",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    repo_path = args.repo.resolve()
    if not repo_path.is_dir():
        print(f"Not a directory: {repo_path}", file=sys.stderr)
        sys.exit(1)

    result = AnalysisPipeline().run(repo_path)

    _section("Benchmark summary")
    print(f"  repo     {repo_path}")
    print(f"  files    {len(result.analyses)}")
    print(f"  nodes    {len(result.graph.nodes)}")
    print(f"  edges    {len(result.graph.edges)}")
    print(f"  cycles   {result.cycles.cycle_count}")

    _section("Stage timings")
    print(format_metrics_table(result.metrics))

    if result.analyses:
        avg_ast = next(
            (m.duration_ms for m in result.metrics if m.stage_name == "ast_parsing"),
            0.0,
        ) / len(result.analyses)
        print()
        print(f"  ast_parsing avg per file: {avg_ast:.2f} ms")

    print()
    print(PERFORMANCE_NOTES)
    print()


if __name__ == "__main__":
    main()

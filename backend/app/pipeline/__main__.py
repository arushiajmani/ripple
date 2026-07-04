"""CLI entry: python -m app.pipeline <repo-path> [--json PATH]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.graph.models import CircularDependencyResult, GraphResult, ScoringResult
from app.pipeline import AnalysisPipeline, PipelineResult

# How many highest-criticality files to print / put in top_critical JSON.
TOP_CRITICAL = 10
RULE = "─" * 64


def _section(title: str) -> None:
    print()
    print(RULE)
    print(f"  {title}")
    print(RULE)


def _print_summary(repo_path: Path, result: PipelineResult) -> None:
    _section("Summary")
    print(f"  repo     {repo_path}")
    print(f"  files    {len(result.analyses)}")
    print(f"  nodes    {len(result.graph.nodes)}")
    print(f"  edges    {len(result.graph.edges)}")
    print(f"  cycles   {result.cycles.cycle_count}")


def _print_edges(graph: GraphResult) -> None:
    _section(f"Dependency edges ({len(graph.edges)})")
    if not graph.edges:
        print("  (none)")
        return
    width = max(len(source) for source, _ in graph.edges)
    for source, target in graph.edges:
        print(f"  {source:<{width}}  →  {target}")


def _print_cycles(cycles: CircularDependencyResult) -> None:
    _section(f"Circular dependencies ({cycles.cycle_count})")
    if not cycles.has_cycles:
        print("  (none)")
        return
    for i, cycle in enumerate(cycles.cycles, start=1):
        path = " → ".join(cycle) + f" → {cycle[0]}"
        print(f"  {i}. {path}")


def _print_top_critical(scores: ScoringResult) -> None:
    top = scores.top(TOP_CRITICAL)
    _section(f"Top critical files ({len(top)})")
    if not top:
        print("  (none)")
        return

    # Column headers — criticality = risk; pagerank = depended-on;
    # betweenness = bridge; in = importers; out = imports.
    print(
        f"  {'#':>3}  {'file':<36}  {'crit':>6}  {'pr':>6}  "
        f"{'btw':>6}  {'in':>3}  {'out':>3}"
    )
    print(
        f"  {'─' * 3}  {'─' * 36}  {'─' * 6}  {'─' * 6}  "
        f"{'─' * 6}  {'─' * 3}  {'─' * 3}"
    )
    for rank, node in enumerate(top, start=1):
        name = node.file_path
        if len(name) > 36:
            name = "…" + name[-35:]
        print(
            f"  {rank:>3}  {name:<36}  "
            f"{node.criticality:>6.3f}  "
            f"{node.pagerank:>6.3f}  "
            f"{node.betweenness:>6.3f}  "
            f"{node.in_degree:>3}  "
            f"{node.out_degree:>3}"
        )
    print()
    print("  crit = change-risk (0.6·norm(PR) + 0.4·norm(BT))")
    print("  pr   = PageRank (how depended-on)")
    print("  btw  = betweenness (bridge / bottleneck)")
    print("  in   = # project files that import this file")
    print("  out  = # project files this file imports")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.pipeline",
        description="Run parse → graph → cycles → scores on a project directory.",
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Project root directory (not a package subfolder)",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        type=Path,
        help="Write full analysis JSON to PATH (e.g. result.json)",
    )
    parser.add_argument(
        "--no-files",
        action="store_true",
        help="Omit per-file parse data (files) from JSON (smaller file)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    repo_path = args.repo_path.resolve()
    if not repo_path.is_dir():
        print(f"Not a directory: {repo_path}", file=sys.stderr)
        sys.exit(1)

    result = AnalysisPipeline().run(repo_path)

    _print_summary(repo_path, result)
    _print_edges(result.graph)
    _print_cycles(result.cycles)
    _print_top_critical(result.scores)

    if args.json is not None:
        out = result.write_json(
            args.json,
            top_n=TOP_CRITICAL,
            include_files=not args.no_files,
        )
        _section("JSON export")
        print(f"  wrote  {out}")

    print()


if __name__ == "__main__":
    main()

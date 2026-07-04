"""CLI entry: python -m app.pipeline <repo-path>"""

from __future__ import annotations

import sys
from pathlib import Path

from app.pipeline import AnalysisPipeline


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.pipeline <repo-path>", file=sys.stderr)
        sys.exit(1)

    repo_path = Path(sys.argv[1]).resolve()
    if not repo_path.is_dir():
        print(f"Not a directory: {repo_path}", file=sys.stderr)
        sys.exit(1)

    result = AnalysisPipeline().run(repo_path)

    print(f"files: {len(result.analyses)}")
    print(f"nodes: {len(result.graph.nodes)}")
    print(f"edges: {len(result.graph.edges)}")
    print(f"cycles: {result.cycles.cycle_count}")
    print("edges:")
    for source, target in result.graph.edges:
        print(f"  {source} -> {target}")
    if result.cycles.has_cycles:
        print("circular_dependencies:")
        for cycle in result.cycles.cycles:
            print(f"  {' -> '.join(cycle)} -> {cycle[0]}")


if __name__ == "__main__":
    main()

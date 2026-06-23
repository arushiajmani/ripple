from __future__ import annotations

import sys
from pathlib import Path

from app.parser.ast_parser import ASTParser, _print_analysis
from app.parser.models import FileAnalysis

SKIP_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
})


def collect_python_files(root: Path) -> set[str]:
    root = root.resolve()
    project_files: set[str] = set()

    for path in root.rglob("*.py"):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        project_files.add(path.relative_to(root).as_posix())

    return project_files


def parse_repository(repo_path: str | Path) -> dict[str, FileAnalysis]:
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    project_files = collect_python_files(root)
    parser = ASTParser(project_files=project_files)
    analyses: dict[str, FileAnalysis] = {}

    for rel_path in sorted(project_files):
        content = (root / rel_path).read_text(encoding="utf-8", errors="ignore")
        analyses[rel_path] = parser.parse_file(rel_path, content)

    return analyses


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m app.parser.repo_parser <path-to-repo> [file]",
            file=sys.stderr,
        )
        sys.exit(1)

    repo_root = Path(sys.argv[1]).resolve()
    if not repo_root.is_dir():
        print(f"Not a directory: {repo_root}", file=sys.stderr)
        sys.exit(1)

    analyses = parse_repository(repo_root)

    if len(sys.argv) > 2:
        rel_path = sys.argv[2].replace("\\", "/")
        analysis = analyses.get(rel_path)
        if analysis is None:
            print(f"File not found in repo: {rel_path}", file=sys.stderr)
            sys.exit(1)
        print("=" * 60)
        _print_analysis(analysis)
        return

    for rel_path, analysis in analyses.items():
        print("=" * 60)
        _print_analysis(analysis)
        print()


if __name__ == "__main__":
    main()

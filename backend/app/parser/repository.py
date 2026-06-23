from __future__ import annotations

from pathlib import Path

from app.parser.ast_parser import ASTParser
from app.parser.models import SKIP_DIRS, FileAnalysis


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

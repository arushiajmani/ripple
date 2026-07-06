from __future__ import annotations

from pathlib import Path

from app.parser.ast_parser import ASTParser
from app.parser.models import SKIP_DIRS, FileAnalysis
from app.metrics import StageMetric, StageTimer


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
    analyses, _metrics = parse_repository_with_metrics(repo_path)
    return analyses


def parse_repository_with_metrics(
    repo_path: str | Path,
) -> tuple[dict[str, FileAnalysis], list[StageMetric]]:
    """Walk repo, parse files, and record per-stage timings."""
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    with StageTimer() as discovery:
        project_files = collect_python_files(root)
    file_count = len(project_files)

    parser = ASTParser(project_files=project_files)
    analyses: dict[str, FileAnalysis] = {}
    ast_ms = 0.0
    resolve_ms = 0.0

    for rel_path in sorted(project_files):
        content = (root / rel_path).read_text(encoding="utf-8", errors="ignore")
        analysis, file_ast_ms, file_resolve_ms = parser.parse_file_timed(
            rel_path, content
        )
        analyses[rel_path] = analysis
        ast_ms += file_ast_ms
        resolve_ms += file_resolve_ms

    metrics = [
        StageMetric("file_discovery", discovery.duration_ms, files_processed=None),
        StageMetric("ast_parsing", ast_ms, files_processed=file_count),
        StageMetric(
            "import_resolution", resolve_ms, files_processed=file_count
        ),
    ]
    return analyses, metrics

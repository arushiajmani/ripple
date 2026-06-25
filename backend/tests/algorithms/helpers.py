from __future__ import annotations

from app.parser.models import FileAnalysis


def make_file(
    file_path: str,
    *,
    resolved_deps: list[str] | None = None,
) -> FileAnalysis:
    return FileAnalysis(
        file_path=file_path,
        resolved_deps=resolved_deps or [],
    )

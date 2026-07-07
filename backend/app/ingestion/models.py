"""Shared ingestion result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.parser.repository import collect_python_files


@dataclass(frozen=True)
class RepositoryHandle:
    """Local checkout of an ingested repository.

    The analysis pipeline only needs ``local_path``; how that directory was
    produced (zip extract, git clone, etc.) is opaque to downstream stages.
    """

    job_id: str
    local_path: Path
    source: str = "zip"
    name: str = ""

    @property
    def python_files(self) -> set[str]:
        """Relative ``.py`` paths under ``local_path`` (skips venv, ``__pycache__``, …)."""
        return collect_python_files(self.local_path)


# Backward-compatible alias used across the codebase.
IngestionResult = RepositoryHandle

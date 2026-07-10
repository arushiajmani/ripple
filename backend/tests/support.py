"""Shared test helpers.

Centralizes fixture-repo paths and the small builders that were previously
copy-pasted across the suite (mini_repo zip bytes, FileAnalysis factory,
GraphResult → DiGraph conversion).
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import networkx as nx

from app.graph import GraphAdapter, GraphResult
from app.ingestion import CloneError
from app.parser.models import FileAnalysis

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


def zip_bytes(members: dict[str, bytes]) -> bytes:
    """Build an in-memory zip from ``{name: content}`` members."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def write_zip(path: Path, members: dict[str, bytes]) -> None:
    """Write a zip of ``{name: content}`` members to ``path``."""
    Path(path).write_bytes(zip_bytes(members))


def mini_repo_zip_bytes() -> bytes:
    """Zip the mini_repo fixture, keeping the ``mini_repo/`` top-level folder."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for py_file in FIXTURE_ROOT.rglob("*.py"):
            rel = py_file.relative_to(FIXTURE_ROOT.parent).as_posix()
            archive.write(py_file, rel)
    return buffer.getvalue()


def write_mini_repo_zip(path: Path) -> None:
    """Write the mini_repo fixture zip to ``path``."""
    Path(path).write_bytes(mini_repo_zip_bytes())


class StubRemoteChecker:
    """Fake ``RemoteRepoChecker`` — records checked URLs, returns ``exists``."""

    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists
        self.checked_urls: list[str] = []

    def repo_exists(self, clone_url: str) -> bool:
        self.checked_urls.append(clone_url)
        return self.exists


class StubCloner:
    """Fake ``RepoCloner`` — copies a local fixture tree instead of cloning."""

    def __init__(self, source_dir: Path = FIXTURE_ROOT) -> None:
        self.source_dir = source_dir
        self.calls: list[tuple[str, Path]] = []

    def clone(self, clone_url: str, dest: Path) -> None:
        self.calls.append((clone_url, dest))
        shutil.copytree(self.source_dir, dest, dirs_exist_ok=True)


class FailingCloner:
    """Fake ``RepoCloner`` that always raises ``CloneError``.

    With ``write_partial=True`` it first drops a file into ``dest`` so tests can
    assert the partial directory is cleaned up.
    """

    def __init__(self, message: str = "git clone failed", *, write_partial: bool = False) -> None:
        self.message = message
        self.write_partial = write_partial

    def clone(self, clone_url: str, dest: Path) -> None:
        if self.write_partial:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "partial.txt").write_text("partial")
        raise CloneError(self.message)


def make_file(
    file_path: str,
    *,
    resolved_deps: list[str] | None = None,
    external_deps: list[str] | None = None,
    has_syntax_error: bool = False,
) -> FileAnalysis:
    """Build a minimal ``FileAnalysis`` for graph/algorithm tests."""
    return FileAnalysis(
        file_path=file_path,
        resolved_deps=resolved_deps or [],
        external_deps=external_deps or [],
        has_syntax_error=has_syntax_error,
    )


def to_digraph(graph: GraphResult) -> nx.DiGraph:
    """Convert a ``GraphResult`` to a NetworkX DiGraph via the canonical adapter."""
    return GraphAdapter().to_digraph(graph)

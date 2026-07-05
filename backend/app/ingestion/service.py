"""Zip ingestion: extract uploaded archives to a temp job directory.

Extracted layout::

    /tmp/ripple/{job_id}/
        ... contents of the zip ...

``IngestionResult.local_path`` is that directory. Pass it to ``AnalysisPipeline.run``
or ``parse_repository``. Call ``cleanup`` when analysis finishes.
"""

from __future__ import annotations

import io
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.parser.repository import collect_python_files

DEFAULT_BASE_DIR = Path("/tmp/ripple")


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of extracting one zip archive."""

    job_id: str
    local_path: Path

    @property
    def python_files(self) -> set[str]:
        """Relative ``.py`` paths under ``local_path`` (skips venv, ``__pycache__``, …)."""
        return collect_python_files(self.local_path)


class IngestionService:
    """Accept a zip file and extract it to ``{base_dir}/{job_id}/``."""

    def __init__(self, base_dir: Path | str = DEFAULT_BASE_DIR) -> None:
        self._base_dir = Path(base_dir)

    def ingest_zip(
        self,
        zip_path: str | Path,
        *,
        job_id: str | None = None,
    ) -> IngestionResult:
        """Extract ``zip_path`` to ``{base_dir}/{job_id}/`` and return the job paths."""
        path = Path(zip_path)
        if not path.is_file():
            raise FileNotFoundError(f"Zip file not found: {path}")

        job = job_id or str(uuid.uuid4())
        dest = self._job_dir(job)
        dest.mkdir(parents=True, exist_ok=False)

        try:
            with zipfile.ZipFile(path, "r") as archive:
                self._safe_extract(archive, dest)
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            raise

        return IngestionResult(job_id=job, local_path=dest)

    def ingest_zip_bytes(
        self,
        data: bytes,
        *,
        job_id: str | None = None,
    ) -> IngestionResult:
        """Extract zip bytes (e.g. from an HTTP upload) to a new job directory."""
        job = job_id or str(uuid.uuid4())
        dest = self._job_dir(job)
        dest.mkdir(parents=True, exist_ok=False)

        try:
            with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
                self._safe_extract(archive, dest)
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            raise

        return IngestionResult(job_id=job, local_path=dest)

    def cleanup(self, job: IngestionResult | str) -> None:
        """Remove the extracted job directory."""
        job_id = job.job_id if isinstance(job, IngestionResult) else job
        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)

    def _job_dir(self, job_id: str) -> Path:
        return self._base_dir / job_id

    @staticmethod
    def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
        """Extract members under ``dest``, rejecting zip-slip paths."""
        dest_root = dest.resolve()
        for member in archive.infolist():
            # Skip directory entries; files create parent dirs on extract.
            if member.is_dir():
                continue
            target = (dest_root / member.filename).resolve()
            if not _is_within_directory(dest_root, target):
                raise ValueError(f"Unsafe path in zip archive: {member.filename!r}")
        archive.extractall(dest_root)


def _is_within_directory(root: Path, target: Path) -> bool:
    """True if ``target`` is ``root`` or a path inside ``root``."""
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False

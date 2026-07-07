"""Zip archive ingestion."""

from __future__ import annotations

import io
import shutil
import uuid
import zipfile
from pathlib import Path

from app.ingestion.models import RepositoryHandle


class ZipIngestion:
    """Extract zip archives to ``{base_dir}/{job_id}/``."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def ingest_path(
        self,
        zip_path: str | Path,
        *,
        job_id: str | None = None,
        name: str = "",
    ) -> RepositoryHandle:
        """Extract ``zip_path`` to a new job directory."""
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

        return RepositoryHandle(
            job_id=job,
            local_path=dest,
            source="zip",
            name=name or path.stem,
        )

    def ingest_bytes(
        self,
        data: bytes,
        *,
        job_id: str | None = None,
        name: str = "",
    ) -> RepositoryHandle:
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

        return RepositoryHandle(
            job_id=job,
            local_path=dest,
            source="zip",
            name=name or "upload",
        )

    def cleanup(self, job_id: str) -> None:
        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)

    def _job_dir(self, job_id: str) -> Path:
        return self._base_dir / job_id

    @staticmethod
    def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
        """Extract members under ``dest``, rejecting zip-slip paths."""
        dest_root = dest.resolve()
        for member in archive.infolist():
            if member.is_dir():
                continue
            target = (dest_root / member.filename).resolve()
            if not _is_within_directory(dest_root, target):
                raise ValueError(f"Unsafe path in zip archive: {member.filename!r}")
        archive.extractall(dest_root)


def _is_within_directory(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False

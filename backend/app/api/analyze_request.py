"""Shared request handling for the two analyze endpoints.

**Repository Analysis** — ``POST /api/repos/analyze`` (slim response: ids + repository).
**Quick Analysis** — ``POST /api/analyze`` (full graph/scores/files inline).

Both call this module. Validation, ingestion, pipeline run, and persistence are
identical; only the HTTP response shape differs. Domain errors propagate to
``app.api.errors``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.analysis import AnalyzeRun, analyze_github_url, analyze_uploaded_zip
from app.db.context import RepositoryPersistContext
from app.ingestion import IngestionService, parse_github_url
from app.pipeline.serialize import build_repository
from app.pipeline.store import AnalysisStore


async def run_analyze_request(
    file: UploadFile | None,
    github_url: str | None,
    ingestion: IngestionService,
    store: AnalysisStore,
    db: Session,
) -> tuple[AnalyzeRun, dict[str, str]]:
    """Validate inputs, ingest + analyze, and return ``(run, repository)``.

    ``repository`` is the ``{"name", "source"}`` block both response shapes need.
    """
    has_file = file is not None and file.filename
    has_github = bool(github_url and github_url.strip())

    if has_file and has_github:
        raise HTTPException(
            status_code=400,
            detail="Provide either a zip file or a GitHub URL, not both",
        )
    if not has_file and not has_github:
        raise HTTPException(
            status_code=400,
            detail="Provide a zip file upload or a github_url form field",
        )

    if has_file:
        assert file is not None
        return await _run_zip_upload(file, ingestion, store, db)

    assert github_url is not None
    return _run_github_submission(github_url, ingestion, store, db)


async def _run_zip_upload(
    file: UploadFile,
    ingestion: IngestionService,
    store: AnalysisStore,
    db: Session,
) -> tuple[AnalyzeRun, dict[str, str]]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")

    zip_name = Path(file.filename or "upload.zip").stem
    persist_context = RepositoryPersistContext(
        source="zip",
        name=zip_name,
        repo_name=zip_name,
        file_hash=hashlib.sha256(data).hexdigest(),
    )
    run = analyze_uploaded_zip(
        ingestion,
        data,
        zip_name=zip_name,
        store=store,
        session=db,
        persist_context=persist_context,
    )
    return run, build_repository(name=zip_name, source="zip")


def _run_github_submission(
    github_url: str,
    ingestion: IngestionService,
    store: AnalysisStore,
    db: Session,
) -> tuple[AnalyzeRun, dict[str, str]]:
    parsed = parse_github_url(github_url)
    persist_context = RepositoryPersistContext(
        source="github",
        name=parsed.display_name,
        owner=parsed.owner,
        repo_name=parsed.repo,
    )
    run = analyze_github_url(
        ingestion,
        github_url,
        store=store,
        session=db,
        persist_context=persist_context,
    )
    return run, build_repository(name=parsed.display_name, source="github")

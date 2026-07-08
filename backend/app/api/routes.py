"""HTTP route definitions."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.analysis import analyze_github_url, analyze_uploaded_zip
from app.api.deps import get_analysis_store, get_ingestion_service
from app.api.impact import analyze_file_impact
from app.database import get_db
from app.db.context import RepositoryPersistContext
from app.graph.algorithms.impact import FileNotInGraphError
from app.ingestion import (
    CloneError,
    IngestionService,
    InvalidGitHubUrlError,
    RepositoryNotFoundError,
    parse_github_url,
)
from app.pipeline.serialize import build_repository, impact_analysis_to_dict
from app.pipeline.store import AnalysisNotFoundError, AnalysisStore

router = APIRouter()


@router.post("/api/analyze")
async def analyze(
    file: UploadFile | None = File(default=None),
    github_url: str | None = Form(default=None),
    ingestion: IngestionService = Depends(get_ingestion_service),
    store: AnalysisStore = Depends(get_analysis_store),
    db: Session = Depends(get_db),
) -> dict:
    """Analyze a Python repository from a zip upload or a public GitHub URL."""
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
        return await _analyze_zip_upload(file, ingestion, store, db)

    assert github_url is not None
    return _analyze_github_submission(github_url, ingestion, store, db)


@router.get("/api/impact/{repo_id}")
def get_impact(
    repo_id: str,
    file: str,
    store: AnalysisStore = Depends(get_analysis_store),
    db: Session = Depends(get_db),
) -> dict:
    """Return on-demand impact analysis for one file in a previously analyzed repo."""
    if not file.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'file' is required")

    try:
        result = analyze_file_impact(store, repo_id, file, session=db)
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotInGraphError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return impact_analysis_to_dict(result)


async def _analyze_zip_upload(
    file: UploadFile,
    ingestion: IngestionService,
    store: AnalysisStore,
    db: Session,
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")

    try:
        zip_name = Path(file.filename or "upload.zip").stem
        persist_context = RepositoryPersistContext(
            source="zip",
            name=zip_name,
            repo_name=zip_name,
            file_hash=hashlib.sha256(data).hexdigest(),
        )
        job_id, result = analyze_uploaded_zip(
            ingestion,
            data,
            zip_name=zip_name,
            store=store,
            session=db,
            persist_context=persist_context,
        )
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip file") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = result.to_dict(
        repository=build_repository(name=zip_name, source="zip"),
    )
    return {"job_id": job_id, "status": "complete", **payload}


def _analyze_github_submission(
    github_url: str,
    ingestion: IngestionService,
    store: AnalysisStore,
    db: Session,
) -> dict:
    try:
        parsed = parse_github_url(github_url)
        persist_context = RepositoryPersistContext(
            source="github",
            name=parsed.display_name,
            owner=parsed.owner,
            repo_name=parsed.repo,
        )
        job_id, result = analyze_github_url(
            ingestion,
            github_url,
            store=store,
            session=db,
            persist_context=persist_context,
        )
    except InvalidGitHubUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RepositoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CloneError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = result.to_dict(
        repository=build_repository(name=parsed.display_name, source="github"),
    )
    return {"job_id": job_id, "status": "complete", **payload}

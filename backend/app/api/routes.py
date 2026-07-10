"""HTTP route definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.analysis import build_analyze_status
from app.api.analyze_request import run_analyze_request
from app.api.deps import get_analysis_store, get_ingestion_service
from app.database import get_db
from app.ingestion import IngestionService
from app.pipeline.store import AnalysisStore

router = APIRouter()


@router.post("/api/analyze", summary="Quick Analysis", tags=["Analysis"])
async def analyze(
    file: UploadFile | None = File(default=None),
    github_url: str | None = Form(default=None),
    ingestion: IngestionService = Depends(get_ingestion_service),
    store: AnalysisStore = Depends(get_analysis_store),
    db: Session = Depends(get_db),
) -> dict:
    """Quick Analysis — full graph/scores/files JSON in one response.

    Same pipeline as Repository Analysis (``POST /api/repos/analyze``); use this
    for scripts and one-shot dumps. UIs should prefer the slim repo endpoint
    and fetch ``GET /api/repos/{repo_id}/graph|scores|impact`` on demand.
    """
    run, repository = await run_analyze_request(file, github_url, ingestion, store, db)
    payload = run.result.to_dict(repository=repository)
    return {**build_analyze_status(run), **payload}

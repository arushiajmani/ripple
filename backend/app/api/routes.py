"""HTTP route definitions."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.analysis import analyze_uploaded_zip
from app.api.deps import get_ingestion_service
from app.ingestion import IngestionService
from app.pipeline.serialize import build_repository

router = APIRouter()


@router.post("/api/analyze")
async def analyze_zip(
    file: UploadFile,
    ingestion: IngestionService = Depends(get_ingestion_service),
) -> dict:
    """Accept a zip upload, run the analysis pipeline, and return the result JSON."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")

    try:
        job_id, result = analyze_uploaded_zip(ingestion, data)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip file") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    zip_name = Path(file.filename or "upload.zip").stem
    payload = result.to_dict(
        repository=build_repository(name=zip_name, source="zip"),
    )
    return {"job_id": job_id, "status": "complete", **payload}

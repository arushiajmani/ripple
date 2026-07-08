"""FastAPI dependencies for the HTTP layer."""

from __future__ import annotations

from fastapi import Request

from app.ingestion import IngestionService
from app.pipeline.store import AnalysisStore


def get_ingestion_service(request: Request) -> IngestionService:
    """Return an ingestion service, honoring ``app.state.ingestion_base_dir`` in tests."""
    base_dir = getattr(request.app.state, "ingestion_base_dir", None)
    if base_dir is not None:
        return IngestionService(base_dir=base_dir)
    return IngestionService()


def get_analysis_store(request: Request) -> AnalysisStore:
    """Return the process-wide analysis result store."""
    store = getattr(request.app.state, "analysis_store", None)
    if store is None:
        store = AnalysisStore()
        request.app.state.analysis_store = store
    return store

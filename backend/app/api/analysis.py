"""Zip upload → pipeline orchestration for the API layer."""

from __future__ import annotations

from app.ingestion import IngestionService
from app.pipeline import AnalysisPipeline, PipelineResult


def analyze_uploaded_zip(
    service: IngestionService,
    zip_bytes: bytes,
    *,
    job_id: str | None = None,
    pipeline: AnalysisPipeline | None = None,
) -> tuple[str, PipelineResult]:
    """Extract a zip, run the analysis pipeline, and always clean up the job dir."""
    ingestion = service.ingest_zip_bytes(zip_bytes, job_id=job_id)
    runner = pipeline or AnalysisPipeline()
    try:
        if not ingestion.python_files:
            raise ValueError("No Python files found in uploaded archive")
        result = runner.run(ingestion.local_path)
        return ingestion.job_id, result
    finally:
        service.cleanup(ingestion)

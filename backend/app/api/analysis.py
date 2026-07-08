"""Ingestion → pipeline orchestration for the API layer."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.context import RepositoryPersistContext
from app.db.persist import persist_pipeline_result
from app.ingestion import IngestionService
from app.ingestion.models import RepositoryHandle
from app.pipeline import AnalysisPipeline, AnalysisStore, PipelineResult


def analyze_repository(
    service: IngestionService,
    ingestion: RepositoryHandle,
    *,
    pipeline: AnalysisPipeline | None = None,
    store: AnalysisStore | None = None,
    session: Session | None = None,
    persist_context: RepositoryPersistContext | None = None,
    empty_repo_message: str = "No Python files found in repository",
) -> tuple[str, PipelineResult]:
    """Run the analysis pipeline on an ingested directory and always clean up."""
    runner = pipeline or AnalysisPipeline()
    try:
        if not ingestion.python_files:
            raise ValueError(empty_repo_message)
        result = runner.run(ingestion.local_path)
        if store is not None:
            store.save(ingestion.job_id, result)
        if session is not None and persist_context is not None:
            persist_pipeline_result(
                session,
                ingestion.job_id,
                result,
                persist_context,
            )
        return ingestion.job_id, result
    finally:
        service.cleanup(ingestion)


def analyze_uploaded_zip(
    service: IngestionService,
    zip_bytes: bytes,
    *,
    job_id: str | None = None,
    pipeline: AnalysisPipeline | None = None,
    store: AnalysisStore | None = None,
    session: Session | None = None,
    persist_context: RepositoryPersistContext | None = None,
    zip_name: str = "",
) -> tuple[str, PipelineResult]:
    """Extract a zip, run the analysis pipeline, and always clean up the job dir."""
    ingestion = service.ingest_zip_bytes(zip_bytes, job_id=job_id, name=zip_name)
    return analyze_repository(
        service,
        ingestion,
        pipeline=pipeline,
        store=store,
        session=session,
        persist_context=persist_context,
        empty_repo_message="No Python files found in uploaded archive",
    )


def analyze_github_url(
    service: IngestionService,
    github_url: str,
    *,
    job_id: str | None = None,
    pipeline: AnalysisPipeline | None = None,
    store: AnalysisStore | None = None,
    session: Session | None = None,
    persist_context: RepositoryPersistContext | None = None,
) -> tuple[str, PipelineResult]:
    """Clone a GitHub repository, run the pipeline, and always clean up."""
    ingestion = service.ingest_github(github_url, job_id=job_id)
    return analyze_repository(
        service,
        ingestion,
        pipeline=pipeline,
        store=store,
        session=session,
        persist_context=persist_context,
        empty_repo_message="No Python files found in repository",
    )

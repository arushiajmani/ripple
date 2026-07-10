"""Ingestion → pipeline orchestration for the API layer."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.context import PersistResult, RepositoryPersistContext
from app.db.persist import persist_pipeline_result
from app.ingestion import EmptyRepositoryError, IngestionService
from app.ingestion.models import RepositoryHandle
from app.pipeline import AnalysisPipeline, AnalysisStore, PipelineResult


@dataclass(frozen=True)
class AnalyzeRun:
    """Outcome of one analyze request."""

    job_id: str
    result: PipelineResult
    persist: PersistResult | None = None


def build_analyze_status(run: AnalyzeRun) -> dict[str, str]:
    """Top-level analyze ids — ``job_id`` and ``repo_id`` adjacent, then ``status``."""
    ids: dict[str, str] = {"job_id": run.job_id}
    if run.persist is not None:
        ids["repo_id"] = str(run.persist.repository_id)
    ids["status"] = "complete"
    return ids


def analyze_repository(
    service: IngestionService,
    ingestion: RepositoryHandle,
    *,
    pipeline: AnalysisPipeline | None = None,
    store: AnalysisStore | None = None,
    session: Session | None = None,
    persist_context: RepositoryPersistContext | None = None,
    empty_repo_message: str = "No Python files found in repository",
) -> AnalyzeRun:
    """Run the analysis pipeline on an ingested directory and always clean up."""
    runner = pipeline or AnalysisPipeline()
    try:
        if not ingestion.python_files:
            raise EmptyRepositoryError(empty_repo_message)
        result = runner.run(ingestion.local_path)
        persist: PersistResult | None = None
        if session is not None and persist_context is not None:
            persist = persist_pipeline_result(
                session,
                ingestion.job_id,
                result,
                persist_context,
            )
        if store is not None and persist is not None:
            store.save(str(persist.repository_id), result)
        return AnalyzeRun(job_id=ingestion.job_id, result=result, persist=persist)
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
) -> AnalyzeRun:
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
) -> AnalyzeRun:
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

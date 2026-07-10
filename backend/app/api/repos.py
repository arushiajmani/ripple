"""Repo-centric REST routes (Phase 1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.analysis import AnalyzeRun, build_analyze_status
from app.api.analyze_request import run_analyze_request
from app.api.deps import get_analysis_store, get_ingestion_service
from app.api.impact import analyze_file_impact, resolve_pipeline_result
from app.database import get_db
from app.db.models import AnalysisJob, AnalysisStatistics, Repository
from app.db.queries import (
    get_latest_completed_job,
    get_repository,
    list_repositories_with_latest_job,
)
from app.ingestion import IngestionService
from app.pipeline.serialize import (
    build_cycles,
    build_graph,
    build_repository,
    impact_analysis_to_dict,
    node_score_to_dict,
    round_json_float,
    summary_fields,
    to_utc_iso_z,
)
from app.pipeline.store import AnalysisStore

router = APIRouter()


def _format_timestamp(value: datetime | None) -> str | None:
    return None if value is None else to_utc_iso_z(value)


def repository_display_name(repo: Repository) -> str:
    if repo.source == "github" and repo.owner:
        return f"{repo.owner}/{repo.repo_name}"
    return repo.repo_name


def repository_payload(repo: Repository) -> dict[str, str]:
    payload = build_repository(name=repository_display_name(repo), source=repo.source)
    if repo.source == "github":
        if repo.owner is not None:
            payload["owner"] = repo.owner
        payload["repo_name"] = repo.repo_name
    return payload


def summary_from_statistics(stats: AnalysisStatistics) -> dict[str, int]:
    """Same ``summary`` shape as the pipeline path, sourced from persisted stats."""
    return summary_fields(
        file_count=stats.file_count,
        node_count=stats.node_count,
        edge_count=stats.edge_count,
        cycle_count=stats.cycle_count,
    )


def statistics_from_row(stats: AnalysisStatistics) -> dict[str, int | float | None]:
    # Distinct from serialize.build_statistics: the DB row carries graph_density
    # (computed at persist time) but not internal_dependency_count.
    density = stats.graph_density
    if density is not None:
        density = round_json_float(density)
    return {
        "class_count": stats.class_count,
        "function_count": stats.function_count,
        "external_dependency_count": stats.external_dependency_count,
        "graph_density": density,
    }


def slim_analyze_response(run: AnalyzeRun, *, repository: dict[str, str]) -> dict:
    if run.persist is None:
        raise HTTPException(status_code=500, detail="Analysis was not persisted")

    return {
        **build_analyze_status(run),
        "repository": repository,
    }


def repo_list_item(repo: Repository, job: AnalysisJob, stats: AnalysisStatistics) -> dict:
    return {
        "repo_id": str(repo.id),
        "name": repository_display_name(repo),
        "source": repo.source,
        "status": job.status,
        "summary": summary_from_statistics(stats),
        "created_at": _format_timestamp(repo.created_at),
        "analyzed_at": _format_timestamp(job.completed_at),
    }


def repo_detail_response(repo: Repository, job: AnalysisJob, stats: AnalysisStatistics) -> dict:
    return {
        "repo_id": str(repo.id),
        "repository": repository_payload(repo),
        "summary": summary_from_statistics(stats),
        "statistics": statistics_from_row(stats),
        "job_id": str(job.id),
    }


@router.post("/api/repos/analyze")
async def analyze_repo(
    file: UploadFile | None = File(default=None),
    github_url: str | None = Form(default=None),
    ingestion: IngestionService = Depends(get_ingestion_service),
    store: AnalysisStore = Depends(get_analysis_store),
    db: Session = Depends(get_db),
) -> dict:
    """Repository Analysis — slim response with repo_id for follow-up GETs.

    Same pipeline as Quick Analysis (``POST /api/analyze``). Returns only
    ``repo_id``, ``job_id``, ``status``, and ``repository``; load graph, scores,
    and impact via ``GET /api/repos/{repo_id}/…``.
    """
    run, repository = await run_analyze_request(file, github_url, ingestion, store, db)
    return slim_analyze_response(run, repository=repository)


@router.get("/api/repos")
def get_repos(db: Session = Depends(get_db)) -> list[dict]:
    """List analyzed repositories using each repo's latest completed job."""
    items: list[dict] = []
    for repo, job in list_repositories_with_latest_job(db):
        if job.statistics is None:
            continue
        items.append(repo_list_item(repo, job, job.statistics))
    return items


@router.get("/api/repos/{repo_id}")
def get_repo(repo_id: str, db: Session = Depends(get_db)) -> dict:
    """Return summary and statistics for a repository's latest completed analysis."""
    try:
        repo_uuid = uuid.UUID(repo_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Repository not found") from exc

    repo = get_repository(db, repo_uuid)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    job = get_latest_completed_job(db, repo_uuid)
    if job is None or job.statistics is None:
        raise HTTPException(
            status_code=404,
            detail="No completed analysis for repository",
        )

    return repo_detail_response(repo, job, job.statistics)


@router.get("/api/repos/{repo_id}/graph")
def get_repo_graph(
    repo_id: str,
    store: AnalysisStore = Depends(get_analysis_store),
    db: Session = Depends(get_db),
) -> dict:
    """Return the import graph (nodes, edges, cycles) for the latest completed job."""
    result = resolve_pipeline_result(store, repo_id, session=db)
    graph = build_graph(result.graph)
    return {
        "repo_id": repo_id,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "cycles": build_cycles(result.cycles),
    }


@router.get("/api/repos/{repo_id}/scores")
def get_repo_scores(
    repo_id: str,
    store: AnalysisStore = Depends(get_analysis_store),
    db: Session = Depends(get_db),
) -> dict:
    """Return the criticality-ranked score list for the latest completed job."""
    result = resolve_pipeline_result(store, repo_id, session=db)
    return {
        "repo_id": repo_id,
        "scores": [node_score_to_dict(score) for score in result.scores.scores],
    }


@router.get("/api/repos/{repo_id}/impact")
def get_repo_impact(
    repo_id: str,
    file: str,
    store: AnalysisStore = Depends(get_analysis_store),
    db: Session = Depends(get_db),
) -> dict:
    """Return on-demand impact analysis for one file in a repository's latest job.

    ``repo_id`` must be ``repositories.id``. Canonical replacement for the legacy
    ``GET /api/impact/{repo_id}`` route.
    """
    if not file.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'file' is required")

    result = analyze_file_impact(store, repo_id, file, session=db)
    return impact_analysis_to_dict(result)

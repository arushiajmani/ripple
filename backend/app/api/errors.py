"""Centralized HTTP error mapping for domain exceptions.

Instead of repeating ``try/except`` → ``HTTPException`` blocks in every endpoint,
domain exceptions propagate out of the handlers and are translated here. Starlette
resolves the most specific handler via the exception's MRO, so registering the
``IngestionError`` base plus the few subclasses that need a different status code
is enough.
"""

from __future__ import annotations

import zipfile

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.graph.algorithms.impact import FileNotInGraphError
from app.ingestion import CloneError, IngestionError, RepositoryNotFoundError
from app.pipeline.store import AnalysisNotFoundError


def _error(status_code: int, detail: str) -> JSONResponse:
    """Match FastAPI's default ``{"detail": ...}`` error body."""
    return JSONResponse(status_code=status_code, content={"detail": detail})


def register_exception_handlers(app: FastAPI) -> None:
    """Attach domain-exception → HTTP-status handlers to ``app``."""

    @app.exception_handler(IngestionError)
    async def _ingestion_error(request: Request, exc: IngestionError) -> JSONResponse:
        # Base case: invalid input, empty repo, unsafe archive, etc.
        return _error(400, str(exc))

    @app.exception_handler(RepositoryNotFoundError)
    async def _repo_not_found(
        request: Request, exc: RepositoryNotFoundError
    ) -> JSONResponse:
        return _error(404, str(exc))

    @app.exception_handler(CloneError)
    async def _clone_error(request: Request, exc: CloneError) -> JSONResponse:
        return _error(502, str(exc))

    @app.exception_handler(zipfile.BadZipFile)
    async def _bad_zip(request: Request, exc: zipfile.BadZipFile) -> JSONResponse:
        return _error(400, "Invalid zip file")

    @app.exception_handler(AnalysisNotFoundError)
    async def _analysis_not_found(
        request: Request, exc: AnalysisNotFoundError
    ) -> JSONResponse:
        return _error(404, str(exc))

    @app.exception_handler(FileNotInGraphError)
    async def _file_not_in_graph(
        request: Request, exc: FileNotInGraphError
    ) -> JSONResponse:
        return _error(404, str(exc))

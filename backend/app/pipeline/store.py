"""In-memory store for completed analysis results (on-demand queries).

Caches ``PipelineResult`` by ``repositories.id`` and/or ``analysis_jobs.id`` so
impact and future graph endpoints can reuse graph + scores without re-parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.pipeline import PipelineResult


class AnalysisNotFoundError(LookupError):
    """Raised when no completed analysis exists for the given identifier."""


@dataclass
class AnalysisStore:
    """Thread-unsafe in-memory cache of ``PipelineResult`` by id."""

    _results: dict[str, PipelineResult] = field(default_factory=dict)

    def save(self, key: str, result: PipelineResult) -> None:
        self._results[key] = result

    def get(self, key: str) -> PipelineResult | None:
        return self._results.get(key)

"""In-memory store for completed analysis results (on-demand queries).

Persists ``PipelineResult`` artifacts keyed by ``job_id`` / ``repo_id`` so
impact and future graph endpoints can reuse graph + scores without re-parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.pipeline import PipelineResult


class AnalysisNotFoundError(LookupError):
    """Raised when no completed analysis exists for the given repo id."""


@dataclass
class AnalysisStore:
    """Thread-unsafe in-memory cache of ``PipelineResult`` by repository id."""

    _results: dict[str, PipelineResult] = field(default_factory=dict)

    def save(self, repo_id: str, result: PipelineResult) -> None:
        self._results[repo_id] = result

    def get(self, repo_id: str) -> PipelineResult | None:
        return self._results.get(repo_id)

    def require(self, repo_id: str) -> PipelineResult:
        result = self.get(repo_id)
        if result is None:
            raise AnalysisNotFoundError(
                f"Repository analysis not found: {repo_id}"
            )
        return result

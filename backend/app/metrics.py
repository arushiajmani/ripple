"""Per-stage pipeline timing metrics (benchmark CLI + future status API)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class StageMetric:
    """One timed pipeline stage."""

    stage_name: str
    duration_ms: float
    files_processed: int | None = None

    def to_dict(self) -> dict[str, float | str | int | None]:
        return {
            "stage_name": self.stage_name,
            "duration_ms": round(self.duration_ms, 2),
            "files_processed": self.files_processed,
        }


class StageTimer:
    """Context manager that records elapsed wall time in milliseconds."""

    def __init__(self) -> None:
        self.duration_ms = 0.0
        self._start: float | None = None

    def __enter__(self) -> StageTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        if self._start is not None:
            self.duration_ms = (time.perf_counter() - self._start) * 1000.0


STAGE_ORDER = (
    "file_discovery",
    "ast_parsing",
    "import_resolution",
    "graph_construction",
    "pagerank_computation",
    "betweenness_computation",
    "score_normalization",
)


def format_metrics_table(metrics: list[StageMetric]) -> str:
    """Human-readable table for stdout (benchmark CLI)."""
    if not metrics:
        return "  (no metrics)"

    by_name = {m.stage_name: m for m in metrics}
    ordered = [by_name[name] for name in STAGE_ORDER if name in by_name]

    name_width = max(len(m.stage_name) for m in ordered)
    lines = [
        f"  {'stage':<{name_width}}  {'ms':>10}  {'files':>8}  {'%':>6}",
        f"  {'─' * name_width}  {'─' * 10}  {'─' * 8}  {'─' * 6}",
    ]

    total_ms = sum(m.duration_ms for m in ordered)
    for metric in ordered:
        files = "" if metric.files_processed is None else str(metric.files_processed)
        pct = (metric.duration_ms / total_ms * 100.0) if total_ms else 0.0
        lines.append(
            f"  {metric.stage_name:<{name_width}}  "
            f"{metric.duration_ms:>10.2f}  {files:>8}  {pct:>5.1f}%"
        )

    lines.append(f"  {'─' * name_width}  {'─' * 10}  {'─' * 8}  {'─' * 6}")
    lines.append(
        f"  {'total':<{name_width}}  {total_ms:>10.2f}  {'':>8}  {'100.0%':>6}"
    )
    return "\n".join(lines)


def metrics_iterator(metrics: list[StageMetric]) -> Iterator[StageMetric]:
    """Yield metrics in canonical stage order."""
    by_name = {m.stage_name: m for m in metrics}
    for name in STAGE_ORDER:
        if name in by_name:
            yield by_name[name]

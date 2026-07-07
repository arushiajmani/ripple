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

    def to_dict(self) -> dict[str, float | str | int]:
        payload: dict[str, float | str | int | None] = {
            "stage_name": self.stage_name,
            "duration_ms": round(self.duration_ms, 2),
            "files_processed": self.files_processed,
        }
        return {key: value for key, value in payload.items() if value is not None}


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

# Human-readable labels and pipeline groups for benchmark stdout.
STAGE_LABELS: dict[str, str] = {
    "file_discovery": "File discovery",
    "ast_parsing": "AST parsing",
    "import_resolution": "Import resolution",
    "graph_construction": "Graph construction",
    "pagerank_computation": "PageRank",
    "betweenness_computation": "Betweenness",
    "score_normalization": "Score normalization",
}

BENCHMARK_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Repository", ("file_discovery",)),
    ("Parsing", ("ast_parsing", "import_resolution")),
    ("Graph", ("graph_construction",)),
    (
        "Algorithms",
        (
            "pagerank_computation",
            "betweenness_computation",
            "score_normalization",
        ),
    ),
)

_UNKNOWN_GROUP = "Other"


class DuplicateStageMetricError(ValueError):
    """Raised when two StageMetric entries share the same stage_name."""


def _index_metrics(metrics: list[StageMetric]) -> dict[str, StageMetric]:
    """Index metrics by stage_name; reject duplicates."""
    by_name: dict[str, StageMetric] = {}
    for metric in metrics:
        if metric.stage_name in by_name:
            raise DuplicateStageMetricError(
                f"duplicate stage metric: {metric.stage_name!r}"
            )
        by_name[metric.stage_name] = metric
    return by_name


def _ordered_metrics_from_index(by_name: dict[str, StageMetric]) -> list[StageMetric]:
    """Canonical order: known stages first, then unknown stages (sorted)."""
    known = [by_name[name] for name in STAGE_ORDER if name in by_name]
    unknown = [
        by_name[name]
        for name in sorted(by_name)
        if name not in STAGE_ORDER
    ]
    return [*known, *unknown]


def _ordered_metrics(metrics: list[StageMetric]) -> list[StageMetric]:
    return _ordered_metrics_from_index(_index_metrics(metrics))


def _stage_label(stage_name: str) -> str:
    return STAGE_LABELS.get(stage_name, stage_name)


def format_metrics_table(metrics: list[StageMetric]) -> str:
    """Human-readable grouped table for stdout (benchmark CLI)."""
    if not metrics:
        return "  (no metrics)"

    by_name = _index_metrics(metrics)
    ordered = _ordered_metrics_from_index(by_name)
    total_ms = sum(m.duration_ms for m in ordered)

    label_width = max(len(_stage_label(m.stage_name)) for m in ordered)
    lines = [
        f"  {'stage':<{label_width}}  {'ms':>10}  {'files':>8}  {'%':>6}",
        f"  {'─' * label_width}  {'─' * 10}  {'─' * 8}  {'─' * 6}",
    ]

    first_group = True
    for group_title, stage_names in BENCHMARK_GROUPS:
        group_metrics = [by_name[name] for name in stage_names if name in by_name]
        if not group_metrics:
            continue
        if not first_group:
            lines.append("")
        first_group = False
        lines.extend(_format_group_lines(group_title, group_metrics, label_width, total_ms))

    unknown_metrics = [
        by_name[name]
        for name in sorted(by_name)
        if name not in STAGE_ORDER
    ]
    if unknown_metrics:
        if not first_group:
            lines.append("")
        lines.extend(
            _format_group_lines(_UNKNOWN_GROUP, unknown_metrics, label_width, total_ms)
        )

    lines.append(f"  {'─' * label_width}  {'─' * 10}  {'─' * 8}  {'─' * 6}")
    lines.append(
        f"  {'total':<{label_width}}  {total_ms:>10.2f}  {'':>8}  {'100.0%':>6}"
    )
    return "\n".join(lines)


def _format_group_lines(
    group_title: str,
    group_metrics: list[StageMetric],
    label_width: int,
    total_ms: float,
) -> list[str]:
    lines = [f"  {group_title}", f"  {'-' * len(group_title)}"]
    for metric in group_metrics:
        label = _stage_label(metric.stage_name)
        files = "" if metric.files_processed is None else str(metric.files_processed)
        pct = (metric.duration_ms / total_ms * 100.0) if total_ms else 0.0
        lines.append(
            f"  {label:<{label_width}}  "
            f"{metric.duration_ms:>10.2f}  {files:>8}  {pct:>5.1f}%"
        )
    return lines


def metrics_iterator(metrics: list[StageMetric]) -> Iterator[StageMetric]:
    """Yield metrics in canonical stage order."""
    yield from _ordered_metrics(metrics)

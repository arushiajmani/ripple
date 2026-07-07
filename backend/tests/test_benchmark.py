"""Benchmark CLI and pipeline stage metrics tests.

Run from backend/:
    PYTHONPATH=. pytest tests/test_benchmark.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.metrics import (
    STAGE_LABELS,
    STAGE_ORDER,
    DuplicateStageMetricError,
    StageMetric,
    format_metrics_table,
    metrics_iterator,
)
from app.pipeline import AnalysisPipeline

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


@pytest.fixture
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline()


def _stage_percentages(table: str) -> list[float]:
    """Extract per-stage % values from a formatted table (excludes total row)."""
    pcts: list[float] = []
    for line in table.splitlines():
        if "total" in line.lower():
            continue
        match = re.search(r"(\d+\.\d+)%\s*$", line)
        if match:
            pcts.append(float(match.group(1)))
    return pcts


def test_pipeline_result_includes_all_stage_metrics(
    pipeline: AnalysisPipeline,
) -> None:
    result = pipeline.run(FIXTURE_ROOT)

    stage_names = [m.stage_name for m in result.metrics]
    assert stage_names == list(STAGE_ORDER)
    assert len(stage_names) == len(set(stage_names))


def test_metrics_have_expected_files_processed(
    pipeline: AnalysisPipeline,
) -> None:
    result = pipeline.run(FIXTURE_ROOT)
    file_count = len(result.analyses)

    by_name = {m.stage_name: m for m in result.metrics}
    assert by_name["file_discovery"].files_processed is None
    assert by_name["ast_parsing"].files_processed == file_count
    assert by_name["import_resolution"].files_processed == file_count
    assert by_name["graph_construction"].files_processed == file_count
    assert by_name["pagerank_computation"].files_processed is None


def test_metrics_durations_are_non_negative(pipeline: AnalysisPipeline) -> None:
    result = pipeline.run(FIXTURE_ROOT)

    for metric in result.metrics:
        assert metric.duration_ms >= 0.0


def test_stage_metric_to_dict() -> None:
    metric = StageMetric("ast_parsing", 12.3456, files_processed=4)
    assert metric.to_dict() == {
        "stage_name": "ast_parsing",
        "duration_ms": 12.35,
        "files_processed": 4,
    }

    assert StageMetric("pagerank_computation", 1.0).to_dict() == {
        "stage_name": "pagerank_computation",
        "duration_ms": 1.0,
    }


def test_format_metrics_table_empty() -> None:
    assert format_metrics_table([]) == "  (no metrics)"


def test_format_metrics_table_single_metric() -> None:
    table = format_metrics_table([StageMetric("ast_parsing", 42.0, files_processed=3)])

    assert "AST parsing" in table
    assert "42.00" in table
    assert "100.0%" in table
    assert "total" in table


def test_format_metrics_table_includes_stages(pipeline: AnalysisPipeline) -> None:
    result = pipeline.run(FIXTURE_ROOT)
    table = format_metrics_table(result.metrics)

    for name in STAGE_ORDER:
        assert STAGE_LABELS[name] in table
    for group_title in ("Repository", "Parsing", "Graph", "Algorithms"):
        assert group_title in table
    assert "total" in table


def test_format_metrics_table_groups_stages_in_pipeline_order() -> None:
    metrics = [
        StageMetric("file_discovery", 1.0),
        StageMetric("ast_parsing", 2.0, files_processed=3),
        StageMetric("import_resolution", 3.0, files_processed=3),
        StageMetric("graph_construction", 4.0, files_processed=3),
        StageMetric("pagerank_computation", 5.0),
        StageMetric("betweenness_computation", 6.0),
        StageMetric("score_normalization", 7.0),
    ]
    table = format_metrics_table(metrics)

    repo_pos = table.index("Repository")
    parsing_pos = table.index("Parsing")
    graph_pos = table.index("Graph")
    algorithms_pos = table.index("Algorithms")
    assert repo_pos < parsing_pos < graph_pos < algorithms_pos


def test_format_metrics_table_percentages_sum_to_100() -> None:
    metrics = [
        StageMetric("file_discovery", 10.0),
        StageMetric("ast_parsing", 20.0),
        StageMetric("import_resolution", 30.0),
        StageMetric("graph_construction", 40.0),
        StageMetric("pagerank_computation", 50.0),
        StageMetric("betweenness_computation", 60.0),
        StageMetric("score_normalization", 70.0),
    ]
    table = format_metrics_table(metrics)
    pcts = _stage_percentages(table)

    assert len(pcts) == len(metrics)
    assert sum(pcts) == pytest.approx(100.0, abs=0.2)


def test_format_metrics_table_unknown_stage_uses_raw_name() -> None:
    table = format_metrics_table(
        [
            StageMetric("custom_stage", 5.0),
            StageMetric("ast_parsing", 10.0),
        ]
    )

    assert "custom_stage" in table
    assert "Other" in table
    assert "AST parsing" in table


def test_format_metrics_table_rejects_duplicate_stage_names() -> None:
    metrics = [
        StageMetric("ast_parsing", 1.0),
        StageMetric("ast_parsing", 2.0),
    ]

    with pytest.raises(DuplicateStageMetricError, match="ast_parsing"):
        format_metrics_table(metrics)


def test_metrics_iterator_rejects_duplicate_stage_names() -> None:
    metrics = [
        StageMetric("ast_parsing", 1.0),
        StageMetric("ast_parsing", 2.0),
    ]

    with pytest.raises(DuplicateStageMetricError, match="ast_parsing"):
        list(metrics_iterator(metrics))


def test_metrics_iterator_yields_canonical_order_from_shuffled_input() -> None:
    shuffled = [
        StageMetric("score_normalization", 7.0),
        StageMetric("file_discovery", 1.0),
        StageMetric("betweenness_computation", 6.0),
        StageMetric("import_resolution", 3.0),
        StageMetric("pagerank_computation", 5.0),
        StageMetric("ast_parsing", 2.0),
        StageMetric("graph_construction", 4.0),
    ]

    names = [m.stage_name for m in metrics_iterator(shuffled)]

    assert names == list(STAGE_ORDER)


def test_metrics_iterator_appends_unknown_stages_after_known() -> None:
    metrics = [
        StageMetric("custom_stage", 5.0),
        StageMetric("ast_parsing", 10.0),
    ]

    names = [m.stage_name for m in metrics_iterator(metrics)]

    assert names == ["ast_parsing", "custom_stage"]


def test_benchmark_performance_notes_constant() -> None:
    from app.benchmark.__main__ import PERFORMANCE_NOTES

    assert "steady-state" in PERFORMANCE_NOTES
    assert "warm-up" in PERFORMANCE_NOTES.lower()


def test_empty_repo_has_parse_and_graph_metrics(
    pipeline: AnalysisPipeline, tmp_path: Path
) -> None:
    result = pipeline.run(tmp_path)

    assert result.analyses == {}
    by_name = {m.stage_name: m for m in result.metrics}
    assert list(by_name)[:4] == [
        "file_discovery",
        "ast_parsing",
        "import_resolution",
        "graph_construction",
    ]
    assert by_name["ast_parsing"].duration_ms == 0.0

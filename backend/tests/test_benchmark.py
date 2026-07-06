"""Benchmark CLI and pipeline stage metrics tests.

Run from backend/:
    PYTHONPATH=. pytest tests/test_benchmark.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.metrics import STAGE_ORDER, StageMetric, format_metrics_table
from app.pipeline import AnalysisPipeline

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


@pytest.fixture
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline()


def test_pipeline_result_includes_all_stage_metrics(
    pipeline: AnalysisPipeline,
) -> None:
    result = pipeline.run(FIXTURE_ROOT)

    stage_names = [m.stage_name for m in result.metrics]
    assert stage_names == list(STAGE_ORDER)


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


def test_format_metrics_table_includes_stages(pipeline: AnalysisPipeline) -> None:
    result = pipeline.run(FIXTURE_ROOT)
    table = format_metrics_table(result.metrics)

    for name in STAGE_ORDER:
        assert name in table
    assert "total" in table


def test_empty_repo_has_parse_and_graph_metrics(
    pipeline: AnalysisPipeline, tmp_path: Path
) -> None:
    result = pipeline.run(tmp_path)

    assert result.analyses == {}
    stage_names = [m.stage_name for m in result.metrics]
    assert stage_names[:4] == [
        "file_discovery",
        "ast_parsing",
        "import_resolution",
        "graph_construction",
    ]
    assert result.metrics[1].duration_ms == 0.0

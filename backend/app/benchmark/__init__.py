"""Benchmark CLI: python -m app.benchmark --repo path/to/project"""

from app.metrics import StageMetric, format_metrics_table

__all__ = ["StageMetric", "format_metrics_table"]

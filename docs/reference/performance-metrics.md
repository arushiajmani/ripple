# Performance Metrics

> Recorded on `PipelineResult.metrics`. Benchmark CLI: [backend/pipeline.md](../backend/pipeline.md#benchmark-cli).

## Instrumented stages

| Stage | What it measures |
|-------|------------------|
| `file_discovery` | `collect_python_files` directory walk |
| `ast_parsing` | Read + `ast.parse` + walk per file |
| `import_resolution` | `classify_dependencies` per file |
| `graph_construction` | `GraphBuilder` + `GraphAdapter` + `CycleDetector` |
| `pagerank_computation` | `nx.pagerank` (timed) |
| `betweenness_computation` | `nx.betweenness_centrality` |
| `score_normalization` | Min-max normalize + `NodeScore` assembly |

**Not timed in pipeline batch:** `impact_analysis` (on-demand via API only).

## StageMetric shape

```python
@dataclass
class StageMetric:
    stage_name: str
    duration_ms: int
    files_processed: int | None = None
```

Duplicate `stage_name` values in one run raise `DuplicateStageMetricError`.

## Benchmark CLI

```bash
cd backend && source .venv/bin/activate
python -m app.benchmark --repo tests/fixtures/mini_repo
```

Output groups stages: **Repository → Parsing → Graph → Algorithms**. Percentages sum to 100% across included stages.

## Steady-state PageRank

The benchmark CLI runs one **untimed** PageRank before the timed `pagerank_computation` stage to exclude one-time NetworkX/SciPy backend initialization. This warm-up is benchmark-only (`AlgorithmEngine(warmup_pagerank=True)`); production analysis computes PageRank a single time. The CLI prints a performance note at the end of the report.

Tests: `test_pagerank_warmup_excludes_cold_start_from_metrics` in `test_scoring.py`.

## Planned API exposure

`GET /api/status/{repo_id}` will return the same `metrics[]` array when `status=complete`. Shape matches `StageMetric.to_dict()`.

## Profiling large repos

Watch for `ast_parsing` dominating wall time on 1000+ file codebases before optimizing graph algorithms. Use benchmark on real targets: [examples/click.md](../examples/click.md), [examples/django.md](../examples/django.md).

## Future status API example

```json
{
  "metrics": [
    { "stage_name": "file_discovery", "duration_ms": 45, "files_processed": null },
    { "stage_name": "ast_parsing", "duration_ms": 8400, "files_processed": 247 },
    { "stage_name": "import_resolution", "duration_ms": 2100, "files_processed": 247 },
    { "stage_name": "graph_construction", "duration_ms": 120, "files_processed": 247 },
    { "stage_name": "pagerank_computation", "duration_ms": 890, "files_processed": null },
    { "stage_name": "betweenness_computation", "duration_ms": 3200, "files_processed": null },
    { "stage_name": "score_normalization", "duration_ms": 15, "files_processed": null }
  ]
}
```

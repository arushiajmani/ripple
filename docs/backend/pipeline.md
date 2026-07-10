# Pipeline

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Backend |
| **Last Updated** | 2026-07-08 |

**Related components:** [Parser](parser.md) · [Graph builder](graph-builder.md) · [Ingestion](ingestion.md) · [API](api.md)

**Tests:** `tests/test_pipeline.py` (9) · `tests/test_serialize.py` (18) · `tests/test_benchmark.py` (16)

**Source files:** `app/pipeline/pipeline.py` · `app/pipeline/serialize.py` · `app/pipeline/store.py` · `app/pipeline/__main__.py` · `app/benchmark/__main__.py` · `app/metrics.py`

---

## Overview

`AnalysisPipeline` orchestrates parse → graph → adapter → cycles → scores and returns `PipelineResult`.

```python
from app.pipeline import AnalysisPipeline

result = AnalysisPipeline().run("tests/fixtures/mini_repo")
result.analyses   # dict[str, FileAnalysis]
result.graph      # GraphResult
result.cycles     # CircularDependencyResult
result.scores     # ScoringResult
result.metrics    # list[StageMetric]
result.scores.top(10)
result.write_json("result.json")
```

## Flow

```text
parse_repository(repo_path)
    → GraphBuilder().build(analyses)
    → GraphAdapter().to_digraph(graph)
    → CycleDetector().detect(digraph)
    → AlgorithmEngine().run_with_metrics(digraph)
    → PipelineResult
```

`ImpactAnalyzer` is **not** in this chain — see [graph-builder.md](graph-builder.md#impact-analysis).

## CLI

```bash
cd backend && source .venv/bin/activate

python -m app.pipeline tests/fixtures/mini_repo
# Summary | Dependency edges | Circular dependencies | Top critical files

python -m app.pipeline tests/fixtures/mini_repo --json result.json
python -m app.pipeline tests/fixtures/mini_repo --json result.json --no-files
```

## JSON export

Serialization lives in `app/pipeline/serialize.py` only.

```python
result.write_json("result.json")
# or: result.to_dict(include_files=False)
```

Document shape: [reference/json-format.md](../reference/json-format.md).

Top N in JSON: `analysis.scores.slice(0, N)` — no separate `top_critical` field.

## AnalysisStore

In-memory cache: `AnalysisStore.save(repo_id, result)` after analyze. Used by repo sub-routes (`/graph`, `/scores`, `/impact`) until/unless loaded from PostgreSQL. Server restart clears memory; DB rows survive when persistence is enabled.

## Benchmark CLI

Profile per-stage timings locally (no HTTP server):

```bash
python -m app.benchmark --repo tests/fixtures/mini_repo
```

Stages: `file_discovery`, `ast_parsing`, `import_resolution`, `graph_construction`, `pagerank_computation`, `betweenness_computation`, `score_normalization`.

Detail: [reference/performance-metrics.md](../reference/performance-metrics.md).

```python
for m in result.metrics:
    print(m.stage_name, m.duration_ms, m.files_processed)
```

## Further reading

- [CLI reference — Pipeline & Benchmark](../development/cli-reference.md)
- [examples/mini_repo.md](../examples/mini_repo.md)

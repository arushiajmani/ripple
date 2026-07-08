# Graph Builder

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Backend |
| **Last Updated** | 2026-07-08 |

**Related components:** [Parser](parser.md) · [Pipeline](pipeline.md) · [API](api.md) (impact)

**Tests:** `tests/test_graph.py` (9) · `tests/test_adapter.py` (4) · `tests/algorithms/test_cycles.py` (8) · `tests/algorithms/test_scoring.py` (13) · `tests/algorithms/test_impact.py` (8)

**Source files:** `app/graph/builder.py` · `app/graph/adapter.py` · `app/graph/models.py` · `app/graph/algorithms/cycles.py` · `app/graph/algorithms/scoring.py` · `app/graph/algorithms/impact.py`

---

## Overview

Turns `dict[str, FileAnalysis]` into a file-level import graph, then runs graph algorithms on a shared `networkx.DiGraph`.

```text
GraphBuilder → GraphResult (nodes + edges)
GraphAdapter → nx.DiGraph (once per pipeline run)
CycleDetector / AlgorithmEngine / ImpactAnalyzer → operate on DiGraph only
```

## GraphBuilder

```python
from app.graph import GraphBuilder
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
result = GraphBuilder().build(analyses)
# result.nodes, result.edges — (importer, imported) pairs
```

| Input | Notes |
|-------|-------|
| `analyses` | Keys are repo-relative paths — same as `parse_repository()` |

Only reads `resolved_deps`. External packages are not nodes. Duplicate deps deduplicated; output sorted for stable tests.

### Edge direction

Edges are **importer → imported** (`auth.py → models.py` means auth imports models).

| Question | NetworkX |
|----------|----------|
| What does this file import? | `successors`, `descendants` |
| What depends on this file? | `predecessors`, `ancestors` |

PageRank flows forward along imports. Impact analysis walks **backward** (dependents = importers).

## GraphAdapter

Single conversion point: `GraphResult` → `nx.DiGraph`. All algorithms share the same graph per pipeline run.

## Cycle detection

`CycleDetector` uses `nx.simple_cycles`, then `normalize_cycle` (lex-smallest start node) to dedupe rotations.

```python
from app.graph import CycleDetector, GraphAdapter, GraphBuilder

digraph = GraphAdapter().to_digraph(GraphBuilder().build(analyses))
result = CycleDetector().detect(digraph)
# result.cycles, result.has_cycles, result.cycle_count
```

Self-loops count as one-node cycles.

## Criticality scoring

`AlgorithmEngine` computes PageRank (`alpha=0.85`), betweenness centrality, in/out degree, and:

```text
criticality = 0.6 * normalize(pagerank) + 0.4 * normalize(betweenness)
```

Min-max normalization is per-repo. One **untimed** PageRank warm-up runs before the timed stage (benchmark steady-state). See [performance metrics](../reference/performance-metrics.md).

| Property | Meaning |
|----------|---------|
| `pagerank` | Importance as a dependency (sums ~1.0) |
| `betweenness` | Bridge / bottleneck on shortest paths |
| `criticality` | Combined change-risk rank |
| `in_degree` | Direct importers in-repo |
| `out_degree` | Direct imports in-repo |

Glossary: [reference/glossary.md](../reference/glossary.md).

## Impact analysis

`ImpactAnalyzer` answers "what breaks if I change file F?" — **on demand**, not a pipeline batch stage.

```python
from app.graph import ImpactAnalyzer

impact = ImpactAnalyzer().analyze(digraph, "myapp/models.py", scores=scores)
# direct_dependents, indirect_dependents, layers, summary
```

- **Direct dependents** — `digraph.predecessors(target)`
- **Indirect** — `ancestors` minus direct
- **Layers** — hop distance on reversed graph
- **Target score** — looked up from `ScoringResult`, not recomputed

Wired via `AnalysisStore` + `GET /api/impact/{repo_id}?file=...`. API detail: [api.md](api.md).

## Try it yourself

```bash
cd backend && source .venv/bin/activate
pytest tests/test_graph.py tests/test_adapter.py tests/algorithms/ -v
python -m app.pipeline tests/fixtures/mini_repo
```

Example graph output: [examples/mini_repo.md](../examples/mini_repo.md#graph-output).

## Further reading

- [JSON format — graph and analysis sections](../reference/json-format.md)
- [CLI reference](../development/cli-reference.md)

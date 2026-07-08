# JSON Format

> Produced by `PipelineResult.write_json()` and `POST /api/analyze`. Implementation: `app/pipeline/serialize.py`.

## Top-level shape

```json
{
  "metadata": { "generated_at": "2026-07-04T12:00:00Z" },
  "repository": { "name": "mini_repo", "source": "zip" },
  "summary": {
    "file_count": 4,
    "node_count": 4,
    "edge_count": 4,
    "cycle_count": 1
  },
  "statistics": {
    "class_count": 2,
    "function_count": 3,
    "internal_dependency_count": 6,
    "external_dependency_count": 4
  },
  "graph": {
    "nodes": ["myapp/models.py", "myapp/auth.py"],
    "edges": [
      { "source": "myapp/auth.py", "target": "myapp/models.py", "type": "imports" }
    ]
  },
  "analysis": {
    "cycles": {
      "has_cycles": true,
      "cycle_count": 1,
      "cycles": [
        {
          "nodes": ["myapp/models.py", "myapp/utils.py"],
          "length": 2,
          "edges": [
            { "source": "myapp/models.py", "target": "myapp/utils.py", "type": "imports" },
            { "source": "myapp/utils.py", "target": "myapp/models.py", "type": "imports" }
          ]
        }
      ]
    },
    "scores": [
      {
        "file_path": "myapp/models.py",
        "pagerank": 0.452,
        "betweenness": 0.0,
        "criticality": 0.6,
        "in_degree": 2,
        "out_degree": 1
      }
    ]
  },
  "files": {
    "myapp/auth.py": {
      "imports": [],
      "resolved_deps": ["myapp/models.py"],
      "external_deps": ["os"],
      "classes": [],
      "functions": [],
      "methods": [],
      "line_count": 15,
      "has_syntax_error": false
    }
  }
}
```

## Section purposes

| Section | Scope |
|---------|--------|
| `metadata` | `generated_at` (UTC ISO-8601) |
| `repository` | `name`, `source` (`zip`, `local`, `github`, …) |
| `summary` | Graph counts (files, nodes, edges, cycles) |
| `statistics` | Parser aggregates (classes, functions, dep totals) |
| `graph` | Structural file import graph |
| `analysis` | Algorithm outputs (cycles, scores; extensible) |
| `files` | Optional full `FileAnalysis` per path (`--no-files` omits) |

## summary vs statistics vs files

| Field | Meaning |
|-------|---------|
| `summary.edge_count` | Unique edges after `GraphBuilder` dedup |
| `statistics.internal_dependency_count` | `sum(len(resolved_deps))` across all files |
| `files[path].resolved_deps` | Per-file in-repo imports |

`internal_dependency_count` may exceed `summary.edge_count` when the parser recorded duplicate deps before graph dedup.

## Scores

Ordered list — `scores[0]` is most critical. No separate `top_critical` field:

```javascript
const top = data.analysis.scores.slice(0, 10);
```

Python: `result.scores.top(10)`.

## Nodes and edges (V1)

- **Nodes** — path strings, not `{ id, type }` objects
- **Edges** — `{ source, target, type }` where `source` is importer
- **`type: "imports"`** today; `"inherits"` / `"calls"` deferred until class/call resolvers exist (V2)

## CLI

```bash
python -m app.pipeline tests/fixtures/mini_repo --json result.json
python -m app.pipeline tests/fixtures/mini_repo --json result.json --no-files
```

Tests: `tests/test_serialize.py` (18).

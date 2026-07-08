# API Schema

> Shipped endpoints only. Planned shapes noted inline. HTTP usage: [backend/api.md](../backend/api.md).

## POST /api/analyze

**Request (zip):** `multipart/form-data` — field `file`

**Request (GitHub):** `multipart/form-data` — field `github_url`

**Response 200:**

```json
{
  "job_id": "uuid",
  "status": "complete",
  "metadata": { "generated_at": "..." },
  "repository": { "name": "owner/repo", "source": "github" },
  "summary": { "file_count": 4, "node_count": 4, "edge_count": 4, "cycle_count": 1 },
  "statistics": { "class_count": 0, "function_count": 0, "internal_dependency_count": 0, "external_dependency_count": 0 },
  "graph": { "nodes": ["..."], "edges": [{ "source": "...", "target": "...", "type": "imports" }] },
  "analysis": { "cycles": { "has_cycles": true, "cycle_count": 1, "cycles": [] }, "scores": [] },
  "files": { "path.py": { } }
}
```

Score floats rounded to **four decimal places** in JSON.

| Status | When |
|--------|------|
| 400 | Empty upload, invalid zip, bad URL, both inputs, no `.py` files |
| 404 | GitHub repo not found |
| 502 | `git clone` failed |

**Planned 202:**

```json
{ "repo_id": "uuid", "status": "processing" }
```

## GET /api/impact/{repo_id}

**Query:** `file` — repo-relative path (URL-encoded)

**Response 200:**

```json
{
  "target": {
    "file": "mini_repo/myapp/models.py",
    "score": {
      "pagerank": 0.3124,
      "betweenness": 0.0,
      "criticality": 0.6,
      "in_degree": 1,
      "out_degree": 1
    }
  },
  "direct_dependents": ["mini_repo/myapp/utils.py"],
  "indirect_dependents": ["mini_repo/myapp/auth.py"],
  "layers": [
    { "depth": 1, "files": ["mini_repo/myapp/utils.py"] },
    { "depth": 2, "files": ["mini_repo/myapp/auth.py"] }
  ],
  "summary": {
    "direct": 1,
    "indirect": 1,
    "total": 2,
    "max_depth": 2,
    "files_affected_percentage": 50.0
  }
}
```

| Status | When |
|--------|------|
| 400 | Missing `file` |
| 404 | Unknown `repo_id` or file not in graph |

## GET /api/status/{repo_id} (planned)

```json
{
  "repo_id": "uuid",
  "status": "pending | processing | complete | failed",
  "error": null,
  "metrics": [
    { "stage_name": "ast_parsing", "duration_ms": 8400, "files_processed": 247 }
  ]
}
```

## GET /api/graph/{repo_id} (planned)

Nodes with `composite_score`, `pagerank`, `betweenness`, degrees; edges; cycles; statistics.

## GET /api/repos (planned)

```json
[{ "repo_id": "uuid", "name": "myproject", "status": "complete", "node_count": 47, "created_at": "..." }]
```

## GET /health

```json
{ "status": "ok" }
```

# API Schema

> **Current** shapes reflect shipped endpoints. **Target** shapes are the repo-centric contract — see [product/repo-centric-api-plan.md](../product/repo-centric-api-plan.md). HTTP usage: [backend/api.md](../backend/api.md).

---

## Current (shipped)

Ripple has **two analyze POST endpoints** with the same request body but different responses. See [backend/api.md — Two ways to analyze](../backend/api.md#two-ways-to-analyze).

| Name | Route | Response |
|------|-------|----------|
| **Quick Analysis** | `POST /api/analyze` | Full JSON (graph, scores, files inline) |
| **Repository Analysis** | `POST /api/repos/analyze` | Slim (`repo_id`, `job_id`, `status`, `repository`) |

### POST /api/analyze — Quick Analysis

**Request (zip):** `multipart/form-data` — field `file`

**Request (GitHub):** `multipart/form-data` — field `github_url`

**Response 200 (fat JSON):**

```json
{
  "repo_id": "uuid",
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

**IDs:** `repo_id` = `repositories.id` (use in GET URLs). `job_id` = `analysis_jobs.id` (one per run). Both are always returned when persistence is enabled.

Score floats rounded to **four decimal places** in JSON.

| Status | When |
|--------|------|
| 400 | Empty upload, invalid zip, bad URL, both inputs, no `.py` files |
| 404 | GitHub repo not found |
| 502 | `git clone` failed |

### GET /health

```json
{ "status": "ok" }
```

---

## Target (repo-centric)

Full spec: [product/repo-centric-api-plan.md](../product/repo-centric-api-plan.md).

### Phase 1 — shipped

#### POST /api/repos/analyze — Repository Analysis

Same request as Quick Analysis (`POST /api/analyze`).

**Response 200 (slim):**

```json
{
  "repo_id": "uuid",
  "job_id": "uuid",
  "status": "complete",
  "repository": {
    "name": "mini_repo",
    "source": "zip"
  }
}
```

**Planned 202:**

```json
{ "repo_id": "uuid", "job_id": "uuid", "status": "processing" }
```

### GET /api/repos

```json
[
  {
    "repo_id": "uuid",
    "name": "pallets/click",
    "source": "github",
    "status": "complete",
    "summary": {
      "file_count": 63,
      "node_count": 63,
      "edge_count": 148,
      "cycle_count": 4
    },
    "created_at": "2026-07-09T12:00:00Z",
    "analyzed_at": "2026-07-09T12:01:30Z"
  }
]
```

### GET /api/repos/{repo_id}

```json
{
  "repo_id": "uuid",
  "repository": {
    "name": "pallets/click",
    "source": "github",
    "owner": "pallets",
    "repo_name": "click"
  },
  "summary": {
    "file_count": 63,
    "node_count": 63,
    "edge_count": 148,
    "cycle_count": 4
  },
  "statistics": {
    "class_count": 120,
    "function_count": 450,
    "external_dependency_count": 12,
    "graph_density": 0.038
  },
  "job_id": "uuid"
}
```

### Phase 2 — shipped

All three sub-routes resolve the repository's **latest completed job**.

#### GET /api/repos/{repo_id}/graph

```json
{
  "repo_id": "uuid",
  "nodes": ["path/to/a.py", "path/to/b.py"],
  "edges": [
    { "source": "path/to/a.py", "target": "path/to/b.py", "type": "imports" }
  ],
  "cycles": {
    "has_cycles": true,
    "cycle_count": 1,
    "cycles": [
      {
        "nodes": ["a.py", "b.py"],
        "length": 2,
        "edges": [
          { "source": "a.py", "target": "b.py", "type": "imports" },
          { "source": "b.py", "target": "a.py", "type": "imports" }
        ]
      }
    ]
  }
}
```

`nodes`/`edges`/`cycles` reuse the same serializers as the fat `POST /api/analyze` payload (`graph.*` and `analysis.cycles`).

#### GET /api/repos/{repo_id}/scores

```json
{
  "repo_id": "uuid",
  "scores": [
    {
      "file_path": "myapp/models.py",
      "pagerank": 0.3124,
      "betweenness": 0.0,
      "criticality": 0.6,
      "in_degree": 3,
      "out_degree": 1
    }
  ]
}
```

DB column `composite_score` maps to JSON field `criticality`.

#### GET /api/repos/{repo_id}/impact

**Path:** `repo_id` — `repositories.id` only (`analysis_jobs.id` is rejected).

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
| 404 | Repository not found, no completed analysis, or file not in graph |

---

## Deferred (not in repo-centric task)

### GET /api/status/{repo_id}

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

### Job history (explicitly out of scope)

- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /api/repos/{repo_id}/jobs`

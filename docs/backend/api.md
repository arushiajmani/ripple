# API

| | |
|---|---|
| **Status** | Partial — repo-centric Phases 1 & 2 shipped; job APIs (Phase 3) remain |
| **Owner** | Backend |
| **Last Updated** | 2026-07-10 |

**Related components:** [Ingestion](ingestion.md) · [Pipeline](pipeline.md) · [Graph builder](graph-builder.md#impact-analysis) · [Persistence](persistence.md)

**Plan:** [product/repo-centric-api-plan.md](../product/repo-centric-api-plan.md) · [API resource model](../architecture/api-resources.md)

**Tests:** `tests/test_api.py` (31) · `tests/test_db_queries.py` (4)

**Source files:** `app/api/routes.py` · `app/api/repos.py` · `app/api/analyze_request.py` · `app/api/errors.py` · `app/api/analysis.py` · `app/api/impact.py` · `app/main.py`

---

## ID model (read this first)

Ripple follows **repository → jobs → results**. See [architecture/api-resources.md](../architecture/api-resources.md).

| ID | Table | Use |
|----|-------|-----|
| **`repo_id`** | `repositories.id` | Repository GET URLs (latest completed job) |
| **`job_id`** | `analysis_jobs.id` | Returned on POST; job APIs (Phase 3) for history/async |

Every analyze returns **both** IDs. Re-analyze → same `repo_id`, new `job_id`.

All GET URLs (`GET /api/repos/{repo_id}/…`) require **`repo_id`** (`analysis_jobs.id` is rejected).

---

## Overview

FastAPI exposes analysis over HTTP. Interactive docs: http://localhost:8000/docs

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload
```

Health: `curl http://localhost:8000/health` → `{"status":"ok"}`

Full request/response schemas: [reference/api-schema.md](../reference/api-schema.md).

---

## Two ways to analyze

Ripple exposes **two POST endpoints** that run the **same pipeline** (ingest → parse → graph → persist). They differ only in the **response shape** — not in what gets analyzed or stored.

| | **Repository Analysis** | **Quick Analysis** |
|---|-------------------------|-------------------|
| **Route** | `POST /api/repos/analyze` | `POST /api/analyze` |
| **Response** | Slim — `repo_id`, `job_id`, `status`, `repository` | Full — graph, scores, cycles, files inline |
| **Best for** | UIs and repo-centric clients | Scripts, debugging, one-shot dumps |
| **Follow-up** | Fetch graph/scores/impact via `GET /api/repos/{repo_id}/…` | Everything is already in the response |

**Why two endpoints?** A frontend does not need the entire graph in the analyze response — it only needs `repo_id` to load `/graph`, `/scores`, and `/impact` on demand. Quick Analysis keeps the original “give me everything now” contract for CLI tools and ad-hoc inspection without extra GETs.

Both accept the same input (**either** zip `file` **or** `github_url`). Both persist to PostgreSQL and return the same `repo_id` + `job_id`. Each call creates a **new** `job_id` (new run); re-analyzing the same repo reuses `repo_id`.

Implementation: shared runner `app/api/analyze_request.py` — handlers differ only in how they serialize the response.

---

## Repository Analysis (preferred)

Repo-centric workflow: analyze → list/detail → graph / scores / impact sub-routes.

### POST /api/repos/analyze — Repository Analysis

Same inputs as Quick Analysis: **either** `file` (zip) **or** `github_url`. Returns a **slim** response (no graph payload).

```bash
curl -s -X POST http://localhost:8000/api/repos/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool
```

```json
{
  "repo_id": "uuid",
  "job_id": "uuid",
  "status": "complete",
  "repository": { "name": "mini_repo", "source": "zip" }
}
```

### GET /api/repos

List repositories with summary from each repo's **latest completed** job.

```bash
curl -s http://localhost:8000/api/repos | python3 -m json.tool
```

### GET /api/repos/{repo_id}

Detail for the latest completed analysis (summary + statistics).

```bash
REPO_ID=$(curl -s -X POST http://localhost:8000/api/repos/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['repo_id'])")

curl -s "http://localhost:8000/api/repos/${REPO_ID}" | python3 -m json.tool
```

| Status | When |
|--------|------|
| 404 | Unknown `repo_id`, or no completed analysis |

### GET /api/repos/{repo_id}/graph

Import graph (`nodes`, `edges`, `cycles`) for the latest completed job — the payload the Cytoscape frontend consumes.

```bash
curl -s "http://localhost:8000/api/repos/${REPO_ID}/graph" | python3 -m json.tool
```

### GET /api/repos/{repo_id}/scores

Criticality-ranked score list (most critical first) for the latest completed job.

```bash
curl -s "http://localhost:8000/api/repos/${REPO_ID}/scores" | python3 -m json.tool
```

### GET /api/repos/{repo_id}/impact?file=...

On-demand blast radius for one file in the latest completed job.

```bash
curl -s "http://localhost:8000/api/repos/${REPO_ID}/impact?file=mini_repo/myapp/models.py" \
  | python3 -m json.tool
```

| Status | When |
|--------|------|
| 400 | Missing or empty `file` query param |
| 404 | Unknown `repo_id` / no completed analysis, or file not in graph |

All three sub-routes resolve the **latest completed job** via `get_latest_completed_job(repo_id)` and reload the full `PipelineResult` (`load_pipeline_result`), warmed through the in-process `AnalysisStore`.

---

## Quick Analysis

One-shot full JSON — graph, scores, files, and metadata in a single response. No follow-up GETs required.

### POST /api/analyze — Quick Analysis

Fat JSON response (graph, scores, files inline). Also returns **`repo_id`** and **`job_id`**.

Use **Repository Analysis** (`POST /api/repos/analyze`) when building a UI that loads `/graph`, `/scores`, and `/impact` separately. Use **Quick Analysis** when you want the full payload in one request (scripts, `result.json`-style dumps).

> The standalone `GET /api/impact/{repo_id}` route was removed — use `GET /api/repos/{repo_id}/impact`.

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool
```

---

## Error handling

Both analyze endpoints share one request runner (`app/api/analyze_request.py`),
and domain exceptions are translated to HTTP responses in one place
(`app/api/errors.py`, registered on the app in `main.py`) rather than via
per-endpoint `try/except`. Every error body is `{"detail": "..."}`.

| Status | When |
|--------|------|
| 400 | Both `file` and `github_url` given, or neither; empty upload; invalid zip; unsafe archive path; invalid GitHub URL; repository has no Python files |
| 404 | GitHub repository not found; unknown `repo_id`; file not in graph |
| 502 | `git clone` failed |

---

## Planned — Phase 3 & beyond

| Phase | Endpoints |
|-------|-----------|
| **3** | `GET /api/jobs/{job_id}`, job sub-routes, optional job history list |
| **4** | Async `POST` → 202, poll `GET /api/jobs/{job_id}` |

Detail: [architecture/api-resources.md](../architecture/api-resources.md).

---

## Tests

```bash
pytest tests/test_api.py -v
pytest tests/test_db_queries.py -v
```

## Further reading

- [product/repo-centric-api-plan.md](../product/repo-centric-api-plan.md)
- [reference/api-schema.md](../reference/api-schema.md)
- [CLI reference — API](../development/cli-reference.md#api--analyze-via-http)

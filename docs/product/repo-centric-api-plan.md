# Repo-centric REST API — Implementation Plan

| | |
|---|---|
| **Status** | Phases 1 & 2 implemented; Phase 3 (job APIs) planned |
| **Owner** | Backend |
| **Last Updated** | 2026-07-10 |
| **Audience** | Implementing agents / contributors |

**Related:** [API resource model](../architecture/api-resources.md) · [backend/api.md](../backend/api.md) · [reference/api-schema.md](../reference/api-schema.md) · [backend/persistence.md](../backend/persistence.md) · [reference/database-schema.md](../reference/database-schema.md)

---

## Target architecture

Ripple follows the **repository → jobs → results** pattern used in mature analysis systems. Full rationale, endpoint matrix, and rollout: **[architecture/api-resources.md](../architecture/api-resources.md)**.

### Two analyze POST endpoints

Same pipeline; different response. Documented names (see [backend/api.md](../backend/api.md#two-ways-to-analyze)):

| Name | Route | Response |
|------|-------|----------|
| **Repository Analysis** | `POST /api/repos/analyze` | Slim — `repo_id` + follow-up GETs |
| **Quick Analysis** | `POST /api/analyze` | Full JSON inline |

```text
Repository APIs     GET /repos/{repo_id}/graph   →  latest job (default UX)
Job APIs            GET /jobs/{job_id}/graph       →  specific run (history, async)
```

---

## Delivery phases

This refactor is split into **phases**. Phase 1 alone delivers a clean, repo-centric REST API. Phase 2 adds repo sub-routes. Phase 3 adds job APIs for history.

| | Phase 1 (implemented) | Phase 2 (implemented) | Phase 3 (later) |
|---|-------------------------|----------------|-----------------|
| **Scope** | Slim POST, list, detail | `/graph`, `/scores`, `/impact` under `/repos/{repo_id}` | `/jobs/{job_id}`, job sub-routes, optional job history |
| **Default job** | Latest completed | Latest completed | Explicit per job |
| **Legacy** | Fat `POST /api/analyze` + `GET /api/impact` coexist | Duplicate `GET /api/impact/{repo_id}` removed; fat `POST /api/analyze` kept | Async 202 + poll |

**Phase 1 is complete on its own.** Do not block it on graph/scores/impact.

---

## Purpose

This document is the **single source of truth** for the API refactor. An implementing agent should read this file and implement **Phase 1 only** unless explicitly asked for Phase 2.

### Goals

1. **Repository-centric URLs** — the frontend thinks in repos (`click`, `flask`), not analysis runs.
2. **Slim `POST`** — analyze returns identifiers (+ optional metadata), not the full graph payload.
3. **Return both IDs on POST** — `repo_id` for repository URLs; `job_id` for async, history, and comparisons (Phase 3).
4. **Phase 2:** graph, scores, impact under `/api/repos/{repo_id}/…` (latest job).
5. **Phase 3:** mirror sub-routes under `/api/jobs/{job_id}/…` for history.

### Non-goals (Phases 1–2)

- Job APIs (`GET /jobs/…`) — **Phase 3**, not blocked by Phase 2
- `GET /repos/{repo_id}/jobs` list — Phase 3 (optional history UI)
- Async `202` + polling (future; response shape is forward-compatible)
- Idempotent “same zip → skip re-analysis” (future)
- CORS (separate frontend task unless bundled)
- SQL-only partial reads for `/graph` (future optimization — see below)

---

## ID model

### Database (unchanged)

```text
repositories (repo_id = repositories.id)
    │
    ├── analysis_jobs (job_id = analysis_jobs.id)   ← new row every analyze
    ├── files              (job_id FK)
    ├── dependencies       (job_id FK)
    ├── node_scores        (job_id FK)
    ├── cycles             (job_id FK)
    └── analysis_statistics (job_id PK)
```

Re-analyzing `pallets/click` creates **one** `repositories` row (reused) and **new** `analysis_jobs` row (Job B, Job C, …).

### API (target)

| ID | Exposed? | Meaning |
|----|----------|---------|
| `repo_id` | **Yes** — repository GET URLs | `repositories.id` (UUID) |
| `job_id` | **Yes** — POST body; job GET URLs (Phase 3) | `analysis_jobs.id`; new every analyze |

### PersistResult (internal dataclass)

Use explicit field names in Python; map to `repo_id` in JSON responses.

```python
@dataclass
class PersistResult:
    repository_id: UUID   # repositories.id — expose as repo_id in API JSON
    job_id: UUID          # analysis_jobs.id
```

### Shipped (Phase 1)

`persist_pipeline_result()` returns `PersistResult`. Legacy `POST /api/analyze` returns `job_id` and `repo_id` at the top of the JSON. `GET /api/repos/{repo_id}/impact` accepts `repositories.id` only.

---

## Data loading — correctness first

**For V1, always reload the full `PipelineResult`.** Do not optimize.

```text
job = get_latest_completed_job(session, repo_id)
result = load_pipeline_result(session, str(job.id))
# serialize from result
```

**Correctness first. SQL optimization later.**

Later you can make `GET /graph` query only `dependencies` (and related tables) instead of rebuilding everything in memory. That is explicitly **out of scope** for Phase 1 and Phase 2. Both phases should use `load_pipeline_result()` for any endpoint that needs graph/score/impact data.

---

## Target request flow

```text
POST /api/repos/analyze
        │
        ▼
   Ingest (zip / GitHub)
        │
        ▼
   AnalysisPipeline.run()
        │
        ▼
   persist_pipeline_result()  →  PersistResult(repository_id, job_id)
        │
        ▼
   AnalysisStore.save(job_id, result)   ← key stays job_id internally
        │
        ▼
   Return { repo_id, job_id?, status }
        │
        ▼
   cleanup temp dir
```

All `GET /api/repos/{repo_id}/…` handlers (Phase 2 sub-routes):

```text
job = get_latest_completed_job(session, repo_id)
result = load_pipeline_result(session, str(job.id))   # always full reload in V1
```

---

## Core helper (Phase 1)

**File:** `app/db/queries.py` (new) or `app/db/load.py` (extend)

```python
def get_latest_completed_job(session: Session, repo_id: uuid.UUID) -> AnalysisJob | None:
    """Return the most recent complete analysis for a repository."""
    return session.scalar(
        select(AnalysisJob)
        .where(
            AnalysisJob.repo_id == repo_id,
            AnalysisJob.status == "complete",
        )
        .order_by(
            AnalysisJob.completed_at.desc().nullslast(),
            AnalysisJob.created_at.desc(),
        )
        .limit(1)
    )
```

**Errors:**

| Situation | HTTP |
|-----------|------|
| `repositories` row missing | 404 `Repository not found` |
| Repo exists, no `complete` job | 404 `No completed analysis for repository` |
| Future: only `processing` jobs | 404 or 409 (defer until async) |

---

## Endpoint specification

Base prefix: **`/api/repos`**. Legacy paths stay until Phase 2 (see Migration).

### Phase 1 — ship these

#### POST /api/repos/analyze

Same inputs as today: `multipart/form-data` with **either** `file` (zip) **or** `github_url`.

**Response 200:**

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

- `repo_id` = `PersistResult.repository_id` (**required**)
- `job_id` = `PersistResult.job_id` (**optional for clients**; include for future-proofing)
- Do **not** include `graph`, `analysis`, `files`

| Status | When |
|--------|------|
| 400 | Empty upload, invalid zip, bad URL, both inputs, no Python files |
| 404 | GitHub repo not found |
| 502 | `git clone` failed |

#### GET /api/repos

List analyzed repositories (dashboard).

**Response 200:**

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

**Query logic:** join `repositories` → latest `analysis_jobs` (complete) → `analysis_statistics`. One list entry per repository. Summary can come from `analysis_statistics` without loading full `PipelineResult`.

#### GET /api/repos/{repo_id}

Repository summary for the **latest completed** job.

**Response 200:**

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

- `job_id` in response is **informational**; frontend may ignore.
- Prefer `analysis_statistics` + `repositories` for summary/detail; use `load_pipeline_result` only if needed for fields not in stats tables.

**Phase 1 stops here.** You already have a clean REST API: analyze → list → detail.

---

### Phase 2 — follow-up PR

These endpoints already exist logically; Phase 2 mostly changes how they are addressed (`repo_id` + latest job, not `job_id` in the URL).

#### GET /api/repos/{repo_id}/graph

Graph payload for Cytoscape (latest completed job).

**Response 200:**

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
    "cycles": [["a.py", "b.py", "a.py"]]
  }
}
```

**Implementation:** `get_latest_completed_job` → **`load_pipeline_result(session, job.id)`** → serialize with `app/pipeline/serialize.py`. No SQL shortcuts.

#### GET /api/repos/{repo_id}/scores

Criticality list (sorted criticality desc).

**Response 200:**

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

**Implementation:** same full reload path; `node_score_to_dict()`.

#### GET /api/repos/{repo_id}/impact?file=...

On-demand blast radius. This is now the **only** impact route.

**Implementation:** `get_latest_completed_job` → **`load_pipeline_result(session, job.id)`** → `analyze_file_impact_from_result()`.

**Legacy cleanup (done):** the standalone `GET /api/impact/{repo_id}` route was removed — it was byte-for-byte identical to this repo-scoped route.

---

## Phase 1 implementation checklist

Work in this order. **Stop after Phase 1** unless tasked with Phase 2.

### 1 — IDs and persistence

- [x] Add `PersistResult` dataclass (`repository_id`, `job_id`) in `app/db/context.py` or `persist.py`
- [x] Change `persist_pipeline_result()` to return `PersistResult`
- [x] Update `analyze_repository()` in `app/api/analysis.py` to use `repository_id` / `job_id`
- [x] Keep `AnalysisStore.save(job_id, result)` keyed by **job_id**

### 2 — Query helper

- [x] Add `get_latest_completed_job(session, repo_id)` in `app/db/queries.py` or `load.py`
- [x] Add `get_repository()` helper for routes
- [x] Tests with Postgres fixture (`tests/test_db_queries.py`)

### 3 — Routes

- [x] `POST /api/repos/analyze` — slim `{ repo_id, job_id, status, repository }`
- [x] `GET /api/repos` — list with latest job summary
- [x] `GET /api/repos/{repo_id}` — detail
- [x] **Do not** add `/graph`, `/scores`, `/impact` in Phase 1

### 4 — Tests and docs (Phase 1)

- [x] `tests/test_api.py` — slim POST; list; detail; `repo_id` from `repository_id`
- [x] `tests/test_db_persist.py` — `PersistResult` return values
- [x] Update [reference/api-schema.md](../reference/api-schema.md) and [backend/api.md](../backend/api.md) — Phase 1 shipped
- [x] Update [development/cli-reference.md](../development/cli-reference.md) curl examples for Phase 1 routes

**Legacy after Phase 2:** fat `POST /api/analyze` stays; the duplicate `GET /api/impact/{repo_id}` route was removed in favor of `GET /api/repos/{repo_id}/impact`.

---

## Phase 3 implementation checklist (job APIs)

- [ ] `GET /api/jobs/{job_id}` — status, timings, summary
- [ ] `GET /api/jobs/{job_id}/graph`, `/scores`, `/impact`
- [ ] Optional `GET /api/repos/{repo_id}/jobs` — history list for UI timeline
- [ ] Shared serializers with repo routes (only job resolution differs)
- [ ] Async: `POST /api/repos/analyze` → 202; poll `GET /api/jobs/{job_id}`

See [architecture/api-resources.md](../architecture/api-resources.md).

---

## Phase 2 implementation checklist

- [x] `GET /api/repos/{repo_id}/graph` — full `load_pipeline_result` → serialize
- [x] `GET /api/repos/{repo_id}/scores` — full reload → `node_score_to_dict()`
- [x] `GET /api/repos/{repo_id}/impact?file=...` — full reload → existing impact logic
- [x] Shared `resolve_pipeline_result()` helper (`app/api/impact.py`) reused by all three routes
- [x] Extend `tests/test_api.py` for sub-routes + DB reload after store clear
- [x] Removed duplicate `GET /api/impact/{repo_id}` route (identical to the repo-scoped route)
- [ ] Optional: slim or remove fat `POST /api/analyze` (deferred)

**Implementation note:** rather than a separate `app/api/serializers.py`, Phase 2 reuses the existing `app/pipeline/serialize.py` builders (`build_graph`, `build_cycles`, `node_score_to_dict`, `impact_analysis_to_dict`) directly. Each sub-route resolves the latest completed job via `resolve_pipeline_result()` (store cache → `get_latest_completed_job` → `load_pipeline_result`).

---

## Files to create or modify

### Phase 1

| File | Action |
|------|--------|
| `app/db/context.py` or `persist.py` | **Add** `PersistResult` dataclass |
| `app/db/persist.py` | **Modify** — return `PersistResult` |
| `app/db/queries.py` | **Create** — `get_latest_completed_job`, list query |
| `app/api/routes.py` | **Modify** — `POST /api/repos/analyze`, `GET /api/repos`, `GET /api/repos/{repo_id}` |
| `app/api/repos.py` | **Create** (optional) — dedicated router |
| `app/api/analysis.py` | **Modify** — propagate `repository_id` as `repo_id` in JSON |
| `tests/test_api.py` | **Modify** |
| `tests/test_db_persist.py` | **Modify** |

### Phase 2 (additional)

| File | Action |
|------|--------|
| `app/api/routes.py` or `repos.py` | **Add** `/graph`, `/scores`, `/impact` |
| `app/api/impact.py` | **Modify** — resolve via `repo_id` → latest job |
| `app/api/serializers.py` | **Create** (optional) |
| `app/db/load.py` | **Optional** — `load_pipeline_result_for_repo(session, repo_id)` wrapper |

**Do not change:** Alembic schema, `AnalysisPipeline`, graph algorithms, parser.

---

## Serializer reuse (Phase 2)

Prefer `app/pipeline/serialize.py` after **full** `load_pipeline_result()`:

| Endpoint | Reuse |
|----------|-------|
| `/scores` | `node_score_to_dict()` |
| `/graph` edges | `edge_to_dict()` |
| `/graph` cycles | cycle builders from `pipeline_result_to_dict` |
| detail `summary` / `statistics` | `build_summary()`, `build_statistics()` |

---

## AnalysisStore strategy

| Layer | Key | Purpose |
|-------|-----|---------|
| `AnalysisStore` | `repo_id` | In-process cache after analyze |
| PostgreSQL | `repository_id` + `job_id` | Durable storage |
| Repository GET URLs | `repo_id` | Latest completed job |
| Job GET URLs (Phase 3) | `job_id` | Specific run |

Phase 2 GET handlers: `get_latest_completed_job` → `load_pipeline_result` → `store.save(repo_id, result)`.

---

## Test plan

**Prerequisites:** `docker compose up -d db` and `alembic upgrade head`.

### Phase 1

```bash
cd backend && source .venv/bin/activate
pytest tests/test_api.py tests/test_db_persist.py -v
```

| Test | Assert |
|------|--------|
| `POST /api/repos/analyze` | Returns `repo_id` (= `repository_id`); persists all tables |
| Re-analyze same GitHub repo | Same `repo_id`, new `job_id` |
| `GET /api/repos` | Lists repo after analyze |
| `GET /api/repos/{repo_id}` | Summary/statistics match analyze |
| Invalid / unknown `repo_id` | 404 |
| Legacy route | `POST /api/analyze` still works unchanged |

### Phase 2 (additional)

| Test | Assert |
|------|--------|
| `GET …/graph` | Node count matches `summary.node_count` |
| `GET …/scores` | Sorted by criticality |
| `GET …/impact` | Blast radius, `file` validation, `job_id`/unknown-repo → 404 |
| Store cleared | Sub-routes still work via DB reload |

---

## Migration / breaking changes

| When | Before | After |
|------|--------|-------|
| Phase 1 | — | New routes alongside legacy |
| Phase 2 | `GET /api/impact/{repo_id}` | Removed; use `GET /api/repos/{repo_id}/impact` |
| Phase 2 (optional) | Fat `POST /api/analyze` | Deprecated or `?legacy=full` only |

Phase 1 is **additive**. Phase 2 removes the duplicate standalone impact route (the only breaking change; the repo-scoped route is a drop-in replacement).

---

## Frontend contract

**After Phase 1:**

```javascript
const { repo_id } = await analyzeZip(file);
navigate(`/repos/${repo_id}`);
// page loads GET /api/repos/{repo_id} for summary
```

**After Phase 2:**

```javascript
// parallel: GET .../graph and GET .../scores
```

Frontend **never stores `job_id`** in V1.

---

## Open questions (resolved)

| Question | Decision |
|----------|----------|
| One PR or two? | **Two** — Phase 1 stops at list + detail |
| Expose `job_id` in API? | Optional in POST only |
| Which job for GETs? | Latest `status = complete` |
| Job history endpoints? | **No** |
| Optimize GET /graph SQL? | **No** — full `load_pipeline_result` in V1 |
| `PersistResult` fields? | `repository_id`, `job_id` (JSON: `repo_id`, `job_id`) |

---

## Acceptance criteria

### Phase 1 done when

1. `persist_pipeline_result()` returns `PersistResult(repository_id, job_id)`.
2. `POST /api/repos/analyze` returns slim JSON with correct `repo_id`.
3. `GET /api/repos` and `GET /api/repos/{repo_id}` work via latest completed job.
4. Tests pass with Postgres up.
5. Docs updated; Phase 2 endpoints still marked planned.
6. Legacy `POST /api/analyze` unchanged; duplicate `GET /api/impact` removed.

### Phase 2 done when

1. `/graph`, `/scores`, `/impact` work under `/api/repos/{repo_id}/…`.
2. All handlers use **full** `load_pipeline_result` (no SQL shortcuts).
3. Impact works via `repo_id` after `AnalysisStore` is cleared.
4. Docs and tests updated for Phase 2.

---

*When a phase ships, update **Status** and check off items in git history.*

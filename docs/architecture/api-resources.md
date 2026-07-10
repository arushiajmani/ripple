# API resource model

| | |
|---|---|
| **Status** | Target architecture (Phases 1 & 2 shipped; Phase 3 planned) |
| **Owner** | Backend |
| **Last Updated** | 2026-07-09 |

**Related:** [repo-centric API plan](../product/repo-centric-api-plan.md) · [backend/api.md](../backend/api.md) · [database schema](../reference/database-schema.md)

---

## Why this shape

Mature analysis systems separate **what was analyzed** (repository) from **when it was analyzed** (job). Results (graph, scores, impact) belong to a job; the default UX shows the **latest** run without forcing users to track job IDs.

```text
Repository                    ← stable identity (click, flask, my_upload.zip)
    │
    ├── Analysis Job A        ← one run (timestamps, status, metrics)
    │       └── Results       ← files, dependencies, scores, cycles, stats
    ├── Analysis Job B
    └── Analysis Job C
```

PostgreSQL already models this: `repositories` → `analysis_jobs` → child tables keyed by `job_id`.

---

## Resource hierarchy

| Resource | Table | Role |
|----------|-------|------|
| **Repository** | `repositories` | Logical project identity; reused across re-analyzes |
| **Analysis job** | `analysis_jobs` | One pipeline execution; new row every `POST …/analyze` |
| **Results** | `files`, `dependencies`, `node_scores`, `cycles`, `analysis_statistics` | Artifacts for one job |

---

## API layers

Two URL families share the same serializers; they differ only in **which job** supplies the data.

### Two analyze POST endpoints

Same ingest + pipeline + persist; different response shape. See [backend/api.md — Two ways to analyze](../backend/api.md#two-ways-to-analyze).

| Name | Route | Response | Typical client |
|------|-------|----------|----------------|
| **Repository Analysis** | `POST /api/repos/analyze` | Slim (`repo_id`, `job_id`, `repository`) | Frontend — load `/graph`, `/scores`, `/impact` on demand |
| **Quick Analysis** | `POST /api/analyze` | Full JSON inline | CLI, scripts, one-shot inspection |

### Repository APIs (default — user-friendly)

**Rule:** `GET /api/repos/{repo_id}/…` resolves the **latest completed** job via `get_latest_completed_job(repo_id)`.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/repos/analyze` | **Repository Analysis** — start analysis → `{ repo_id, job_id, status }` |
| `GET` | `/api/repos` | List repositories |
| `GET` | `/api/repos/{repo_id}` | Summary + statistics (latest job) |
| `GET` | `/api/repos/{repo_id}/graph` | Graph payload (latest job) |
| `GET` | `/api/repos/{repo_id}/scores` | Criticality list (latest job) |
| `GET` | `/api/repos/{repo_id}/impact?file=…` | Blast radius (latest job) |

Frontend V1 flow:

```text
POST /api/repos/analyze  →  repo_id
GET  /api/repos/{repo_id}/graph
GET  /api/repos/{repo_id}/scores
```

`job_id` is returned on POST for logging, async polling, and future history — **not required in the default UI**.

### Job APIs (history, comparisons, async)

**Rule:** `GET /api/jobs/{job_id}/…` loads **that specific** job.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/jobs/{job_id}` | Job status, timings, error, summary |
| `GET` | `/api/jobs/{job_id}/graph` | Graph for a past run |
| `GET` | `/api/jobs/{job_id}/scores` | Scores for a past run |
| `GET` | `/api/jobs/{job_id}/impact?file=…` | Impact for a past run |
| `GET` | `/api/repos/{repo_id}/jobs` | Job history list (optional; UI timeline) |

Not shipped yet. Same `load_pipeline_result(session, job_id)` under the hood.

---

## POST response contract

Every analyze endpoint returns **both** IDs:

```json
{
  "job_id": "uuid",
  "repo_id": "uuid",
  "status": "complete"
}
```

| Field | Meaning |
|-------|---------|
| `repo_id` | `repositories.id` — use in repository GET URLs |
| `job_id` | `analysis_jobs.id` — use when polling async jobs or comparing runs |

Re-analyze same zip/GitHub repo → **same `repo_id`**, **new `job_id`**.

---

## Default resolution

```text
GET /api/repos/{repo_id}/graph
        │
        ▼
get_latest_completed_job(repo_id)
        │
        ▼
load_pipeline_result(session, job.id)
        │
        ▼
serialize → JSON
```

**Correctness first:** full `PipelineResult` reload in V1. SQL partial reads are a later optimization.

---

## Async (future)

Same POST shape extends naturally:

```json
{ "repo_id": "uuid", "job_id": "uuid", "status": "processing" }
```

Poll `GET /api/jobs/{job_id}` until `status: complete`, then use either:

- `GET /api/repos/{repo_id}/graph` (latest), or
- `GET /api/jobs/{job_id}/graph` (that specific run)

---

## Advantages

| Benefit | How |
|---------|-----|
| **Future-proof** | Job row exists before async, history, or comparisons |
| **History** | Job APIs + optional `GET /repos/{repo_id}/jobs` |
| **Async** | Poll by `job_id`; repo URLs still work when complete |
| **Comparisons** | Diff job A vs job B scores/graphs |
| **User-friendly** | Dashboard uses repo URLs only; latest job is implicit |

## Trade-off

Slightly larger API surface (repo routes + job routes). Shared serializers keep implementation cost low.

---

## Rollout in Ripple

| Phase | Scope | Status |
|-------|-------|--------|
| **1** | `POST /api/repos/analyze`, `GET /api/repos`, `GET /api/repos/{repo_id}` | ✓ Shipped |
| **2** | `GET /api/repos/{repo_id}/graph`, `/scores`, `/impact` (latest job) | ✓ Shipped |
| **3** | `GET /api/jobs/{job_id}`, job sub-routes, optional job history list | Planned |
| **4** | Async `POST` → 202, `GET /api/jobs/{job_id}` status poll | Planned |

Implementation checklist: [repo-centric API plan](../product/repo-centric-api-plan.md).

Legacy `POST /api/analyze` (**Quick Analysis** — full JSON in one response) remains for scripts and ad-hoc use. The standalone `GET /api/impact/{repo_id}` route was removed as a duplicate — impact now lives only at `GET /api/repos/{repo_id}/impact`.

---

## What we explicitly defer

- Idempotent “same zip → skip re-analysis”
- CORS (frontend task)
- SQL-only graph reads without full `PipelineResult`

These do not block the resource model above.

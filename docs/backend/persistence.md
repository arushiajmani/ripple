# Persistence

| | |
|---|---|
| **Status** | Partial (schema + sync write on analyze shipped; async 202 + status poll planned) |
| **Owner** | Backend |
| **Last Updated** | 2026-07-08 |

**Related components:** [Pipeline](pipeline.md) · [API](api.md)

**Tests:** `tests/test_db_schema.py` (2) · `tests/test_db_persist.py`

**Source files:** `app/db/models.py` · `app/db/persist.py` · `app/db/load.py` · `app/db/context.py` · `app/database.py` · `alembic/`

---

## Overview

PostgreSQL stores analysis artifacts. ORM models mirror 8 SRS tables; Alembic manages migrations.

**Shipped today:**

- `alembic upgrade head` creates schema
- `POST /api/analyze` writes `PipelineResult` via `app/db/persist.py`
- `GET /api/impact` can load from DB after server restart (`app/db/load.py`)
- `AnalysisStore` still caches in memory for the current process

**Not yet:** async `202`, `GET /api/status`, idempotent zip re-upload cache.

Full table definitions: [reference/database-schema.md](../reference/database-schema.md).

## Memory vs database

```text
Today (sync analyze):
  Ingest → Pipeline → PipelineResult
       → persist to PostgreSQL
       → AnalysisStore.save(job_id, result)
       → return JSON 200
       → cleanup temp dir

Impact query:
  AnalysisStore (memory) or load from DB if store miss
```

Planned async flow: `202` → background persist → poll `GET /api/status/{job_id}`.

## PipelineResult → tables

| In memory | PostgreSQL |
|-----------|------------|
| `graph.nodes` + `analyses` | `files` |
| `graph.edges` | `dependencies` (`dependency_type='import'`) |
| `scores` | `node_scores` (`composite_score` = API `criticality`) |
| `cycles` | `cycles` + `cycle_members` |
| summary counts | `analysis_statistics` |
| repo identity | `repositories`, `analysis_jobs` |

## Apply migrations

From project root:

```bash
docker compose up -d db
cd backend && source .venv/bin/activate
alembic upgrade head
docker compose exec db psql -U ripple -d ripple -c '\dt'
docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"
```

Expected: 9 tables; `version_num = 63207e50c596`.

Generate a new revision after editing models:

```bash
cd backend && source .venv/bin/activate
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Design notes

- **`composite_score` vs `criticality`** — same formula; JSON uses `criticality`, DB uses neutral column name
- **`postgresql_nulls_not_distinct`** on `(owner, repo_name, branch)` — zip rows with `owner = NULL` dedupe correctly on PG15+
- **`cycle_members` PK** — `(cycle_id, position)` orders files along the loop

## Tests

```bash
pytest tests/test_db_schema.py -v    # ORM metadata, no live DB
pytest tests/test_db_persist.py -v   # write path
```

## Further reading

- [CLI reference — Database operations](../development/cli-reference.md#database-operations)
- [reference/database-schema.md](../reference/database-schema.md)

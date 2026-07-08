# Database Schema

> ORM: `app/db/models.py`. Migration: `63207e50c596_initial_schema`. Operations: [cli-reference](../development/cli-reference.md#database-operations).

## Entity relationships

```text
repositories
    └── analysis_jobs
            ├── files
            ├── dependencies      (source_file → target_file)
            ├── node_scores
            ├── cycles
            │     └── cycle_members
            └── analysis_statistics
```

## Tables

| Table | Role |
|-------|------|
| `repositories` | Stable identity: `owner`, `repo_name`, `branch`, or zip `file_hash` |
| `analysis_jobs` | One row per run: `status`, timings |
| `files` | Per-job file index: `file_path`, `line_count`, `syntax_error`, `sha256` |
| `dependencies` | Directed edges; `dependency_type` default `import` |
| `node_scores` | `pagerank_score`, `betweenness_score`, `composite_score`, degrees |
| `cycles` | Cycle header (`length`) |
| `cycle_members` | Ordered files (`position`) |
| `analysis_statistics` | Cached counts, `graph_density` |

## Naming

- API/JSON **`criticality`** = DB **`composite_score`** (same `0.6·norm(PR) + 0.4·norm(BT)` formula)

## PipelineResult mapping

| Memory | Table |
|--------|-------|
| `graph.nodes` + `analyses` | `files` |
| `graph.edges` | `dependencies` |
| `scores` | `node_scores` |
| `cycles` | `cycles`, `cycle_members` |
| summary counts | `analysis_statistics` |

Write path: `app/db/persist.py`. Load path: `app/db/load.py`.

## Example queries

```sql
-- Cycles containing a file
SELECT c.id, c.length
FROM cycles c
JOIN cycle_members cm ON cm.cycle_id = c.id
JOIN files f ON f.id = cm.file_id
WHERE f.file_path = 'myapp/models.py'
  AND c.job_id = :job_id;

-- Latest job for a GitHub repo
SELECT j.*
FROM analysis_jobs j
JOIN repositories r ON r.id = j.repo_id
WHERE r.owner = 'pallets' AND r.repo_name = 'click'
ORDER BY j.completed_at DESC NULLS LAST
LIMIT 1;
```

## Indexes (shipped)

```sql
CREATE INDEX idx_analysis_jobs_repo ON analysis_jobs(repo_id);
CREATE INDEX idx_files_job ON files(job_id);
CREATE INDEX idx_cycle_members_file ON cycle_members(file_id);
CREATE INDEX idx_node_scores_composite ON node_scores(composite_score DESC);
```

Full DDL: `alembic/versions/63207e50c596_initial_schema.py`.

## Design principles

- Normalize repo identity (not raw URLs)
- Version analysis runs (`analysis_version`, `analysis_jobs`)
- Normalize cycles (not `TEXT[]` on one row)
- Cache statistics for fast `GET /api/graph` reads
- `files.sha256` for incremental re-analysis (planned)

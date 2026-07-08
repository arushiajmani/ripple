# API

| | |
|---|---|
| **Status** | Partial (sync analyze + impact shipped; async/graph/repos planned) |
| **Owner** | Backend |
| **Last Updated** | 2026-07-08 |

**Related components:** [Ingestion](ingestion.md) · [Pipeline](pipeline.md) · [Graph builder](graph-builder.md#impact-analysis) · [Persistence](persistence.md)

**Tests:** `tests/test_api.py` (14)

**Source files:** `app/api/routes.py` · `app/api/analysis.py` · `app/api/impact.py` · `app/main.py`

---

## Overview

FastAPI exposes analysis over HTTP. Interactive docs: http://localhost:8000/docs

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload
```

Health: `curl http://localhost:8000/health` → `{"status":"ok"}`

Full request/response schemas: [reference/api-schema.md](../reference/api-schema.md).

## POST /api/analyze

Accepts **either** a zip upload or a public GitHub URL. Runs synchronously; returns full analysis JSON.

```bash
# Zip (from repo root)
curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool

# GitHub (requires git on server)
curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pypa/sampleproject" | python3 -m json.tool
```

Provide **either** `file` or `github_url`, not both.

Flow: ingest → `AnalysisPipeline.run(local_path)` → persist + `AnalysisStore.save(job_id, result)` → `cleanup()`.

Use returned `job_id` as `repo_id` for impact queries.

| Status | When |
|--------|------|
| 400 | Empty upload, invalid zip, bad URL, both inputs, no Python files |
| 404 | GitHub repo not found |
| 502 | `git clone` failed |

## GET /api/impact/{repo_id}

On-demand blast radius for one file in a previously analyzed repo.

```bash
JOB_ID=$(curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

curl -s "http://localhost:8000/api/impact/${JOB_ID}?file=mini_repo/myapp/models.py" \
  | python3 -m json.tool
```

| Status | When |
|--------|------|
| 400 | Missing or empty `file` query param |
| 404 | Unknown `repo_id` or file not in graph |

Does not re-parse or rebuild the graph. Algorithm detail: [graph-builder.md](graph-builder.md#impact-analysis).

## Planned endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/analyze` → 202 | Async job + poll |
| `GET /api/status/{repo_id}` | Job status + `metrics[]` |
| `GET /api/graph/{repo_id}` | Graph JSON for frontend |
| `GET /api/repos` | Analysis history |

## Tests

```bash
pytest tests/test_api.py -v
pytest tests/test_api.py -k impact -v
```

## Further reading

- [reference/api-schema.md](../reference/api-schema.md)
- [CLI reference — API](../development/cli-reference.md#api--analyze-via-http)

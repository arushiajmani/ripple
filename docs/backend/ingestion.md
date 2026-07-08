# Ingestion

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Backend |
| **Last Updated** | 2026-07-08 |

**Related components:** [Pipeline](pipeline.md) · [API](api.md) · [Parser](parser.md)

**Tests:** `tests/test_ingestion.py` (8) · `tests/test_github_ingestion.py` (17)

**Source files:** `app/ingestion/service.py` · `app/ingestion/zip.py` · `app/ingestion/github.py` · `app/ingestion/validation.py` · `app/ingestion/models.py`

---

## Overview

`IngestionService` materializes a Python project on disk. Zip and GitHub paths produce a `RepositoryHandle` with `local_path` for `AnalysisPipeline.run()` — the pipeline never cares which source was used.

There is **no** `python -m app.ingestion` CLI; use the API, Python API, or pytest.

## API

| Method | Purpose |
|--------|---------|
| `ingest_zip(path, job_id=...)` | Extract zip on disk |
| `ingest_zip_bytes(data, job_id=...)` | Extract from upload bytes |
| `ingest_github(url, job_id=...)` | Shallow clone (`git clone --depth 1`) |
| `cleanup(result)` | Remove `{base_dir}/{job_id}/` |

Default layout: `/tmp/ripple/{job_id}/` (override with `IngestionService(base_dir=...)`).

## Validation

- **Zip-slip** — paths like `../outside.py` rejected; partial dir removed on failure
- **GitHub** — `parse_github_url`, `git ls-remote` before clone
- Errors: `InvalidGitHubUrlError`, `RepositoryNotFoundError`, `CloneError`

Requires **git** on the server for GitHub URLs.

## Python example

```python
from app.ingestion import IngestionService
from app.pipeline import AnalysisPipeline

service = IngestionService()
ingestion = service.ingest_zip("project.zip")

try:
    result = AnalysisPipeline().run(ingestion.local_path)
    result.write_json("result.json")
finally:
    service.cleanup(ingestion)
```

## Import resolution (relative imports)

`from .utils import helper` in `myproject/auth/session.py` resolves to `myproject/auth/utils.py`.

`from ..config import settings` → one level up + `config.py`.

Third-party packages (`import requests`) stay in `external_deps`, not graph nodes.

## Tests

```bash
cd backend && source .venv/bin/activate
pytest tests/test_ingestion.py -v          # zip (8)
pytest tests/test_github_ingestion.py -v   # GitHub (17)
pytest tests/test_api.py -v                # HTTP analyze + impact (14)

# Skip live GitHub clone (CI / offline):
pytest tests/test_github_ingestion.py -v -m "not integration"
```

## HTTP integration

`POST /api/analyze` accepts `file` (zip) or `github_url`. Flow: ingest → pipeline → persist/store → `cleanup()` in `finally`.

Detail: [api.md](api.md).

**Zip note:** if the archive has a top-level folder (`myproject/...`), graph paths include that prefix.

## Further reading

- [CLI reference — Ingestion](../development/cli-reference.md#ingestion-zip-and-github)
- [examples/](../examples/) — analyze cloned public repos

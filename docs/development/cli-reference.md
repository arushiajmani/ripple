> Canonical command reference. Module concepts: [backend/](../backend/). Schemas: [reference/](../reference/).

# CLI Reference

Every command below is written **in full** at least once (including `cd`, venv activation, and real fixture paths).

**Working directory:** almost all backend commands run from `backend/`. Docker commands run from the project root (`ripple/`).

## Command sheet (all inputs)

One table for every way to run something with **your own input** (repo path, file path, or zip). Replace `{repo-path}` with any project directory on disk.

| What you want | Input you provide | Command | Stages covered |
|---------------|-------------------|---------|----------------|
| Parse one file | `.py` file | `python -m app.parser.cli tests/sample_file.py` | AST parse only |
| Parse a whole repo | directory | `python -m app.parser.cli {repo-path}` | file discovery, AST parse, import resolution |
| Parse one file in repo context | repo + relative file | `python -m app.parser.cli {repo-path} myapp/auth.py` | Same, with correct resolved_deps |
| Full analysis report | directory | `python -m app.pipeline {repo-path}` | All stages; cycles + scores printed |
| Full analysis + JSON | directory + output path | `python -m app.pipeline {repo-path} --json result.json` | All stages + JSON export |
| Per-stage timings | directory | `python -m app.benchmark --repo {repo-path}` | All stages + timing table |
| Zip → extract → analyze | zip file | `curl -F file=@…zip …/api/analyze` or pytest — see [Ingestion](#ingestion-zip-and-github) | extract, then pipeline |
| GitHub → clone → analyze | public repo URL | `curl -F github_url=https://github.com/owner/repo …/api/analyze` | clone, then pipeline |
| Impact for one file | `job_id` + file path | `curl "…/api/impact/{job_id}?file=path/to/file.py"` | on-demand blast radius (after analyze) |
| Apply DB migrations | (Postgres running) | `alembic upgrade head` | create/upgrade all SRS tables |
| List DB tables | (Postgres running) | `docker compose exec db psql -U ripple -d ripple -c '\dt'` | 9 tables (8 SRS + `alembic_version`) |
| Check migration revision | (Postgres running) | `docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"` | should show `63207e50c596` |
| Interactive psql | (Postgres running) | `docker compose exec db psql -U ripple -d ripple` | `\dt`, `\d table`, SQL + `;`, `\q` |
| Schema unit tests | (no live DB) | `pytest tests/test_db_schema.py -v` | ORM metadata vs SRS table list |
| Impact unit tests | (synthetic graphs) | `pytest tests/algorithms/test_impact.py -v` | layers, cycles, score lookup |
| Zip ingestion tests | (pytest builds zips) | `pytest tests/test_ingestion.py -v` | extract, zip-slip, cleanup |
| GitHub ingestion tests | (mocked + 1 live clone) | `pytest tests/test_github_ingestion.py -v` | URL parse, clone, cleanup |
| API tests | zip + GitHub + impact | `pytest tests/test_api.py -v` | HTTP → pipeline → cleanup; impact endpoint |
| Run automated tests | (pytest fixtures) | `pytest tests/ -v` | Varies by test file |

**Examples with the built-in fixture** (swap `tests/fixtures/mini_repo` for your repo):

```bash
cd backend
source .venv/bin/activate

python -m app.parser.cli tests/fixtures/mini_repo
python -m app.pipeline tests/fixtures/mini_repo
python -m app.benchmark --repo tests/fixtures/mini_repo

# Your own project on disk:
python -m app.pipeline /path/to/your/python/project
python -m app.benchmark --repo /path/to/your/python/project
```

## Pipeline stages vs repo input

Parser, pipeline, and benchmark all take a **project root directory**. You do not pass separate inputs per stage on the CLI — one repo path runs the full chain. The benchmark breaks out timings **after** the run.

| Stage | In benchmark? | Command |
|-------|-------------|---------|
| `file_discovery` | Yes | `python -m app.parser.cli {repo-path}` |
| `ast_parsing` | Yes | Same parser CLI (per-file output) |
| `import_resolution` | Yes | Same parser CLI (resolved_deps, external_deps) |
| `graph_construction` | Yes | `python -m app.pipeline {repo-path}` |
| Cycle detection | Inside `graph_construction` timer | `python -m app.pipeline {repo-path}` |
| `pagerank_computation` | Yes | `python -m app.benchmark --repo {repo-path}` |
| `betweenness_computation` | Yes | Same benchmark command |
| `score_normalization` | Yes | Same benchmark command |
| `impact_analysis` | On-demand only | `GET /api/impact/{job_id}?file=…` or `ImpactAnalyzer().analyze(digraph, file)` |
| Zip extract | No | `IngestionService.ingest_zip*` or `pytest tests/test_ingestion.py` |
| Git clone | No | `IngestionService.ingest_github` or `pytest tests/test_github_ingestion.py` |

**Why one repo argument:** `AnalysisPipeline.run(repo_path)` orchestrates every stage. The parser CLI stops before graph building; the benchmark adds timing on top of the same pipeline.

## One-time setup (full commands)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After that, keep the venv active in your shell. Re-run `source .venv/bin/activate` in new terminals.

---

## Analysis CLIs (with input)

These commands take **paths as arguments** — a `.py` file, a project directory, or `--repo` for the benchmark.

### Parser — inspect imports and structure

| Command | Input | What it does |
|---------|-------|--------------|
| `python -m app.parser.cli {file-or-repo}` | File or directory | Print imports, classes, functions, deps |
| `python -m app.parser.cli {repo} {relative-file}` | Repo root + path inside repo | One file with full project context |
| `python -m app.parser.ast_parser …` | Same as above | Backward-compatible alias |

**Full commands** (run from `backend/` with venv active):

```bash
cd backend
source .venv/bin/activate

# Single file — no repo context; resolved_deps will be empty
python -m app.parser.cli tests/sample_file.py

# Whole project — pass the project root, not a subpackage
python -m app.parser.cli tests/fixtures/mini_repo

# Use backend/ itself as the project root (paths like app/parser/models.py)
python -m app.parser.cli .

# One file from inside mini_repo with correct resolved_deps
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
```

**Expected on `mini_repo` / `myapp/auth.py`:** `resolved_deps` includes `myapp/models.py`, `myapp/utils.py`; `external_deps` includes `os`, `requests`.

### Pipeline — full analysis report (+ optional JSON)

| Command | Input | What it does |
|---------|-------|--------------|
| `python -m app.pipeline {repo-path}` | Project directory | Parse → graph → cycles → scores; prints summary, edges, cycles, top 10 |
| `python -m app.pipeline {repo} --json {path}` | Repo + output file | Same analysis; writes JSON to `{path}` |
| `python -m app.pipeline {repo} --json {path} --no-files` | Repo + output file | JSON without per-file files map |

**Full commands:**

```bash
cd backend
source .venv/bin/activate

python -m app.pipeline tests/fixtures/mini_repo

python -m app.pipeline tests/fixtures/mini_repo --json result.json

python -m app.pipeline tests/fixtures/mini_repo --json result.json --no-files
```

**Expected on `mini_repo`:** 1 circular dependency (`models` ↔ `utils`); `myapp/models.py` or `myapp/utils.py` among top critical files.

### Benchmark — per-stage timings

| Command | Input | What it does |
|---------|-------|--------------|
| `python -m app.benchmark --repo {repo-path}` | Project directory (required) | Full pipeline + per-stage timing table |

**Full command:**

```bash
cd backend
source .venv/bin/activate

python -m app.benchmark --repo tests/fixtures/mini_repo
```

**Output includes:** stage timings (`file_discovery` … `score_normalization`) and a **Performance Notes** block explaining steady-state PageRank measurement (untimed warm-up before the timed stage).

**Project root rule:** pass the directory that owns all relative paths (the repo root), not a package subfolder like `app/parser/`. See [§5a — Analysis root convention](../backend/parser.md#analysis-root-convention).

---

## Ingestion (zip and GitHub)

Ripple has **`IngestionService`** — every path produces a `RepositoryHandle` with `local_path` for `AnalysisPipeline.run()`. Zip and GitHub are invisible to the analysis engine. There is **no `python -m app.ingestion` CLI**; use the API, Python API, or pytest.

**Design:** `{base_dir}/{job_id}/` (default `/tmp/ripple/`). Zip extracts archive contents; GitHub shallow-clones (`git clone --depth 1`) into the job dir. Validation: zip-slip protection; GitHub URL parse + `git ls-remote` existence check.

### Run ingestion tests

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_ingestion.py -v          # zip (8)
PYTHONPATH=. pytest tests/test_github_ingestion.py -v   # GitHub (17)
PYTHONPATH=. pytest tests/test_api.py -v                 # HTTP analyze + impact (14)
```

Skip the live GitHub clone in CI or offline runs:

```bash
PYTHONPATH=. pytest tests/test_github_ingestion.py -v -m "not integration"
```

### Zip tests (`test_ingestion.py`)

| Test | What it proves |
|------|----------------|
| `test_ingest_zip_extracts_to_job_directory` | Zip of `mini_repo` extracts under job dir |
| `test_ingest_zip_bytes` | In-memory zip bytes work |
| `test_ingest_zip_generates_job_id_when_omitted` | Auto UUID `job_id` |
| `test_ingest_zip_missing_file_raises` | Missing zip → error |
| `test_ingest_zip_rejects_zip_slip` | Path traversal blocked |
| `test_failed_extract_removes_partial_directory` | Bad zip → no orphan dir |
| `test_cleanup_removes_job_directory` | `cleanup()` removes extract |
| `test_ingested_repo_runs_through_pipeline` | Zip → extract → full pipeline |

### GitHub tests (`test_github_ingestion.py`)

| Test | What it proves |
|------|----------------|
| `test_parse_github_url_*` | URL validation (common forms + rejections) |
| `test_ingest_github_clones_to_job_directory` | Mocked clone lands under job dir |
| `test_ingest_github_rejects_missing_repository` | Remote check failure before clone |
| `test_ingest_github_removes_partial_directory_on_clone_failure` | Failed clone cleans up |
| `test_ingested_github_repo_runs_through_pipeline` | Clone → full pipeline |
| `test_ingest_github_integration_clones_public_repository` | Live clone of `pypa/sampleproject` (`@pytest.mark.integration`) |

### API — analyze via HTTP

```bash
# Server in backend/
uvicorn app.main:app --reload

# Zip (from repo root)
curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool

# GitHub (requires git on server)
curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pypa/sampleproject" | python3 -m json.tool

# Impact (after analyze — use job_id from response)
JOB_ID=$(curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
curl -s "http://localhost:8000/api/impact/${JOB_ID}?file=mini_repo/myapp/models.py" | python3 -m json.tool
```

**Note (zip):** if the zip contains a top-level folder (e.g. `myproject/...`), paths in the graph will include that prefix unless you point the pipeline at the inner root.

---

## Server & infrastructure

| Command | Where | What it does |
|---------|-------|--------------|
| `uvicorn app.main:app --reload` | `backend/` | FastAPI dev server on port 8000 |
| `docker compose up --build` | project root | Start frontend, backend, PostgreSQL |
| `docker compose up -d db` | project root | Start PostgreSQL only |
| `alembic upgrade head` | `backend/` | Apply pending migrations (needs `DATABASE_URL`) |
| `alembic revision --autogenerate -m "…"` | `backend/` | Diff ORM models → new migration file |
| `docker compose exec db psql -U ripple -d ripple` | project root | Interactive Postgres shell |
| `docker compose exec db psql … -c '\dt'` | project root | List tables without entering psql |
| `docker compose exec db psql … -c "SELECT …;"` | project root | Run one SQL statement from bash |

**Full commands:**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
# Health: curl http://localhost:8000/health  →  {"status":"ok"}
```

```bash
cd ripple
docker compose up --build
# Frontend http://localhost:5173  ·  Backend http://localhost:8000
```

```bash
# Database — schema only (from project root)
docker compose up -d db
cd backend && source .venv/bin/activate
alembic upgrade head

# Verify (from project root)
docker compose exec db psql -U ripple -d ripple -c '\dt'
docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"
```

## Database operations

Ripple's Postgres container uses user/database `ripple` / `ripple` (see `docker-compose.yml`). Default URL for local Alembic: `postgresql://ripple:ripple@localhost:5432/ripple`.

### Apply migrations

```bash
docker compose up -d db
cd backend && source .venv/bin/activate
alembic upgrade head
```

### Inspect schema (one-liners from project root)

```bash
docker compose exec db psql -U ripple -d ripple -c '\dt'
docker compose exec db psql -U ripple -d ripple -c '\d alembic_version'
docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"
docker compose exec db psql -U ripple -d ripple -c "SELECT COUNT(*) FROM repositories;"
```

### Interactive `psql`

```bash
docker compose exec db psql -U ripple -d ripple
```

| Command | Purpose |
|---------|---------|
| `\dt` | List tables |
| `\d tablename` | Describe columns and indexes (e.g. `\d alembic_version`) |
| `\q` | Quit |
| `SELECT * FROM files;` | Run SQL — **must end with `;`** |

### Prompts and troubleshooting

| Prompt | Meaning |
|--------|---------|
| `ripple=#` | Ready for input |
| `ripple-#` | Continuation — previous statement not terminated. Type `;` + Enter, or **Ctrl+C** to cancel |

| Problem | Cause | Fix |
|---------|-------|-----|
| `bash: SELECT: command not found` | Ran SQL in bash, not in `psql` | Use `docker compose exec db psql …` or open interactive `psql` first |
| `ripple-#` stuck | Forgot semicolon on previous line | `;` + Enter, or Ctrl+C |
| `alembic` can't connect | Postgres not running | `docker compose up -d db` |
| Empty data tables after migrate only | No analyze run yet | Run `POST /api/analyze` to populate rows; see [persistence](../backend/persistence.md) |

After a successful `alembic upgrade head`, expect **9 tables**: the 8 SRS tables plus `alembic_version` with `version_num = 63207e50c596`.

---

## Automated tests (pytest)

Run from `backend/` with `pytest` (`pythonpath = .` in `pytest.ini`). Integration tests use **in-repo fixtures** (`tests/fixtures/mini_repo/`) and **temp directories** created by pytest — you do not pass paths on the CLI for those.

### Run the full suite

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Runs all **141** tests. `-v` prints one line per test (`PASSED` / `FAILED`).

### Run one suite (full commands)

```bash
cd backend
source .venv/bin/activate

pytest tests/test_parser.py -v       # parser (15)
pytest tests/test_graph.py -v       # GraphBuilder (9)
pytest tests/test_adapter.py -v     # GraphAdapter (4)
pytest tests/test_pipeline.py -v    # AnalysisPipeline on temp repos + mini_repo (9)
pytest tests/test_ingestion.py -v   # zip extract + pipeline (8)
pytest tests/test_benchmark.py -v   # stage metrics + benchmark notes (16)
pytest tests/test_serialize.py -v   # JSON export shape (18)
pytest tests/test_db_schema.py -v   # ORM schema metadata (2)
pytest tests/algorithms/test_cycles.py -v    # CycleDetector (8)
pytest tests/algorithms/test_scoring.py -v    # AlgorithmEngine (13)
pytest tests/algorithms/test_impact.py -v     # ImpactAnalyzer (8)
pytest tests/algorithms/ -v         # cycles + scoring + impact (29)
pytest tests/test_api.py -v         # analyze + impact API (14)
```

See [Command sheet](#command-sheet-all-inputs) for which pytest file maps to which capability. Zip-specific tests are **only** in `test_ingestion.py` (no zip CLI exists yet).

### Run a single test or filter by name

```bash
cd backend
source .venv/bin/activate

PYTHONPATH=. pytest tests/test_parser.py::test_future_import_ignored -v

PYTHONPATH=. pytest tests/test_pipeline.py::test_run_parses_mini_repo_integration -v

PYTHONPATH=. pytest tests/ -k "cycle" -v

PYTHONPATH=. pytest tests/ --collect-only
```

| Shorthand | What it does |
|-----------|--------------|
| `PYTHONPATH=. pytest tests/ -q` | Full suite, minimal output |
| `tests/test_parser.py::test_name` | One test by function name |
| `tests/test_parser.py::test_external_import_forms[absolute]` | One parametrized case |
| `-k "cycle"` | Tests whose names contain `cycle` |
| `--collect-only` | List tests without running |

### Roadmap milestone gates (full commands)

```bash
cd backend
source .venv/bin/activate

PYTHONPATH=. pytest tests/test_parser.py -v

PYTHONPATH=. pytest tests/test_graph.py tests/algorithms/ tests/test_pipeline.py -v
```

### Manual CLI checks (same inputs tests use)

Use these to **verify behavior by eye** before or after pytest. Inputs match what integration tests exercise:

```bash
cd backend
source .venv/bin/activate

# Parser integration (same fixture as test_parse_repository_mini_repo)
python -m app.parser.cli tests/fixtures/mini_repo

# Pipeline integration (same fixture as test_run_parses_mini_repo_integration)
python -m app.pipeline tests/fixtures/mini_repo

# Benchmark metrics (same fixture as test_benchmark.py)
python -m app.benchmark --repo tests/fixtures/mini_repo

# Ingestion (zip + GitHub — pytest; git required for live GitHub test)
PYTHONPATH=. pytest tests/test_ingestion.py tests/test_github_ingestion.py -v
```

**Fixture:** `tests/fixtures/mini_repo/` — intentionally cyclic (`myapp/models.py` ↔ `myapp/utils.py`); shared by parser, pipeline, benchmark, and multiple pytest modules.

---

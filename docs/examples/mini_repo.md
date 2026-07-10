# Example: mini_repo

Built-in test fixture at `backend/tests/fixtures/mini_repo/`. Intentional import cycle for cycle detection demos.

## Repository layout

```text
mini_repo/
└── myapp/
    ├── __init__.py
    ├── auth.py      # imports models, utils; external os, requests
    ├── models.py    # imports utils (cycle)
    └── utils.py     # imports models (cycle)
```

**Cycle:** `models.py` ↔ `utils.py`

## Commands

From `backend/` with venv active:

```bash
python -m app.parser.cli tests/fixtures/mini_repo
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
python -m app.pipeline tests/fixtures/mini_repo
python -m app.benchmark --repo tests/fixtures/mini_repo
python -m app.pipeline tests/fixtures/mini_repo --json /tmp/mini_repo.json
```

## Parser output

`myapp/auth.py`:

```text
file_path: myapp/auth.py
resolved_deps:
  - myapp/models.py
  - myapp/utils.py
external_deps:
  - os
  - requests
functions:
  - login
```

## Graph output

Pipeline summary (representative run):

```text
  files    4
  nodes    4
  edges    4
  cycles   1

Dependency edges:
  myapp/auth.py    →  myapp/models.py
  myapp/auth.py    →  myapp/utils.py
  myapp/models.py  →  myapp/utils.py
  myapp/utils.py   →  myapp/models.py

Circular dependencies:
  1. myapp/models.py → myapp/utils.py → myapp/models.py
```

## Criticality (top files)

| File | crit | in | out | Notes |
|------|------|----|-----|-------|
| `myapp/models.py` | 0.600 | 2 | 1 | On cycle; fan-in from auth + utils |
| `myapp/utils.py` | 0.600 | 2 | 1 | On cycle; fan-in from auth + models |
| `myapp/auth.py` | 0.000 | 0 | 2 | Leaf importer (nothing imports auth) |
| `myapp/__init__.py` | 0.000 | 0 | 0 | Isolated |

Scores are **relative within this repo** — not comparable across projects.

## Impact analysis

After HTTP analyze of `tests/fixtures/mini_repo.zip`:

```bash
REPO_ID=$(curl -s -X POST http://localhost:8000/api/repos/analyze \
  -F "file=@tests/fixtures/mini_repo.zip" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['repo_id'])")

curl -s "http://localhost:8000/api/repos/${REPO_ID}/impact?file=mini_repo/myapp/models.py" \
  | python3 -m json.tool
```

Changing `models.py` affects files that import it (e.g. `auth.py`, `utils.py`) — walk dependents backward along import edges.

## Benchmark

Expect sub-second total time on this fixture. Use as a sanity check before profiling larger repos.

## Tests using this fixture

- `test_parse_repository_mini_repo`
- `test_run_parses_mini_repo_integration`
- `test_ingested_repo_runs_through_pipeline`
- Multiple API tests with `mini_repo.zip`

## Related

- [backend/parser.md](../backend/parser.md)
- [backend/graph-builder.md](../backend/graph-builder.md)
- [reference/json-format.md](../reference/json-format.md)

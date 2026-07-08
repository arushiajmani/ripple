# Testing

> Run from `backend/` with venv active. `pytest.ini` sets `pythonpath = .`.

## Quick start

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt   # one-time
pytest tests/ -v                  # 141 tests
```

## pytest basics

Pytest discovers `test_*.py` files and `test_*` functions. Use `assert` — no boilerplate classes.

| Flag | Effect |
|------|--------|
| `-v` | One line per test (recommended while learning) |
| `-q` | Minimal output |
| `-x` | Stop on first failure |
| `-k "cycle"` | Filter by name substring |
| `--collect-only` | List tests without running |

Run one test:

```bash
pytest tests/test_parser.py::test_future_import_ignored -v
pytest tests/test_parser.py::test_external_import_forms[absolute] -v
```

Exit code `0` = all passed; non-zero = failures or collection error.

### Fixtures and parametrization

Ripple tests use `@pytest.fixture` (e.g. `parser`, `build_digraph`) and `@pytest.mark.parametrize` (counts as multiple tests in `-v` output).

## Strategy by layer

| Suite | File | Tests | Isolates |
|-------|------|-------|----------|
| Parser | `test_parser.py` | 15 | `ASTParser`, `parse_repository` |
| Graph | `test_graph.py` | 9 | `GraphBuilder` — synthetic `FileAnalysis` |
| Adapter | `test_adapter.py` | 4 | `GraphResult` → `nx.DiGraph` |
| Pipeline | `test_pipeline.py` | 9 | Full stack |
| Benchmark | `test_benchmark.py` | 16 | Stage metrics, CLI table |
| Serialize | `test_serialize.py` | 18 | JSON export shape |
| Ingestion (zip) | `test_ingestion.py` | 8 | Zip extract, zip-slip |
| Ingestion (GitHub) | `test_github_ingestion.py` | 17 | URL parse, clone |
| API | `test_api.py` | 14 | HTTP analyze + impact |
| DB schema | `test_db_schema.py` | 2 | ORM metadata (no live DB) |
| DB persist | `test_db_persist.py` | — | Write path |
| Cycles | `algorithms/test_cycles.py` | 8 | `CycleDetector` |
| Scoring | `algorithms/test_scoring.py` | 13 | `AlgorithmEngine` |
| Impact | `algorithms/test_impact.py` | 8 | `ImpactAnalyzer` |

```text
test_parser.py     →  FileAnalysis
test_graph.py      →  GraphResult        (no parser)
test_pipeline.py   →  PipelineResult     (full stack)
test_cycles.py     →  nx.DiGraph only
```

## Per-suite commands

```bash
pytest tests/test_parser.py -v
pytest tests/test_graph.py -v
pytest tests/test_adapter.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_ingestion.py -v
pytest tests/test_github_ingestion.py -v
pytest tests/test_benchmark.py -v
pytest tests/test_serialize.py -v
pytest tests/test_db_schema.py -v
pytest tests/test_db_persist.py -v
pytest tests/algorithms/ -v
pytest tests/test_api.py -v
```

## Milestone gates

```bash
pytest tests/test_parser.py -v
pytest tests/test_graph.py tests/algorithms/ tests/test_pipeline.py -v
```

## Fixture

`tests/fixtures/mini_repo/` — intentional cycle `models.py` ↔ `utils.py`. Shared by parser, pipeline, benchmark, and API tests.

Walkthrough: [examples/mini_repo.md](../examples/mini_repo.md).

## Not covered yet

- Async API + status polling
- Five real open-source repos (manual milestone)
- Private GitHub (OAuth deferred)

## Further reading

- [CLI reference — Automated tests](cli-reference.md#automated-tests-pytest)
- [pytest documentation](https://docs.pytest.org/)
- Per-test name tables remain in [learn.md](../learn.md#testing-overview) until fully ported; prefer suite-level docs above for maintenance.

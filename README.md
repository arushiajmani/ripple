# Ripple

Ripple is a code dependency analysis platform that parses Python repositories, constructs dependency graphs, and identifies critical files, architectural bottlenecks, and change impact paths.

## Features

### Shipped

* **AST parser** — extract imports, classes, functions, and methods from a `.py` file
* **Repo batch parsing** — walk a directory and parse all `.py` files via `parse_repository()`
* **Dependency classification** — internal (`resolved_deps`) vs stdlib/third-party (`external_deps`) when project context is provided
* **Graph builder** — assemble `dict[str, FileAnalysis]` into a `GraphResult` (nodes + directed import edges)
* **Cycle detection** — `CycleDetector` finds circular dependencies via NetworkX (`graph/algorithms/cycles.py`)
* **Criticality scoring** — `AlgorithmEngine`: PageRank (how depended-on), betweenness (bridge/bottleneck), criticality (`0.6 * norm(PR) + 0.4 * norm(BT)` risk rank), in/out degree
* **Analysis pipeline** — parse → graph → cycles → scores (`PipelineResult`)
* **JSON export** — `result.write_json("result.json")` or `python -m app.pipeline <repo> --json result.json`
* **CLI** — parser: `python -m app.parser.cli`; pipeline: `python -m app.pipeline` (report + optional JSON)

### Planned (near term)

* Zip upload ingestion (`IngestionService`)
* Pipeline stage metrics and benchmark CLI (`python -m app.benchmark --repo path/to/project`)
* Impact analysis for proposed changes
* Interactive graph visualization
* REST API for repository analysis

### Future scope — V1 / V2 / V3

| Version | Focus |
|---------|--------|
| **V1 (current)** | File-level import graph — nodes = files, edges = `resolved_deps` |
| **V2** | Class graph (inheritance + dependencies), function/call graphs, impact analysis, library analytics (`external_deps`), graph algorithms |
| **V3** | AI-assisted repository explanations, architectural insights, change-risk estimation |

See [docs/learn.md](docs/learn.md#design-decisions) for design rationale and [docs/learn.md](docs/learn.md#future-scope) for detail.

## Architecture

```
Repository
    ↓
RepositoryParser          parse_repository() — batch walk + ASTParser per file
    ↓
FileAnalysis              canonical parsed record (per file)
    ↓
GraphBuilder              V1: file import graph from resolved_deps only
    ↓
GraphResult
    ↓
CycleDetector             CircularDependencyResult
    ↓
AlgorithmEngine           ScoringResult (PageRank, betweenness, criticality)
    ↓
PipelineResult            analyses + graph + cycles + scores
```

**Parser layer:** `ASTParser`, `FileAnalysis`, RepositoryParser (`parse_repository` in `repository.py`)

**Graph layer:** `GraphBuilder`, `GraphResult`, `CycleDetector`, `AlgorithmEngine`, `ScoringResult`

**Pipeline:** `AnalysisPipeline` orchestrates parse → graph → cycles → scores. `GraphBuilder` currently reads only `resolved_deps`; other `FileAnalysis` fields (`classes`, `functions`, `imports`, `external_deps`, `line_count`, `has_syntax_error`) are preserved for V2 graph builders without reparsing.

Full rationale: [Design Decisions](docs/learn.md#design-decisions) · Roadmap: [Future Scope](docs/learn.md#future-scope) · Study guide: [docs/learn.md](docs/learn.md)

## Tech Stack

### Backend

* Python 3.11+
* FastAPI
* PostgreSQL
* SQLAlchemy
* NetworkX

### Frontend

* React
* Vite
* Cytoscape.js

### Infrastructure

* Docker
* Docker Compose

---

## Project Structure

```text
ripple/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app (health check)
│   │   ├── parser/
│   │   │   ├── models.py        # FileAnalysis, ImportInfo, …
│   │   │   ├── ast_parser.py    # ASTParser (single-file parsing)
│   │   │   ├── dependencies.py  # resolved vs external classification
│   │   │   ├── repository.py    # walk repo, parse_repository()
│   │   │   └── cli.py           # terminal output
│   │   ├── graph/
│   │   │   ├── models.py        # GraphResult
│   │   │   └── builder.py       # GraphBuilder
│   │   └── pipeline/
│   │       ├── pipeline.py      # AnalysisPipeline (parse → graph → cycles → scores)
│   │       ├── serialize.py     # PipelineResult → JSON
│   │       └── __main__.py      # python -m app.pipeline [--json PATH]
│   └── tests/
│       ├── sample_file.py       # single file to try the parser on
│       ├── test_parser.py       # parser tests (11)
│       ├── test_graph.py        # graph builder tests (9)
│       ├── test_pipeline.py     # pipeline tests (9)
│       ├── test_api.py          # API tests (stub)
│       ├── algorithms/
│       │   ├── test_cycles.py   # cycle detection (8)
│       │   └── test_scoring.py  # PageRank / criticality (12)
│       └── fixtures/
│           └── mini_repo/       # cyclic fixture (models ↔ utils)
├── frontend/
├── docs/
│   ├── learn.md                 # architecture, design decisions, study guide
│   ├── Architecture.md          # full system architecture document
│   └── Roadmap.md
└── docker-compose.yml
```

---

## Prerequisites

* Docker & Docker Compose (for full stack)
* Python 3.11+ (local backend / parser development)
* Node.js 20+ (local frontend development)

---

## Running with Docker

From the project root:

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Backend  | http://localhost:8000 |
| Frontend | http://localhost:5173 |

Health check: `GET http://localhost:8000/health` → `{"status": "ok"}`

---

## Parser CLI

Run from `backend/`:

```bash
cd backend
source .venv/bin/activate   # if using a venv
pip install -r requirements.txt

# single file
python -m app.parser.cli tests/sample_file.py

# whole project (resolved vs external deps) — use project root, not a subpackage
python -m app.parser.cli tests/fixtures/mini_repo
python -m app.parser.cli .                          # backend/ as root (paths like app/parser/…)

# one file from repo context
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
```

**Important:** use `python -m app.parser.cli` from `backend/`, not `python tests/...`, or Python won't find the `app` package. (`python -m app.parser.ast_parser` is a backward-compatible alias.)

### Analysis root convention

Always pass the **project root** (the directory that should own all relative file paths), not a package subfolder.

| Root you pass | Paths in `project_files` | `from app.parser.models import …` |
|---------------|--------------------------|-----------------------------------|
| `backend/` (`.`) | `app/parser/models.py` | Resolves ✓ |
| repo root (`..`) | `backend/app/parser/models.py` | Resolves via suffix match ✓ |
| `app/parser/` | `models.py` only | **Does not resolve** — shows as `external_deps: app` |

Imports use package names (`app.parser.models`); resolution maps those to **paths relative to the root you gave**. Pointing at `./app/parser` indexes only `models.py`, which does not match `app/parser/models.py`.

This is intentional: production analysis (zip / clone / pipeline) always runs from the uploaded project root. Do not pass a subpackage folder and expect internal edges.

Detail: [docs/learn.md — Analysis root convention](docs/learn.md#analysis-root-convention).

### Single file (no repo context)

* `resolved_deps` — empty
* `external_deps` — top-level packages from imports (`os`, `numpy`, …)

### Whole project (correct root)

* `resolved_deps` — paths to other project files (e.g. `myapp/utils.py`)
* `external_deps` — stdlib and third-party packages (`os`, `requests`, …)

Example for `tests/fixtures/mini_repo/myapp/auth.py`:

```
resolved_deps: myapp/models.py, myapp/utils.py
external_deps: os, requests
```

### Python API

```python
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
print(analyses["myapp/auth.py"].resolved_deps)
```

For one file with manual control:

```python
from app.parser.ast_parser import ASTParser

parser = ASTParser(project_files={"myapp/utils.py"})
analysis = parser.parse_file("myapp/auth.py", content)
```

For design rationale and AST details, see [docs/learn.md](docs/learn.md).

### Graph builder

Turn parsed files into a dependency graph:

```python
from app.graph import GraphBuilder
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
result = GraphBuilder().build(analyses)

print(result.nodes)   # sorted file paths
print(result.edges)   # (importer, imported) pairs
```

Edges run **importer → imported** — e.g. `("myapp/auth.py", "myapp/models.py")` means `auth.py` imports `models.py`. External packages and out-of-repo paths are not graph nodes.

### Pipeline

Run parse → graph → cycles → scores in one step:

```bash
python -m app.pipeline tests/fixtures/mini_repo
# sections: Summary | Dependency edges | Circular dependencies | Top critical files
python -m app.pipeline tests/fixtures/mini_repo --json result.json
python -m app.pipeline tests/fixtures/mini_repo --json result.json --no-files
```

```python
from app.pipeline import AnalysisPipeline

result = AnalysisPipeline().run("tests/fixtures/mini_repo")
result.analyses   # dict[str, FileAnalysis]
result.graph      # GraphResult (nodes + edges)
result.cycles     # CircularDependencyResult
result.scores     # ScoringResult (sorted by criticality)
result.scores.top(10)  # highest-criticality NodeScore list
# JSON: metadata, summary, statistics, graph, analysis (scores), files
# Top N in JSON: analysis.scores.slice(0, N) — no separate top_critical field
result.write_json("result.json")
```
# NodeScore fields:
#   pagerank     — how depended-on (importance flows to shared modules)
#   betweenness  — bridge / bottleneck on paths between other files
#   criticality  — 0.6 * norm(PR) + 0.4 * norm(BT); relative change-risk
#   in_degree    — # of project files that import this file
#   out_degree   — # of project files this file imports
```

Study guide: [What each property means](docs/learn.md#1-what-each-property-means) · [Criticality Scoring](docs/learn.md#phase-1-week-2--criticality-scoring) · [Pipeline](docs/learn.md#phase-1--analysis-pipeline)

---

## Backend Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Tests

From `backend/` (requires `PYTHONPATH=.` so Python finds the `app` package):

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v                    # all 63 tests (-v = verbose, one line per test)
PYTHONPATH=. pytest tests/test_parser.py -v      # parser (11)
PYTHONPATH=. pytest tests/test_graph.py -v       # graph builder (9)
PYTHONPATH=. pytest tests/test_pipeline.py -v    # pipeline (9)
PYTHONPATH=. pytest tests/test_serialize.py -v   # JSON export (14)
PYTHONPATH=. pytest tests/algorithms/ -v         # cycles (8) + scoring (12)
```

| Suite | Tests | Covers |
|-------|-------|--------|
| **`test_parser.py`** | 11 | Import forms (parametrized), `__future__` / syntax edge cases, `mini_repo` integration |
| **`test_graph.py`** | 9 | Empty/single-node graphs; dependency edges; dedup; missing deps; cycles; self-loops; dict-key semantics; syntax-error files |
| **`test_pipeline.py`** | 9 | End-to-end parse → graph → cycles → scores; `test_small_cycle`; `mini_repo` integration |
| **`test_serialize.py`** | 14 | metadata, summary, statistics, graph, analysis, files |
| **`test_cycles.py`** | 8 | `CycleDetector`: empty/acyclic graphs, simple cycles, self-loops, disjoint cycles, normalization |
| **`test_scoring.py`** | 12 | `AlgorithmEngine`: normalize, PageRank fan-in, betweenness bridge, criticality weights, `top()` |

**Fixture:** `tests/fixtures/mini_repo/` — shared by parser and pipeline; intentionally cyclic (`models` ↔ `utils`) so `python -m app.pipeline tests/fixtures/mini_repo` reports one cycle and top critical files.

**More detail:** [Cycle Detection](docs/learn.md#phase-1-week-2--cycle-detection) · [Criticality Scoring](docs/learn.md#phase-1-week-2--criticality-scoring) · [Testing overview](docs/learn.md#testing-overview)

---

## Frontend Development

```bash
cd frontend
npm install
npm run dev
```

---

## Current Status

### Phase 0 – Infrastructure

* [x] Docker setup
* [x] PostgreSQL container
* [x] Backend container
* [x] Frontend container

### Phase 1 – Parser & Graph (in progress)

* [x] Modular parser package (`models`, `ast_parser`, `dependencies`, `repository`, `cli`)
* [x] `ASTParser` + `FileAnalysis` dataclasses
* [x] Absolute, from, relative, and aliased imports
* [x] Classes (name, bases, methods)
* [x] Module-level functions vs class methods (separate lists)
* [x] `resolved_deps` / `external_deps` with suffix path matching
* [x] `parse_repository()` — walk repo, parse all files
* [x] CLI: `python -m app.parser.cli <file-or-repo>`
* [x] Unit tests (`tests/test_parser.py`, 11 cases) + `tests/fixtures/mini_repo`
* [x] `CycleDetector` + tests (`tests/algorithms/test_cycles.py`, 8 cases)
* [x] `GraphBuilder` + `GraphResult` — nodes and directed import edges
* [x] Graph unit tests (`tests/test_graph.py`, 9 cases)
* [x] `AnalysisPipeline` — parser → graph → cycles → scores
* [x] Pipeline tests (`tests/test_pipeline.py`, 9 cases)
* [x] `AlgorithmEngine` — PageRank, betweenness, criticality (`test_scoring.py`, 12 cases)
* [x] JSON export — `serialize.py`, `--json PATH` (`test_serialize.py`)
* [ ] `IngestionService` (zip upload, filters)
* [ ] Pipeline stage metrics and benchmark CLI

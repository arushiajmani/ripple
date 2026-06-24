# Ripple

Ripple is a code dependency analysis platform that parses Python repositories, constructs dependency graphs, and identifies critical files, architectural bottlenecks, and change impact paths.

## Features

### Shipped

* **AST parser** — extract imports, classes, functions, and methods from a `.py` file
* **Repo batch parsing** — walk a directory and parse all `.py` files via `parse_repository()`
* **Dependency classification** — internal (`resolved_deps`) vs stdlib/third-party (`external_deps`) when project context is provided
* **Graph builder** — assemble `dict[str, FileAnalysis]` into a `GraphResult` (nodes + directed import edges)
* **CLI** — inspect single-file or whole-repo output from the terminal

### Planned

* Zip upload ingestion (`IngestionService`)
* Graph algorithms — PageRank, betweenness, cycle detection, criticality scores (`AlgorithmEngine`)
* Impact analysis for proposed changes
* Interactive graph visualization
* REST API for repository analysis

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
│   │   └── graph/
│   │       ├── models.py        # GraphResult
│   │       └── builder.py       # GraphBuilder
│   └── tests/
│       ├── sample_file.py       # single file to try the parser on
│       ├── test_parser.py       # parser unit tests
│       ├── test_graph.py        # graph builder unit tests
│       └── fixtures/
│           └── mini_repo/       # tiny repo for resolved vs external deps
├── frontend/
├── docs/
│   ├── learn.md                 # code study guide (parser + graph builder)
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

# whole repo (resolved vs external deps)
python -m app.parser.cli tests/fixtures/mini_repo

# one file from repo context
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
```

**Important:** use `python -m app.parser.cli` from `backend/`, not `python tests/...`, or Python won't find the `app` package. (`python -m app.parser.ast_parser` is a backward-compatible alias.)

### Single file (no repo context)

* `resolved_deps` — empty
* `external_deps` — top-level packages from imports (`os`, `numpy`, …)

### Whole repo

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

From `backend/`:

```bash
PYTHONPATH=. pytest tests/ -v
```

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
* [x] Unit tests (`tests/test_parser.py`) + `tests/fixtures/mini_repo`
* [x] `GraphBuilder` + `GraphResult` — nodes and directed import edges
* [x] Graph unit tests (`tests/test_graph.py`, 9 cases)
* [ ] `AlgorithmEngine` (PageRank, cycles, criticality)
* [ ] `IngestionService` (zip upload, filters)

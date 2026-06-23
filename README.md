# Ripple

Ripple is a code dependency analysis platform that parses Python repositories, constructs dependency graphs, and identifies critical files, architectural bottlenecks, and change impact paths.

## Features

### Shipped

* **AST parser** — extract imports, classes, functions, and methods from a `.py` file
* **Dependency hints** — classify imports as internal (`resolved_deps`) vs stdlib/third-party (`external_deps`) when project context is provided
* **CLI** — inspect parser output from the terminal

### Planned

* Full-repo ingestion and batch parsing
* File-level dependency graphs (NetworkX)
* Cycle detection and criticality scores (PageRank, centrality)
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
│   │   └── parser/
│   │       ├── models.py        # FileAnalysis, ImportInfo, …
│   │       ├── ast_parser.py    # ASTParser (single-file parsing)
│   │       ├── dependencies.py  # resolved vs external classification
│   │       ├── repository.py    # walk repo, parse_repository()
│   │       └── cli.py           # terminal output
│   └── tests/
│       └── sample_file.py       # small file to try the parser on
├── frontend/
├── docs/
│   ├── learn.md                 # code study guide (read this to understand the parser)
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

The parser is the first shipped component. Run it from `backend/`:

```bash
cd backend
source .venv/bin/activate   # if using a venv
pip install -r requirements.txt

python -m app.parser.cli tests/sample_file.py
```

**Important:** use `python -m app.parser.cli` from `backend/`, not `python tests/...`, or Python won't find the `app` package. (`python -m app.parser.ast_parser` is a backward-compatible alias.)

### What you get (single file, no repo context)

* `imports` — structured import list with human-readable display
* `resolved_deps` — empty (no project context to resolve against)
* `external_deps` — top-level packages seen in imports (`os`, `numpy`, …)
* `classes` — name, bases, nested method names
* `functions` — module-level functions only

### Repo-aware parsing (manual for now)

Pass `project_files` when you know all `.py` paths in the repo. Internal imports resolve to real files; everything else stays external:

```python
from pathlib import Path
from app.parser.ast_parser import ASTParser
from app.parser.repository import parse_repository

root = Path("path/to/repo")
project_files = {p.relative_to(root).as_posix() for p in root.rglob("*.py")}

parser = ASTParser(project_files=project_files)
content = (root / "myapp/auth.py").read_text()
analysis = parser.parse_file("myapp/auth.py", content)

print(analysis.resolved_deps)   # e.g. ['myapp/utils.py']
print(analysis.external_deps)   # e.g. ['os', 'requests']
```

There is no `parse_repo` command yet — that comes with `IngestionService` + `GraphBuilder` in a later phase.

For design rationale and AST details, see [docs/learn.md](docs/learn.md).

---

## Backend Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
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

### Phase 1 – AST Parser (in progress)

* [x] `ASTParser` + `FileAnalysis` dataclasses
* [x] Absolute, from, relative, and aliased imports
* [x] Classes (name, bases, methods)
* [x] Module-level functions vs class methods (separate lists)
* [x] `resolved_deps` / `external_deps` when `project_files` is set
* [x] CLI: `python -m app.parser.cli <file-or-repo>`
* [x] Unit tests (`tests/test_parser.py`)
* [ ] Repo ingestion + batch parsing
* [ ] `GraphBuilder`

# Ripple — Project Roadmap

> **Reorganized.** See [product/README.md](product/README.md) for the consolidated roadmap, requirements summary, and interview guide.

*Archive below — full original week-by-week roadmap.*

---

## How To Read This Roadmap

Each phase has a clear **entry condition** (what must be true before starting it) and **exit condition** (what must be true before moving to the next phase). Do not move forward until the exit condition is met. This discipline is what separates projects that ship from projects that stall.

The phases are sequenced so that the hardest, most important work happens first — when your energy is highest and before any UI decisions constrain your thinking.

---

## Phase 0 — Project Setup

**Duration:** 2–3 days  
**Entry condition:** None  
**Exit condition:** Empty project runs with one command, all tools verified working

### Tasks

- [x] Create GitHub repository, initialize with `.gitignore` for Python and Node
- [x] Set up project folder structure (see Architecture doc)
- [x] Create `docker-compose.yml` with three services: `backend`, `db`, `frontend`
- [x] Verify PostgreSQL container starts and is reachable from backend container
- [x] Create Python virtual environment, `requirements.txt` with initial dependencies
- [x] Create FastAPI app with a single `GET /health` endpoint returning `{ "status": "ok" }`
- [x] Create React app with Vite, verify it loads in browser
- [x] Write a `README.md` stub with setup instructions

### Deliverable

Running `docker-compose up` starts all three services. `GET /health` returns 200. React app loads at `localhost:3000`.

### Why This Phase Matters

Infrastructure problems discovered in Week 5 are catastrophic. Infrastructure problems discovered in Day 2 are a minor inconvenience. Always validate your foundation before building on it.

---

## Phase 1 — Analysis Engine (The Core)

**Duration:** Weeks 1–3  
**Entry condition:** Phase 0 complete  
**Exit condition:** CLI script analyzes a real Python project and produces correct JSON output

This is the most important phase. Everything else is presentation. If the analysis is wrong, the entire project is wrong. Take your time here.

---

### Week 1 — AST Parser

**Goal:** Parse a single Python file and correctly extract all import relationships.

#### Tasks

- [x] Implement `ASTParser` class in `backend/app/parser/ast_parser.py`
- [x] Handle absolute imports: `import os`, `import numpy as np`
- [x] Handle from-imports: `from os import path`, `from os.path import join`
- [x] Handle relative imports: `from . import utils`, `from .utils import helper`
- [x] Handle aliased imports: `import pandas as pd`, `from collections import defaultdict as dd`
- [x] Extract class definitions (name, base classes)
- [x] Extract function/method definitions (name, parent class if any)
- [x] Return structured `FileAnalysis` dataclass with all extracted information
- [x] Write unit tests covering all import forms above — `tests/test_parser.py`
- [ ] Test against at least 5 real Python files from different open source projects

#### Milestone Check

Run `python -m app.parser.cli path/to/any_file.py` and see correctly extracted imports, classes, and functions printed to terminal. For `resolved_deps`, pass the **project root** (e.g. `python -m app.parser.cli .` from `backend/`), not a package subfolder. Verify with `PYTHONPATH=. pytest tests/test_parser.py -v` (11 cases). **pytest help:** [learn.md — Introduction to pytest](./learn.md#introduction-to-pytest). **Root convention:** [learn.md — Analysis root convention](./learn.md#analysis-root-convention).

#### Common Pitfalls To Avoid

- `from __future__ import annotations` — handle gracefully, don't crash
- Files with syntax errors — catch `SyntaxError`, log the file, skip it, don't crash the whole analysis
- Encoding issues — open files with `encoding='utf-8', errors='ignore'`
- `__init__.py` files — parse them, they often contain important re-exports
- **Wrong analysis root** — `python -m app.parser.cli ./app/parser` indexes `models.py` only; imports like `app.parser.models` then appear as `external_deps: app`. Always pass the project root (`.`, fixture root, or uploaded zip root)

---

### Week 2 — Graph Builder + Algorithms

**Goal:** Assemble parsed files into a graph and compute criticality scores.

#### Tasks

- [x] Implement `GraphBuilder` class in `backend/app/graph/builder.py`
- [x] Resolve relative imports to absolute file paths using folder structure
- [x] Handle unresolvable imports gracefully (external packages like `requests`, `numpy` — skip or add as external nodes)
- [x] Build `nx.DiGraph` where nodes are file paths and edges are import relationships — via `GraphAdapter` (single conversion per pipeline run)
- [x] Implement `AlgorithmEngine` class in `backend/app/graph/algorithms/scoring.py`
- [x] Compute PageRank scores (`nx.pagerank`, alpha=0.85)
- [x] Compute Betweenness Centrality (`nx.betweenness_centrality`)
- [x] Compute composite criticality score: `0.6 * normalized_pagerank + 0.4 * normalized_betweenness`
- [x] Detect circular dependencies (`nx.simple_cycles`) — `CycleDetector` in `graph/algorithms/cycles.py`, wired into `AnalysisPipeline` as `PipelineResult.cycles`
- [x] Compute in-degree and out-degree for each node — on `NodeScore`
- [x] Write unit tests using small synthetic graphs (5–10 nodes) with known correct answers — `test_graph.py`, `test_cycles.py`, `test_scoring.py`, `test_impact.py`, `test_pipeline.py`
- [x] Serialize graph results to JSON — `metadata` / `summary` / `statistics` / `graph` / `analysis` / `files`

#### Milestone Check

Graph structure, cycles, and criticality scores:

```bash
PYTHONPATH=. pytest tests/test_graph.py tests/algorithms/ tests/test_pipeline.py -v
python -m app.pipeline tests/fixtures/mini_repo --json result.json
```

**Study guides:** [Cycle Detection](./learn.md#phase-1-week-2--cycle-detection) · [Criticality Scoring](./learn.md#phase-1-week-2--criticality-scoring) · [Impact Analysis](./learn.md#phase-1-week-2--impact-analysis) · [Pipeline](./learn.md#phase-1--analysis-pipeline).

#### Understanding The Algorithms (For Interviews)

Full property glossary: [learn.md — What each property means](./learn.md#1-what-each-property-means).

**PageRank:** Iteratively propagates importance along edges (importer → imported). A file is important if many important files import it. Raw scores sum to ~1.0. The `alpha=0.85` damping factor prevents sink nodes from absorbing all weight.

**Betweenness Centrality:** For every pair of nodes (A, B), find the shortest path between them. Count how many of those paths pass through node X. High betweenness = architectural bottleneck / bridge node.

**Criticality:** `0.6 * norm(pagerank) + 0.4 * norm(betweenness)` after min-max normalize. Relative change-risk rank within one repo; used for “top critical files.”

**in_degree / out_degree:** Direct importers of this file / direct imports from this file (in-repo only).

**Why normalize before combining:** PageRank and betweenness use different scales. PageRank sums to 1.0; betweenness can be larger on big graphs. Without normalization, betweenness would dominate regardless of the 0.6 / 0.4 weights.

---

### Week 3 — Ingestion + End-to-End Integration

**Goal:** Accept a zip file upload **or** a public GitHub URL, run the full pipeline, produce a result JSON.

#### Tasks

- [x] Implement `IngestionService` in `backend/app/ingestion/` (zip + GitHub modules)
- [x] Accept zip file, extract to temp directory (`/tmp/ripple/{job_id}/`)
- [x] Accept GitHub URL — validate, `git ls-remote`, shallow clone to same job-dir layout
- [x] Walk directory tree, collect all `.py` files — via `parse_repository()` / `collect_python_files()`
- [x] Filter out virtual environments (`venv/`, `.venv/`, `env/`), build artifacts (`__pycache__/`, `*.pyc`), test files (optional — include for now, filter later) — via `SKIP_DIRS` in `parser/models.py`
- [x] Wire `IngestionService` → `AnalysisPipeline` in API layer — `POST /api/analyze` accepts `file` or `github_url`
- [x] Instrument every pipeline stage with timing: `file_discovery`, `ast_parsing` (total + per-file average), `import_resolution`, `graph_construction`, `pagerank_computation`, `betweenness_computation`, `score_normalization` — timings on `PipelineResult.metrics`
- [x] Add benchmark CLI: `python -m app.benchmark --repo path/to/project` — runs the pipeline and prints a formatted timing breakdown to stdout (for performance testing on large repos)
- [x] Output complete result as a JSON file — `python -m app.pipeline <repo> --json result.json`
- [x] Clean up temp directory after analysis
- [ ] Test end-to-end on 3 different real Python projects of varying sizes

#### Milestone Check

```bash
# Automated ingestion tests
cd backend && source .venv/bin/activate
PYTHONPATH=. pytest tests/test_ingestion.py -v          # zip (8)
PYTHONPATH=. pytest tests/test_github_ingestion.py -v   # GitHub (17)
PYTHONPATH=. pytest tests/test_api.py -v                 # HTTP API (31)

# Manual: local directory → pipeline → JSON
python -m app.pipeline tests/fixtures/mini_repo --json result.json

# Manual: API — zip or GitHub (server: uvicorn app.main:app --reload)
curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool

curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pypa/sampleproject" | python3 -m json.tool

# Impact (after analyze — use repo_id from response)
REPO_ID=$(curl -s -X POST http://localhost:8000/api/repos/analyze \
  -F "file=@tests/fixtures/mini_repo.zip" | python3 -c "import sys,json; print(json.load(sys.stdin)['repo_id'])")
curl -s "http://localhost:8000/api/repos/${REPO_ID}/impact?file=mini_repo/myapp/models.py" | python3 -m json.tool

# Benchmark: per-stage timing breakdown
python -m app.benchmark --repo tests/fixtures/mini_repo
```

The JSON output is correct, complete, and makes intuitive sense for a project you understand.

#### The Import Resolution Problem (Explained)

When a file contains `from .utils import helper`, the `.` means "same package as this file." To resolve this to an actual file path, you need to know:

1. The path of the current file
2. The root of the Python package (where `__init__.py` lives)

Resolution algorithm:

```
current file:  myproject/auth/session.py
import:        from .utils import helper
resolved:      myproject/auth/utils.py  (same directory + utils.py)
```

For `from ..config import settings`:

```
current file:  myproject/auth/session.py
import:        from ..config import settings
resolved:      myproject/config.py  (one level up + config.py)
```

Unresolvable imports (third-party packages like `import requests`) should be tracked separately as "external dependencies" — they're useful metadata but shouldn't be graph nodes since you don't have their source.

---

## Phase 2 — API Layer

**Duration:** Weeks 4–5  
**Entry condition:** Phase 1 complete — `AnalysisPipeline` produces correct JSON for any Python zip  
**Exit condition:** All API endpoints functional and testable via Swagger UI at `/docs`

---
### Week 4 — Database + Core Endpoints

#### Tasks

- [x] Set up Alembic for database migrations (`backend/alembic/`, `alembic.ini`, initial revision `63207e50c596_initial_schema`)
- [x] Implement all tables from the schema in the SRS — SQLAlchemy ORM in `app/db/models.py` (`repositories`, `analysis_jobs`, `files`, `dependencies`, `node_scores`, `cycles`, `cycle_members`, `analysis_statistics`); schema unit tests in `tests/test_db_schema.py`
- [ ] Implement `POST /api/analyze` (full) — async 202, job record in PostgreSQL, background analysis *(sync zip + GitHub wired in Week 3 — see `app/api/routes.py`; ORM + migration ready, write path not wired yet)*
- [ ] Implement `GET /api/status/{repo_id}` — returns current job status; includes `metrics` array (stage durations) once analysis is complete
- [ ] Implement background task that runs `AnalysisPipeline` and writes results to PostgreSQL
- [ ] Implement idempotency — same zip uploaded twice returns existing result (hash the file content)
- [ ] Handle failures gracefully — if analysis crashes, set status to `"failed"` with error message

#### Milestone Check

**Schema (shipped):** from project root, with Postgres up:

```bash
# 1. Start database
docker compose up -d db

# 2. Apply migrations (backend venv)
cd backend && source .venv/bin/activate
alembic upgrade head

# 3. Verify — list tables (9 total: 8 SRS + alembic_version)
cd ..   # back to project root if needed
docker compose exec db psql -U ripple -d ripple -c '\dt'

# 4. Confirm migration revision
docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"
# Expected version_num: 63207e50c596
```

**Interactive inspection** (optional):

```bash
docker compose exec db psql -U ripple -d ripple
```

Then inside `psql`: `\dt`, `\d alembic_version`, `SELECT * FROM files;` (end SQL with `;`), `\q` to exit.

If the prompt shows `ripple-#` instead of `ripple=#`, PostgreSQL is waiting for you to finish the previous statement — add the missing `;` or press **Ctrl+C**.

**Async analyze (remaining):** Upload a zip via `curl` or Swagger UI. Poll status endpoint until `"complete"`. Verify results are stored in PostgreSQL by querying the database directly.

---

### Week 5 — Graph Endpoints *(repo-centric API Phases 1 & 2 shipped)*

**Implementation spec:** [product/repo-centric-api-plan.md](./product/repo-centric-api-plan.md)

#### Tasks

- [x] Implement `ImpactAnalyzer` in `backend/app/graph/algorithms/impact.py` — on-demand blast radius (direct + transitive dependents, hop-distance layers)
- [x] Implement `AnalysisStore` — in-memory `PipelineResult` cache keyed by `repo_id`
- [x] Implement `GET /api/repos/{repo_id}/impact?file=...` — requires `repositories.id` (standalone `GET /api/impact/{repo_id}` removed as duplicate)
- [x] PostgreSQL persist on analyze — `persist_pipeline_result()` + `load_pipeline_result()` ([persistence.md](./backend/persistence.md))
- [x] **Repo-centric API Phase 1** per [repo-centric-api-plan.md](./product/repo-centric-api-plan.md):
  - [x] `persist_pipeline_result()` → `PersistResult(repository_id, job_id)`
  - [x] `get_latest_completed_job(repo_id)` query helper
  - [x] `POST /api/repos/analyze` — slim `{ repo_id, job_id, status }`
  - [x] `GET /api/repos` — list repositories
  - [x] `GET /api/repos/{repo_id}` — latest job summary
- [x] **Repo-centric API Phase 2** — [repo-centric-api-plan.md](./product/repo-centric-api-plan.md):
  - [x] `GET /api/repos/{repo_id}/graph`, `/scores`, `/impact` (latest job)
- [ ] **Job APIs Phase 3** — [api-resources.md](./architecture/api-resources.md):
  - [ ] `GET /api/jobs/{job_id}`, job sub-routes
  - [ ] Optional `GET /api/repos/{repo_id}/jobs` (history)
- [ ] Add proper HTTP error responses (404 for unknown repo_id, 422 for invalid inputs)
- [ ] Add CORS configuration so React frontend can call the API
- [ ] Write integration tests for all endpoints using FastAPI's `TestClient` *(partial: `tests/test_api.py` — 31 cases covering analyze, repos, graph, scores, impact)*

**Phase 3 (not Phase 2):** `GET /jobs`, `GET /jobs/{job_id}`, `GET /api/repos/{repo_id}/jobs`

#### Milestone Check

Impact endpoint (shipped):

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload &
REPO_ID=$(curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@tests/fixtures/mini_repo.zip" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['repo_id'])")
curl -s "http://localhost:8000/api/repos/${REPO_ID}/impact?file=mini_repo/myapp/models.py" | python3 -m json.tool
```

Repo-centric Phases 1 & 2 shipped. Remaining Week 5: job APIs (Phase 3), CORS, full Swagger coverage.

#### The Impact Analysis Algorithm (Explained)

**Shipped:** `ImpactAnalyzer` in `backend/app/graph/algorithms/impact.py`. Study guide: [learn.md — Impact Analysis](./learn.md#phase-1-week-2--impact-analysis).

"What breaks if I change file X?" means: find all files that directly or transitively import X.

In graph terms: find all **predecessors** (reverse reachability). Edges are importer → imported.

```python
# In NetworkX (ImpactAnalyzer):
direct = sorted(digraph.predecessors(target_file))
indirect = sorted(nx.ancestors(digraph, target_file) - set(direct))

# Hop-distance layers (for concentric UI):
rev = digraph.reverse(copy=False)
distances = nx.single_source_shortest_path_length(rev, target_file)
```

Direct dependents = immediate predecessors. Indirect dependents = ancestors minus direct. Each file appears in exactly one layer by hop distance. The target's existing `NodeScore` is looked up from `ScoringResult` — not recomputed.

**Tests:**

```bash
PYTHONPATH=. pytest tests/algorithms/test_impact.py -v
PYTHONPATH=. pytest tests/test_api.py -k impact -v
```

---

## Phase 3 — Frontend

**Duration:** Weeks 6–8  
**Entry condition:** Phase 2 complete — all API endpoints functional  
**Exit condition:** Project is demo-ready and portfolio-publishable

---

### Week 6 — Graph Visualization

#### Tasks

- [x] Set up React project with Vite, install Cytoscape.js and react-cytoscapejs — Vite scaffold only; Cytoscape not installed
- [ ] Create `GraphCanvas` component that accepts nodes and edges as props
- [ ] Fetch graph data from `GET /api/graph/{repo_id}` on page load
- [ ] Render nodes with color encoding: red (criticality > 0.7), orange (> 0.4), green (< 0.4)
- [ ] Render node size proportional to PageRank score
- [ ] Apply force-directed layout (`cose` layout in Cytoscape)
- [ ] Enable zoom, pan, fit-to-screen controls
- [ ] Show loading state while graph data is fetching

#### Milestone Check

Real repo graph renders correctly in browser. Nodes are colored and sized by criticality. Graph is zoomable and pannable. High-criticality nodes are visually obvious without reading labels.

---

### Week 7 — Interactivity + Sidebar

#### Tasks

- [ ] Implement node click handler — selected node gets highlighted border
- [ ] On node click, call `GET /api/repos/{repo_id}/impact?file={selected_file}`
- [ ] Highlight direct dependents in orange, transitive dependents in light red, unaffected nodes dimmed
- [ ] Build `Sidebar` component with three panels:
  - `CriticalFilesList` — top 10 files ranked by criticality score with score displayed
  - `NodeDetail` — shown when node is selected: file path, scores, in/out degree
  - `ImpactPanel` — "X files depend on this file" with list of dependents
- [ ] Build `CycleWarnings` panel — list all detected circular dependency cycles
- [ ] Add "clear selection" behavior when clicking empty canvas space

#### Milestone Check

Full interaction flow works: click a node → sidebar updates → dependents highlight on graph → clicking away clears selection. Cycle warnings show correctly if cycles exist.

---

### Week 8 — Input Flow + Polish + Documentation

#### Tasks

- [ ] Build `HomePage` with zip file upload form, GitHub URL input, and recent analyses list
- [ ] Implement polling logic: after upload, poll `GET /api/status/{repo_id}` every 2 seconds until complete
- [ ] Show progress indicator during analysis ("Parsing files... Building graph... Computing scores...")
- [ ] Build `AnalysisPage` that loads when status becomes `"complete"`
- [ ] Add error states: invalid zip, analysis failed, network error
- [x] Write `README.md` with: project description, architecture overview, setup instructions, screenshots — description, architecture, and setup done; screenshots pending
- [ ] Record a 2-minute demo video showing the full flow
- [ ] (Optional) Deploy: Railway or Render for backend + PostgreSQL, Vercel for frontend

#### Milestone Check

A person who has never seen the project can clone the repo, run `docker-compose up`, and successfully analyze a Python project within 5 minutes. README is clear enough that no verbal explanation is needed.

---

## Version Ladder Summary

### MVP — What's Described Above

**Timeline:** 8 weeks  
**Resume claim:** "Built a static analysis tool that parses Python repositories into directed dependency graphs and applies PageRank and Betweenness Centrality to identify architecturally critical files and compute change impact, with an interactive React visualization."

### v2 — AI Explanation Layer

**Timeline:** 3–4 weeks after MVP  
**What to add:**

- `POST /api/explain/{repo_id}` endpoint
- Graph traversal to extract relevant context for a user's question
- LLM call with structured graph context as input, natural language explanation as output
- Chat panel in the frontend sidebar

**Resume addition:** "Extended with an LLM layer that generates architectural explanations grounded in graph-traversal context rather than raw code retrieval, producing structured, verifiable answers."

### v3 — Behavioral Coupling (Stretch Goal)

**Timeline:** 4–6 weeks after v2  
**What to add:**

- Git history analysis using `gitpython`
- Co-change coupling matrix: files that change together frequently
- New edge type in graph: "behavioral coupling" vs "structural coupling"
- Surface files with high behavioral coupling but low structural coupling as "hidden dependencies"

**Resume addition:** "Implemented behavioral coupling analysis by correlating git co-change history with structural dependency graphs, identifying hidden architectural dependencies not visible in import relationships."

---

## Risk Register


| Risk                                                  | Likelihood | Impact | Mitigation                                                                     |
| ----------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------ |
| Import resolution breaks on complex projects          | High       | High   | Handle failures gracefully, mark unresolved imports, don't crash               |
| Phase 1 takes longer than 3 weeks                     | Medium     | High   | Descope to file-level only (no function-level nodes), cut test coverage target |
| Cytoscape rendering slow on large graphs (500+ nodes) | Medium     | Medium | Add node filtering by criticality threshold, only render top N nodes           |
| PostgreSQL migration issues slow Phase 2              | Low        | Medium | Keep schema simple, use Alembic from day one                                   |
| Scope creep back into v2/v3 features                  | High       | Medium | Refer back to this document, defer all non-MVP features explicitly             |
| Large repo performance in benchmark CLI               | Medium     | High   | Use `app.benchmark` to profile per-stage timings; parallelize `ast_parsing` before optimizing algorithms |


---

## Weekly Check-In Questions

Ask yourself these at the end of every week:

1. Did I meet this week's milestone? If not, why?
2. Am I building something that's in scope for MVP, or am I adding features?
3. Is my current blocker a technical problem or an avoidance problem?
4. What's the one thing that, if I don't do it this week, will block all future weeks?

---

*Roadmap version: 1.2 | Project: Ripple | Last updated: July 2026*
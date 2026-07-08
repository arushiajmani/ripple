# Ripple — Software Requirements Specification & Project Plan

> **Reorganized.** See [product/README.md](product/README.md), [reference/](reference/), and [backend/](backend/).

*Archive below — full original SRS.*

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Project Vision](#2-project-vision)
3. [Scope Definition](#3-scope-definition)
4. [System Architecture](#4-system-architecture)
5. [Component Design](#5-component-design)
6. [Data Flow](#6-data-flow)
7. [Database Schema](#7-database-schema)
8. [API Design](#8-api-design)
9. [Frontend Design](#9-frontend-design)
10. [Functional Requirements](#10-functional-requirements)
11. [Non-Functional Requirements](#11-non-functional-requirements)
12. [Project Plan & Milestones](#12-project-plan--milestones)
13. [Version Ladder](#13-version-ladder)
14. [Interview Talking Points](#14-interview-talking-points)

---

## 1. Problem Statement

When a developer encounters an unfamiliar Python codebase, two questions take the most time to answer:

- **"Which files are the most critical to understand?"**
- **"What breaks if I change this file?"**

Today, answering these requires reading thousands of lines of code, asking senior engineers, or trial and error. This costs hours to days of productive time.

Ripple solves this by statically analyzing a Python repository, constructing a dependency graph, and applying graph algorithms to surface architectural intelligence — visually and instantly.

---

## 2. Project Vision

Ripple is a developer tool that transforms a Python repository into an interactive dependency graph, ranked by architectural criticality, with one-click impact analysis.

**It is not:**

- A code quality linter (that's SonarQube)
- A code search engine (that's Sourcegraph)
- A code chatbot (that's GitHub Copilot)

**It is:**

- A graph-theoretic architectural intelligence tool
- Focused on structure, not style
- Built on CS fundamentals: graph algorithms, static analysis, AST parsing

---

## 3. Scope Definition

### In Scope — MVP


| Feature                         | Description                                          |
| ------------------------------- | ---------------------------------------------------- |
| GitHub repo ingestion           | Clone any public Python repo by URL                  |
| Python AST parsing              | Extract files, classes, functions, imports           |
| Dependency graph construction   | Build directed graph of module dependencies          |
| Criticality scoring             | Rank files using PageRank and Betweenness Centrality |
| Circular dependency detection   | Identify strongly connected components               |
| Impact analysis                 | Click a node → see all files that depend on it       |
| Interactive graph visualization | Force-directed, zoomable, clickable graph            |
| Critical files sidebar          | Top 10 most critical files ranked with scores        |


### Out of Scope — MVP (Deferred to v2/v3)


| Feature                    | Reason Deferred                                    |
| -------------------------- | -------------------------------------------------- |
| AI/LLM chat interface      | Adds complexity before graph is validated          |
| Git history analysis       | Separate data source, separate pipeline            |
| Multi-language support     | Each language is a separate parser effort          |
| User authentication        | Unnecessary for a portfolio demo                   |
| Function-level graph nodes | File-level is sufficient and significantly simpler |
| Private repository support | Requires OAuth, deferred to v2                     |


---

## 4. System Architecture

### Architecture Style: Modular Monolith

**Why not Microservices?**
Microservices require service discovery, network communication between services, distributed tracing, and independent deployments. For a solo student project, this adds infrastructure overhead without any benefit. The codebase isn't large enough to justify team isolation boundaries.

**Why not a pure Monolith?**
A single Python script with no separation of concerns is hard to test, hard to extend, and not impressive to show in interviews.

**Why Modular Monolith?**
Each component (parser, graph engine, API, frontend) has a clear boundary and could theoretically become its own service later. You get the organizational clarity of microservices without the operational complexity. This is what most real-world startups actually do before scaling.

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                         │
│                   React + Cytoscape.js                      │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP (REST API)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Ingestion │  │    Analysis  │  │   Graph API      │   │
│  │   Module    │  │    Engine    │  │   Layer          │   │
│  │             │  │              │  │                  │   │
│  │ clone repo  │  │ ast parser   │  │ /api/analyze     │   │
│  │ validate    │  │ networkx     │  │ /api/graph/{id}  │   │
│  │ index files │  │ algorithms   │  │ /api/impact/{id} │   │
│  └──────┬──────┘  └──────┬───────┘  └──────────────────┘   │
│         │                │                                   │
│         └────────────────▼                                   │
│                  ┌───────────────┐                           │
│                  │  PostgreSQL   │                           │
│                  │  (graph cache │                           │
│                  │   + results)  │                           │
│                  └───────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   GitHub / Git Clone  │
              │   (external service)  │
              └───────────────────────┘
```

### Docker Composition

```
docker-compose.yml
├── frontend    (React app, port 3000)
├── backend     (FastAPI, port 8000)
└── db          (PostgreSQL, port 5432)
```

Docker is included because:

1. It makes setup a single command (`docker-compose up`) for anyone reviewing your portfolio
2. It isolates the Python environment and database cleanly
3. It's expected in professional environments and shows deployment awareness
4. It prevents "works on my machine" problems when showing the project

---

## 5. Component Design

### Component 1: Ingestion Module

**Responsibility:** Accept a zip upload or public GitHub URL, materialize the repository on disk, validate inputs, index all `.py` files. Return a `RepositoryHandle` whose `local_path` is the only handoff to the analysis pipeline.

**Key Design Decision — Where to clone/extract?**

- Clone/extract to disk (temp directory) → simple, fast, easy to read files
- Clone to memory → complex, unnecessary

Decision: Use a temp job directory (`/tmp/ripple/{job_id}/`). Clean up after analysis completes. Zip and GitHub paths are invisible to `AnalysisPipeline`.

**Shipped interface (`IngestionService`):**

- `ingest_zip` / `ingest_zip_bytes` — zip extraction with zip-slip protection
- `ingest_github` — URL validation, `git ls-remote`, shallow `git clone --depth 1`
- `cleanup` — remove job directory

**System Design Concept — Idempotency (planned):**
If the same URL is submitted twice, Ripple should return the cached result rather than recloning. This is achieved by hashing the URL to generate a deterministic `repo_id` and checking PostgreSQL before cloning. This is called **idempotent ingestion** and is a standard pattern in data pipelines.

---

### Component 2: Analysis Engine

**Responsibility:** Parse Python files into ASTs, extract relationships, build the dependency graph, run graph algorithms, compute scores.

This is the intellectual core of the project.

#### Step 2a: AST Parsing

Python's built-in `ast` module parses each `.py` file into a tree of nodes. You walk this tree to extract:

```
From each file, extract:
  - ImportFrom nodes  → "this file imports from X"
  - Import nodes      → "this file imports X"
  - ClassDef nodes    → "this file defines class Y"
  - FunctionDef nodes → "this file defines function Z"
  - Call nodes        → "this file calls function W" (best-effort)
```

**Why AST and not regex?**
Regex on source code is fragile. `import os` and `from os import path` and `import os as operating_system` are all semantically the same but would require separate regex patterns. The AST handles all of these uniformly because it understands Python's grammar, not just its text.

**Interface:**

```python
class ASTParser:
    def parse_file(self, file_path: str) -> FileAnalysis:
        # Returns:
        # - imports: List[str]         (what this file imports)
        # - classes: List[str]         (class names defined here)
        # - functions: List[str]       (function names defined here)
        # - dependencies: List[str]    (resolved module names)
        ...
```

#### Step 2b: Graph Construction

After parsing all files, you build a directed graph:

```
Nodes: each Python file (e.g., "auth/session.py")
Edges: directed dependency relationships

Edge direction matters:
  auth/session.py  →  utils/crypto.py
  means: session.py IMPORTS crypto.py
  means: if crypto.py changes, session.py is potentially affected
```

**Why directed?**
The direction encodes causality. A change in `crypto.py` ripples *forward* to everything that imports it. Impact analysis = finding all nodes reachable from a changed node following edge direction.

**Implementation:**

```python
import networkx as nx

class GraphBuilder:
    def build(self, file_analyses: List[FileAnalysis]) -> nx.DiGraph:
        G = nx.DiGraph()
        for analysis in file_analyses:
            G.add_node(analysis.file_path)
            for dep in analysis.dependencies:
                G.add_edge(analysis.file_path, dep)
        return G
```

#### Step 2c: Graph Algorithms

This is where CS fundamentals earn their place in the project.

**Algorithm 1: PageRank**

Originally designed by Google to rank web pages by importance. A page is important if many important pages link to it. Applied to code: a file is architecturally critical if many other critical files depend on it.

```python
scores = nx.pagerank(G, alpha=0.85)
# Returns: {"auth/session.py": 0.043, "utils/crypto.py": 0.021, ...}
# Higher score = more critical file
```

Interview talking point: PageRank is an iterative algorithm. It starts by assigning every node equal weight (1/N), then repeatedly propagates weight along edges until scores converge. The `alpha=0.85` is the damping factor — it models the probability that a "random walker" follows an edge vs. jumps to a random node. This prevents sink nodes (files with no outgoing imports) from absorbing all weight.

**Algorithm 2: Betweenness Centrality**

Measures how often a node lies on the shortest path between two other nodes. In code: a file with high betweenness centrality is a "bridge" — it connects otherwise disconnected parts of the codebase. These are the most dangerous files to change.

```python
betweenness = nx.betweenness_centrality(G)
# High betweenness = architectural bottleneck
```

**Algorithm 3: Cycle Detection (Strongly Connected Components)**

A circular dependency is a set of files where A imports B imports C imports A. These create tight coupling, make testing harder, and indicate architectural problems.

```python
cycles = list(nx.simple_cycles(G))
# Returns list of cycles: [["auth.py", "session.py", "user.py"], ...]
```

**Composite Criticality Score:**
Combine both metrics into a single score per file:

```
criticality_score = 0.6 * normalized_pagerank + 0.4 * normalized_betweenness
```

The weighting (0.6/0.4) is a deliberate design choice you can explain: PageRank captures "how many things depend on this?" while betweenness captures "does everything route through this?" Both matter, but structural importance (PageRank) is weighted slightly higher for this use case.

**Pipeline instrumentation:**

Every `AnalysisPipeline` stage is timed and recorded:

`file_discovery` → `ast_parsing` (total + per-file average) → `import_resolution` → `graph_construction` → `pagerank_computation` → `betweenness_computation` → `score_normalization`

Timings are exposed via `GET /api/status/{repo_id}` (`metrics` array when complete) and via `python -m app.benchmark --repo path/to/project` for local performance testing.

---

### Component 3: FastAPI Backend (API Layer)

**Responsibility:** Expose the analysis engine via HTTP. Receive requests, trigger analysis, return results.

**Why FastAPI over Django?**
Django is a full web framework designed for building websites with templates, admin panels, ORM-based models, and session management. Ripple needs none of that. It needs a fast, clean API. FastAPI gives you:

- Automatic OpenAPI/Swagger documentation at `/docs`
- Pydantic models for request/response validation
- Async support for handling long-running analysis jobs
- Type hints throughout, which makes code readable and self-documenting

**Why FastAPI over Flask?**
Flask is minimal but gives you nothing. You'd manually add validation, documentation, async support — things FastAPI includes. For a new project with no Flask legacy, there's no reason to start with Flask.

---

### Component 4: React Frontend

**Responsibility:** Display the interactive dependency graph. Allow node clicking for impact analysis. Show criticality rankings.

**Why React over plain HTML/JS?**
The graph UI has complex state: which node is selected, which nodes are highlighted, what's shown in the sidebar. Managing this with vanilla JS event listeners becomes spaghetti quickly. React's component model keeps the selected-node state in one place and propagates it cleanly to the graph and sidebar components.

**Why Cytoscape.js over D3?**
D3 is a low-level visualization library — you define every pixel of the graph from scratch. Cytoscape.js is specifically designed for network/graph visualization. It gives you force-directed layouts, node click events, edge highlighting, and zoom/pan out of the box. D3 is the right choice if you need a completely custom visualization; Cytoscape is the right choice if the visualization itself is not the hard part of your project (and for Ripple, it isn't).

---

## 6. Data Flow

This section traces exactly what happens from the moment a user pastes a URL to the moment the graph appears on screen.

```
1. USER pastes GitHub URL into React frontend
        │
        ▼
2. Frontend sends POST /api/analyze (multipart: `file` or `github_url`)
        │
        ▼
3. FastAPI receives request, validates input (URL format / zip integrity)
        │
        ▼
4. Check PostgreSQL: has this repo been analyzed before?
   ├── YES → return cached repo_id, skip to step 9
   └── NO  → continue
        │
        ▼
5. IngestionService (zip extract or `ingest_github`)
   - materialize to /tmp/ripple/{job_id}/
   - find all .py files
   - store file list in PostgreSQL (repos table)  [planned]
        │
        ▼
6. ASTParser.parse_file() for each .py file
   - extract imports, classes, functions
   - store raw analysis in PostgreSQL (file_analyses table)
        │
        ▼
7. GraphBuilder.build(file_analyses)
   - construct nx.DiGraph
   - store edges in PostgreSQL (graph_edges table)
        │
        ▼
8. AlgorithmEngine.run(graph)
   - compute PageRank scores
   - compute Betweenness Centrality
   - detect cycles
   - compute composite criticality scores
   - record per-stage timings (file_discovery through score_normalization)
   - store scores in PostgreSQL (node_scores table)
        │
        ▼
9. API returns { job_id, status: "complete", ...full analysis JSON }
   - PipelineResult saved to AnalysisStore (in-memory) for on-demand impact queries
   - temp ingest dir cleaned up
        │
        ▼
10. (Planned) Frontend polls GET /api/graph/{repo_id}
    - receives nodes[], edges[], scores{}
        │
        ▼
11. Cytoscape.js renders interactive graph
    - node color = criticality (red=high, green=low)
    - node size = PageRank score
        │
        ▼
12. USER clicks a node (e.g., "auth/session.py")
        │
        ▼
13. (API shipped) Frontend calls GET /api/impact/{repo_id}?file=auth/session.py
        │
        ▼
14. (API shipped) Backend runs `ImpactAnalyzer` on stored `PipelineResult`:
    - `predecessors` → direct dependents
    - `ancestors` → transitive dependents
    - reversed graph shortest paths → hop-distance layers
    - lookup existing `NodeScore` for target (no recompute)
        │
        ▼
15. (Planned) Frontend highlights affected nodes in red
    Sidebar shows: "7 files depend on auth/session.py"
```

**System Design Concept — Asynchronous Processing:**
Step 5–8 (clone + parse + analyze) can take 30–120 seconds for a large repo. You should not make the user wait on a single HTTP request that long — most browsers and proxies will time out. The solution is to:

1. Immediately return `{ repo_id, status: "processing" }` from the POST endpoint
2. Run the analysis in a background task (FastAPI's `BackgroundTasks`)
3. Have the frontend poll `GET /api/status/{repo_id}` every 2 seconds
4. When status becomes `"complete"`, fetch the graph (status response includes `metrics` array with per-stage durations)

This is the **async job pattern** used by every real system that processes long-running tasks (video encoding, ML training, report generation).

---

## 7. Database Schema

**Why PostgreSQL?**
You need persistence so you don't re-analyze the same repo on every page refresh. PostgreSQL gives you:

- ACID transactions (analysis results are consistent)
- JSON column support (store graph data flexibly)
- A real database on your resume
- The ability to query results with SQL (useful for debugging)

**Why not Neo4j?**
Neo4j is a graph database. It would make graph traversal queries elegant (using Cypher). However:

- It adds another service to run and maintain
- NetworkX already handles all your algorithm needs in Python
- Explaining Neo4j in an interview requires knowing Cypher, graph database internals, and why you need a dedicated graph store
- For this scale (hundreds to low thousands of nodes), PostgreSQL is more than sufficient

The right answer to "why not Neo4j?" is: "I evaluated it, but since I'm using NetworkX for algorithm execution, Neo4j would be persistence-only. PostgreSQL handles that with less operational overhead, and I can always migrate graph traversal queries to Neo4j if I need to scale."

### Design principles

| Principle | Rationale |
|-----------|-----------|
| **Normalize identities, not URLs** | `https://github.com/pallets/click`, `…/click.git`, and `…/click/` are the same repo — store `owner` + `repo_name`, not a raw URL |
| **Version analysis runs** | Algorithms evolve; `analysis_version` + `analysis_jobs` let you compare runs and re-analyze without losing history |
| **Normalize cycles** | `cycle_files TEXT[]` makes queries like "every cycle containing `core.py`" awkward — use `cycles` + `cycle_members` |
| **Cache statistics** | Don't recompute `file_count`, `edge_count`, density on every `GET /api/graph` — persist in `analysis_statistics` |
| **Hash file content** | `files.sha256` enables incremental analysis (skip unchanged files on re-run) |

**Note:** Shipped JSON export still uses `criticality` in `analysis.scores` (in-memory `NodeScore`). The database column is `composite_score` — same weighted formula (`0.6 * norm(PR) + 0.4 * norm(BT)`), neutral name for storage.

### Schema (implemented)

ORM models: `backend/app/db/models.py`. Migrations: `backend/alembic/` (initial revision creates all tables below). **Writing pipeline results into these tables is still planned** — the API currently uses in-memory `AnalysisStore`.

**Apply and verify** (from project root):

```bash
docker compose up -d db
cd backend && source .venv/bin/activate && alembic upgrade head
cd ..
docker compose exec db psql -U ripple -d ripple -c '\dt'
docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"
```

Interactive: `docker compose exec db psql -U ripple -d ripple` → `\dt`, `\d alembic_version`, SQL ending with `;`, `\q` to quit. Prompt `ripple-#` means a statement is unfinished (missing `;`).

#### Persistence flow (planned)

**Today:** `POST /api/analyze` runs the pipeline synchronously and returns full JSON. `AnalysisStore` keeps `PipelineResult` in memory by `job_id` until server restart. Postgres schema exists; tables are empty.

**Next:** same `AnalysisPipeline.run()` → write `PipelineResult` into the tables below → return `job_id` / poll status. See [learn.md — Right now vs after persistence](./learn.md#right-now-vs-after-persistence).

| `PipelineResult` | PostgreSQL |
|------------------|------------|
| `graph.nodes`, `analyses` | `files` |
| `graph.edges` | `dependencies` |
| `scores` | `node_scores` |
| `cycles` | `cycles`, `cycle_members` |
| counts / density | `analysis_statistics` |

```sql
-- Logical repository (GitHub or zip upload)
CREATE TABLE repositories (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source           TEXT NOT NULL,          -- 'github' | 'zip'
    owner            TEXT,                   -- GitHub org/user; NULL for zip
    repo_name        TEXT NOT NULL,          -- GitHub repo or zip stem
    branch           TEXT,                   -- analyzed branch (GitHub)
    commit_sha       TEXT,                   -- pinned commit when known
    default_branch   TEXT,                   -- e.g. 'main'
    file_hash        TEXT UNIQUE,            -- SHA-256 of zip bytes (zip idempotency)
    analysis_version TEXT NOT NULL DEFAULT '1',  -- Ripple algorithm/schema version
    created_by       TEXT,                   -- future: user id or 'anonymous'
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (owner, repo_name, branch)        -- NULLS NOT DISTINCT in PG15+ for zip rows
);

-- One row per analysis execution (repo may be analyzed many times)
CREATE TABLE analysis_jobs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id       UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'pending',
    -- pending | processing | complete | failed
    error_msg     TEXT,
    started_at    TIMESTAMP,
    completed_at  TIMESTAMP,
    duration_ms   INTEGER,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Each Python file discovered in a job
CREATE TABLE files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id        UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    file_path     TEXT NOT NULL,
    language      TEXT NOT NULL DEFAULT 'python',
    line_count    INTEGER,
    syntax_error  BOOLEAN NOT NULL DEFAULT FALSE,
    sha256        TEXT,                      -- content hash for incremental skip
    UNIQUE (job_id, file_path)
);

-- Directed edges between files (extensible beyond imports)
CREATE TABLE dependencies (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id           UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    source_file_id   UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    target_file_id   UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    dependency_type  TEXT NOT NULL DEFAULT 'import',
    -- import | inheritance | call | type_hint | dynamic_import (future)
    UNIQUE (job_id, source_file_id, target_file_id, dependency_type)
);

-- Algorithm scores per file (one row per file per job)
CREATE TABLE node_scores (
    file_id            UUID PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    job_id             UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    pagerank_score     FLOAT NOT NULL,
    betweenness_score  FLOAT NOT NULL,
    composite_score    FLOAT NOT NULL,       -- 0.6*norm(PR) + 0.4*norm(BT)
    in_degree          INTEGER NOT NULL,
    out_degree         INTEGER NOT NULL
);

-- Circular dependency (header)
CREATE TABLE cycles (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id   UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    length   INTEGER NOT NULL
);

-- Ordered members of each cycle (position 0..n-1 along the loop)
CREATE TABLE cycle_members (
    cycle_id  UUID NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    file_id   UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    PRIMARY KEY (cycle_id, position),
    UNIQUE (cycle_id, file_id)
);

-- Precomputed repo-level stats (avoid recomputing on every read)
CREATE TABLE analysis_statistics (
    job_id                    UUID PRIMARY KEY REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    file_count                INTEGER NOT NULL,
    node_count                INTEGER NOT NULL,
    edge_count                INTEGER NOT NULL,
    cycle_count               INTEGER NOT NULL,
    external_dependency_count INTEGER NOT NULL DEFAULT 0,
    class_count               INTEGER NOT NULL DEFAULT 0,
    function_count            INTEGER NOT NULL DEFAULT 0,
    graph_density             FLOAT,           -- edges / (n*(n-1)) for directed simple graph
    computed_at               TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Example queries enabled by normalization:**

```sql
-- Every cycle that includes core.py
SELECT c.id, c.length
FROM cycles c
JOIN cycle_members cm ON cm.cycle_id = c.id
JOIN files f ON f.id = cm.file_id
WHERE f.file_path = 'src/click/core.py'
  AND c.job_id = :job_id;

-- Latest completed analysis for pallets/click
SELECT j.*
FROM analysis_jobs j
JOIN repositories r ON r.id = j.repo_id
WHERE r.owner = 'pallets' AND r.repo_name = 'click'
ORDER BY j.completed_at DESC NULLS LAST
LIMIT 1;
```

**Index strategy:**

```sql
CREATE INDEX idx_analysis_jobs_repo ON analysis_jobs(repo_id);
CREATE INDEX idx_analysis_jobs_status ON analysis_jobs(status);
CREATE INDEX idx_files_job ON files(job_id);
CREATE INDEX idx_files_sha256 ON files(job_id, sha256);
CREATE INDEX idx_dependencies_job ON dependencies(job_id);
CREATE INDEX idx_dependencies_source ON dependencies(source_file_id);
CREATE INDEX idx_dependencies_target ON dependencies(target_file_id);
CREATE INDEX idx_node_scores_job ON node_scores(job_id);
CREATE INDEX idx_node_scores_composite ON node_scores(composite_score DESC);
CREATE INDEX idx_cycles_job ON cycles(job_id);
CREATE INDEX idx_cycle_members_file ON cycle_members(file_id);
```

**Idempotency (ingestion → DB):**

- **GitHub:** upsert `repositories` on `(owner, repo_name, branch)`; parse URL at the API layer only
- **Zip:** dedupe on `file_hash` before starting a new job
- **Re-analysis:** same repo, new `analysis_jobs` row; compare `analysis_version` and `files.sha256` for incremental parse

---

## 8. API Design

### Why REST over GraphQL?

GraphQL is powerful when clients need to request exactly the fields they want across nested resources — useful for complex UIs with many data shapes. For Ripple, the frontend has exactly three data needs: the full graph, the impact analysis for a node, and the job status. REST is simpler, more universally understood, and requires no special client library. GraphQL would be overengineering here.

### Endpoints

#### Shipped today (sync, in-memory store)

Two endpoints are live. Both require the FastAPI server (`uvicorn app.main:app --reload` from `backend/`). GitHub ingestion requires **git** on the server.

##### POST /api/analyze

```
Request (zip):  multipart/form-data
                file: <zip file>

Request (GitHub): multipart/form-data
                  github_url: https://github.com/owner/repo

Response 200 OK:
{
  "job_id": "uuid",
  "status": "complete",
  "metadata": { "generated_at": "..." },
  "repository": { "name": "owner/repo", "source": "github" },
  "summary": { "file_count": 4, "node_count": 4, "edge_count": 5, "cycle_count": 1 },
  "statistics": { ... },
  "graph": { "nodes": [...], "edges": [...] },
  "analysis": { "cycles": {...}, "scores": [...] },
  "files": { ... }
}

Response 400: empty upload, invalid zip, invalid GitHub URL, both inputs, no Python files
Response 404: GitHub repository not found or not accessible
Response 502: git clone failed
```

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool

curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pypa/sampleproject" | python3 -m json.tool
```

Flow: ingest → `AnalysisPipeline.run(local_path)` → `AnalysisStore.save(job_id, result)` → `cleanup()` (temp dir removed). The `job_id` in the response is the key for impact queries.

##### GET /api/impact/{repo_id}

Uses in-memory `AnalysisStore` keyed by `job_id` from `POST /api/analyze`. Does **not** re-parse source or rebuild the graph. Temp extract/clone dirs are already cleaned; only `PipelineResult` artifacts (graph + scores) remain until server restart (Postgres schema shipped; write path planned).

```
Path params:
  repo_id: job_id returned by POST /api/analyze

Query params:
  file: repo-relative path, URL-encoded (e.g. mini_repo/myapp/models.py)

Response 200 OK:
{
  "target": {
    "file": "mini_repo/myapp/models.py",
    "score": {
      "pagerank": 0.3124,
      "betweenness": 0.0,
      "criticality": 0.6,
      "in_degree": 1,
      "out_degree": 1
    }
  },
  "direct_dependents": ["mini_repo/myapp/utils.py"],
  "indirect_dependents": ["mini_repo/myapp/auth.py"],
  "layers": [
    { "depth": 1, "files": ["mini_repo/myapp/utils.py"] },
    { "depth": 2, "files": ["mini_repo/myapp/auth.py"] }
  ],
  "summary": {
    "direct": 1,
    "indirect": 1,
    "total": 2,
    "max_depth": 2,
    "files_affected_percentage": 50.0
  }
}

Response 400: missing or empty `file` query parameter
Response 404: unknown repo_id (analysis not in store)
Response 404: file not in graph (path not a node in this repo's import graph)
```

Field notes:

| Field | Meaning |
|-------|---------|
| `target.file` | Queried repo-relative path |
| `target.score` | Existing metrics from batch scoring (no `file_path` — use `target.file`); omitted if unavailable |
| `direct_dependents` | Immediate importers (hop 1), sorted |
| `indirect_dependents` | **Indirect** importers only (depth 2+), sorted; excludes direct |
| `layers` | Blast radius by hop distance — `{ depth, files }`; each file in exactly one layer |
| `summary.direct` | Count of direct dependents |
| `summary.indirect` | Count of indirect dependents |
| `summary.total` | `direct + indirect` |
| `summary.max_depth` | Deepest hop distance (0 when no dependents) |
| `summary.files_affected_percentage` | `summary.total / total_files_in_graph * 100`, rounded to 3 decimal places |

```bash
# Analyze first; capture job_id
JOB_ID=$(curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

curl -s "http://localhost:8000/api/impact/${JOB_ID}?file=mini_repo/myapp/models.py" \
  | python3 -m json.tool
```

**Tests:**

```bash
cd backend && source .venv/bin/activate
PYTHONPATH=. pytest tests/test_api.py -v                              # analyze + impact (14)
PYTHONPATH=. pytest tests/test_api.py -k impact -v                    # impact API only (3)
PYTHONPATH=. pytest tests/algorithms/test_impact.py -v                # ImpactAnalyzer unit (8)
```

Study guide: [learn.md — Impact Analysis](./learn.md#phase-1-week-2--impact-analysis). Full contract mirror: [Architecture §6 — GET /api/impact/{repo_id}](./Architecture.md#get-apiimpactrepo_id).

---

#### Planned (async + PostgreSQL)

```
POST   /api/analyze
       Request:  { "github_url": "https://github.com/owner/repo" }
       Response: { "repo_id": "uuid", "status": "processing" }
       Purpose:  Trigger analysis job (202 Accepted)

GET    /api/status/{repo_id}
       Response: { "repo_id": "uuid", "status": "processing|complete|failed",
                   "metrics": [ { "stage_name": "ast_parsing", "duration_ms": 8400,
                                  "files_processed": 247 }, ... ] }
       Purpose:  Poll for job completion; metrics[] present when complete

GET    /api/graph/{repo_id}
       Response: {
           "nodes": [
               {
                   "id": "auth/session.py",
                   "composite_score": 0.87,
                   "pagerank": 0.043,
                   "betweenness": 0.21,
                   "in_degree": 12,
                   "out_degree": 3
               }, ...
           ],
           "edges": [
               { "source": "auth/session.py", "target": "utils/crypto.py", "type": "import" }, ...
           ],
           "cycles": [
               { "length": 3, "nodes": ["auth.py", "session.py", "user.py"] }, ...
           ],
           "statistics": { "file_count": 47, "edge_count": 89, "cycle_count": 2, ... }
       }
       Purpose:  Fetch complete graph for visualization (stats from analysis_statistics)

GET    /api/repos
       Response: [ list of previously analyzed repos ]
       Purpose:  Show analysis history on homepage
```

Interactive docs: `http://localhost:8000/docs` (Swagger UI lists both shipped endpoints).

When PostgreSQL ships, `GET /api/impact/{repo_id}?file=...` will load graph + scores from the database instead of the in-memory store; the response shape stays the same.

**Benchmark CLI (no HTTP):**

```bash
python -m app.benchmark --repo path/to/project
```

---

## 9. Frontend Design

### Component Structure

```
App
├── HomePage
│   ├── URLInputForm          (paste GitHub URL, submit)
│   └── RecentAnalysesList    (previously analyzed repos)
│
└── AnalysisPage
    ├── StatusBanner          (shows "Analyzing... / Complete")
    ├── GraphCanvas           (Cytoscape.js graph)
    │   └── Node              (color = criticality, size = pagerank)
    └── Sidebar
        ├── CriticalFilesList (top 10 ranked files)
        ├── NodeDetail        (shown when node is clicked)
        │   ├── FileInfo      (path, scores)
        │   └── ImpactPanel   ("X files break if this changes")
        └── CycleWarnings     (list of detected circular dependencies)
```

### Visual Design Rules

**Node color encoding:**

```
criticality_score > 0.7   →  Red    (high risk)   — UI maps from composite_score
criticality_score > 0.4   →  Orange (medium risk)
criticality_score > 0.0   →  Green  (low risk)
```

**Node size encoding:**

```
size = base_size + (pagerank_score * scale_factor)
```

Larger nodes are more structurally important. This creates a visual hierarchy without needing labels on every node.

**On node click:**

- Clicked node: highlighted border
- Direct dependents (files that import it): orange highlight
- Transitive dependents (all affected files): light red highlight
- All other nodes: dimmed

This makes the impact analysis immediately visual — you see the "ripple" propagate through the graph.

---

## 10. Functional Requirements


| ID    | Requirement                                                           | Priority     |
| ----- | --------------------------------------------------------------------- | ------------ |
| FR-01 | System accepts a valid public GitHub URL                              | Must Have    |
| FR-02 | System clones and indexes all .py files                               | Must Have    |
| FR-03 | System parses imports and builds dependency graph                     | Must Have    |
| FR-04 | System computes PageRank scores for all nodes                         | Must Have    |
| FR-05 | System computes Betweenness Centrality for all nodes                  | Must Have    |
| FR-06 | System detects circular dependencies                                  | Must Have    |
| FR-07 | System returns graph as JSON via REST API                             | Must Have    |
| FR-08 | Frontend renders interactive force-directed graph                     | Must Have    |
| FR-09 | User can click a node to see impact analysis                          | Must Have    |
| FR-10 | Sidebar shows top 10 critical files ranked                            | Must Have    |
| FR-11 | Previously analyzed repos are cached                                  | Should Have  |
| FR-12 | Circular dependencies are visually highlighted                        | Should Have  |
| FR-13 | Pipeline stage metrics exposed via status API when analysis completes | Must Have    |
| FR-14 | Benchmark CLI prints formatted per-stage timing breakdown             | Should Have  |
| FR-15 | User can search/filter nodes by file name                             | Nice to Have |
| FR-16 | User can export graph as PNG or JSON                                  | Nice to Have |


---

## 11. Non-Functional Requirements


| Category      | Requirement                                                                                |
| ------------- | ------------------------------------------------------------------------------------------ |
| Performance   | Analysis of a repo with <500 Python files completes in under 60 seconds                    |
| Accuracy      | Parser correctly handles standard Python import patterns (absolute, relative, from-import) |
| Usability     | Interactive graph loads and is usable within 3 seconds of analysis completing              |
| Reliability   | Failed analysis jobs surface a clear error message to the user                             |
| Portability   | Entire system runs locally with a single `docker-compose up` command                       |
| Observability | Per-stage pipeline metrics recorded; benchmark CLI available for performance testing       |
| Code Quality  | Each component (parser, graph engine, API) has unit tests with >70% coverage               |


### Verification (how to test requirements)

Run all backend tests from `backend/`: `pytest tests/ -v` (**141 tests**). Use `-v` for verbose output (one line per test). Per-suite commands, pytest basics, and the full test catalog: [learn.md — Introduction to pytest](./learn.md#introduction-to-pytest) and [Testing overview](./learn.md#testing-overview). Quick commands: [README](../README.md#tests) · Full CLI reference: [Architecture §12](./Architecture.md#12-cli-reference).


| Requirement                            | Status          | Verified by                                                                     |
| -------------------------------------- | --------------- | ------------------------------------------------------------------------------- |
| FR-01 Accept public GitHub URL           | Implemented     | `test_github_ingestion.py`, `test_api.py` (GitHub form field) |
| FR-02 Index `.py` files                | Partial         | `test_collect_python_files_skips_cache_dirs`, `test_parse_repository_mini_repo` |
| FR-03 Parse imports + dependency graph | Partial         | `test_parser.py` (15), `test_graph.py` (9), `test_pipeline.py` (9)              |
| FR-04 PageRank                         | Partial         | `test_scoring.py` (13) + pipeline; graph/status API pending — [learn.md](./learn.md#phase-1-week-2--criticality-scoring) |
| FR-05 Betweenness                      | Partial         | same as FR-04                                                                   |
| FR-06 Circular dependencies            | Partial         | `test_cycles.py` (8) + `test_pipeline.py`; graph/status API pending — [learn.md](./learn.md#phase-1-week-2--cycle-detection) |
| FR-07 REST API                         | Partial         | Sync `POST /api/analyze` (zip or `github_url`) + `GET /api/impact/{repo_id}` — `tests/test_api.py` (14); async/DB endpoints pending |
| FR-09 Impact analysis (on-demand)      | Implemented     | `ImpactAnalyzer` + `GET /api/impact` — `tests/algorithms/test_impact.py` (8), `tests/test_api.py` (3 impact cases) |
| FR-13 Pipeline metrics                 | Partial         | `PipelineResult.metrics`; status API pending                                    |
| FR-14 Benchmark CLI                    | Implemented     | `python -m app.benchmark --repo` (`tests/test_benchmark.py`)                    |


**Parser milestone (Week 1):** `PYTHONPATH=. pytest tests/test_parser.py -v`  
**Graph + cycles + impact (Week 2):** `PYTHONPATH=. pytest tests/test_graph.py tests/algorithms/ tests/test_pipeline.py -v`

**Manual CLI check (FR-03):** run from `backend/` with the **project root**, e.g. `python -m app.parser.cli .` or `python -m app.parser.cli tests/fixtures/mini_repo`. Do not pass a package subfolder (`./app/parser`) — internal imports will be misclassified as external. See [learn.md — Analysis root convention](./learn.md#analysis-root-convention).

---

## 12. Project Plan & Milestones

### Phase 1 — Analysis Engine (Weeks 1–3)

*Goal: Pure Python. No web server. No frontend. Prove the analysis works.*

**Week 1: Parser**

- [x] Set up project structure and Git repo
- [x] Implement `ASTParser` — parse a single `.py` file and extract imports
- [x] Handle absolute imports (`import os`), from-imports (`from os import path`), and aliased imports (`import numpy as np`)
- [x] Write unit tests for the parser against 10+ edge case files — `tests/test_parser.py` (15 parametrized + integration cases)
- [x] Milestone: `python -m app.parser.cli path/to/file.py` prints all imports correctly

**Week 2: Graph Builder + Algorithms**

- [x] Implement `GraphBuilder` — assemble parsed files into a dependency graph (`GraphResult`)
- [x] Implement PageRank computation — `AlgorithmEngine` (`graph/algorithms/scoring.py`)
- [x] Implement Betweenness Centrality computation — same
- [x] Implement cycle detection — `CycleDetector` (`graph/algorithms/cycles.py`)
- [x] Write unit tests for graph algorithms — `test_graph.py`, `test_cycles.py`, `test_scoring.py`, `test_impact.py`
- [x] Implement on-demand impact analysis — `ImpactAnalyzer` (`graph/algorithms/impact.py`)
- [x] Pipeline reports cycles + scores — `PipelineResult.cycles` / `.scores`; CLI prints top critical files
- [x] Milestone: `python -m app.pipeline <repo-path>` prints top critical files and any cycles

**Week 3: Ingestion + Integration**

- [x] Implement `IngestionService` — zip upload to temp directory (`/tmp/ripple/{job_id}/`)
- [x] Implement `IngestionService` — clone a public GitHub repo to temp directory (`ingest_github`, shallow clone)
- [x] Walk repo and parse all `.py` files — `parse_repository()` / zip extract / git clone
- [x] Wire parse → graph → cycles → scores in `AnalysisPipeline`
- [x] Wire `IngestionService` → `AnalysisPipeline` in API layer — sync `POST /api/analyze` (zip **or** `github_url` form field)
- [x] Clean up temp directory after analysis (`IngestionService.cleanup`)
- [x] Wire full pipeline with pipeline stage instrumentation (`PipelineResult.metrics`)
- [x] Add benchmark CLI: `python -m app.benchmark --repo path/to/project`
- [x] Output results as JSON file — `PipelineResult.write_json()` / `--json PATH` (includes `repository` metadata; scores rounded to 4 dp)
- [ ] Test against 3 different real Python repos
- [x] Milestone: CLI produces `result.json` with nodes, edges, scores, and cycles (`--json`)
- [x] Milestone: `curl -X POST /api/analyze -F file=@…zip` returns full analysis JSON (see [README](../README.md#api-rest-endpoints))
- [x] Milestone: `curl -X POST /api/analyze -F github_url=https://github.com/pypa/sampleproject` returns full analysis JSON
- [x] Milestone: `GET /api/impact/{job_id}?file=…` returns layered blast radius after analyze (see [§8 — GET /api/impact/{repo_id}](#get-apiimpactrepo_id))

*At the end of Phase 1, the hard work is done. Everything after this is presentation.*

---

### Phase 2 — API Layer (Weeks 4–5)

*Goal: Wrap the analysis engine in FastAPI. Enable async job processing.*

**Week 4: FastAPI Setup + Database**

- [x] Set up FastAPI project, Docker Compose (FastAPI + PostgreSQL) — health endpoint only
- [x] Implement `POST /api/analyze` (partial) — sync zip or GitHub URL, returns full analysis JSON (`tests/test_api.py`)
- [x] Implement `ImpactAnalyzer` — on-demand blast radius (`graph/algorithms/impact.py`, `tests/algorithms/test_impact.py`, 8 cases)
- [x] Implement `GET /api/impact/{repo_id}?file=...` — returns impact analysis from stored `PipelineResult` (`tests/test_api.py`, 3 impact cases)
- [x] Implement PostgreSQL schema (migrations via Alembic) — `app/db/models.py`, `alembic/versions/63207e50c596_initial_schema.py`, `tests/test_db_schema.py`
- [ ] Implement `POST /api/analyze` (full) — async 202, job record in DB, background analysis
- [ ] Implement `GET /api/status/{repo_id}` — returns job status and `metrics[]` when complete
- [ ] Milestone: Can submit a zip via curl, poll status until complete, stage timings in status response

**Week 5: Graph Endpoints**

- [ ] Implement `GET /api/graph/{repo_id}` — returns full graph JSON
- [ ] Implement `GET /api/repos` — returns history
- [ ] Test all endpoints via FastAPI's auto-generated `/docs` UI
- [ ] Milestone: Full API functional, tested manually via Swagger UI *(impact endpoint shipped — see [§8 — GET /api/impact/{repo_id}](#get-apiimpactrepo_id))*

---

### Phase 3 — Frontend (Weeks 6–8)

*Goal: Build the React + Cytoscape.js interface. Make it demo-ready.*

**Week 6: Graph Visualization**

- [x] Set up React project (Vite)

- Integrate Cytoscape.js
- Render nodes and edges from API response
- Apply color and size encoding based on criticality scores
- Milestone: Graph renders correctly for a real repo

**Week 7: Interactivity + Sidebar**

- Implement node click → impact analysis API call → highlight affected nodes
- Build sidebar: critical files list, node detail panel, cycle warnings
- Add loading state + error handling
- Milestone: Full interaction flow works end to end

**Week 8: Polish + Documentation**

- [ ] Add URL input form on homepage
- [ ] Add recent analyses list
- [x] Write README with architecture explanation, screenshots, and setup instructions — architecture and setup done; screenshots pending
- [ ] Record a 2-minute demo video
- [ ] Deploy (optional: Railway or Render for backend, Vercel for frontend)
- [ ] Milestone: Project is portfolio-ready

---

## 13. Version Ladder

### MVP (What's Described Above)

Graph visualization + impact analysis + criticality ranking for Python repos.
**Resume claim:** "Built a static analysis tool that models Python repositories as directed dependency graphs and applies PageRank and Betweenness Centrality to identify architecturally critical files and compute change impact."

### v2 — AI Layer (3–4 weeks after MVP)

Add graph-context RAG:

- When user asks "explain the authentication flow," run graph traversal to find auth-related nodes, retrieve their source code, pass structured graph context + code to an LLM
- Key claim: **LLM responses are grounded in graph traversal, not raw code retrieval**
- This is what separates it from "just another code chatbot"

### v3 — Stretch Goal: Behavioral Coupling (Research-Adjacent)

Analyze git history to find files that frequently change together (co-change coupling). Compare structural coupling (from the dependency graph) with behavioral coupling (from git history). Files with high behavioral coupling but low structural coupling are hidden dependencies — a genuinely novel insight.

- Requires: `gitpython`, co-occurrence matrix computation, new graph edge type
- **This makes the project research-adjacent and gives you the strongest possible interview story**

---

## 14. Interview Talking Points

These are the questions you should be able to answer confidently after building this project.

**On architecture:**

- "Why a modular monolith instead of microservices?"
- "Why PostgreSQL instead of Neo4j for a graph project?"
- "How does your async job processing work?"

**On algorithms:**

- "Explain how PageRank works and why it applies to code."
- "What's the difference between Betweenness Centrality and PageRank? When would each be more useful?"
- "How do you detect circular dependencies? What algorithm?"
- "What's a strongly connected component and why does it matter for code?"

**On system design:**

- "How would you scale this to handle 100 concurrent analysis requests?"
- "How would you handle a 10,000-file monorepo? Would your algorithm choices change?"
- "What's the tradeoff between file-level and function-level graph nodes?"

**On static analysis:**

- "What are the limits of static analysis? What can't your parser detect?"
- "How does Python's dynamic nature (getattr, importlib) affect your accuracy?"
- "Why did you choose the ast module over Tree-sitter?"

**The answer to every one of these questions is already embedded in this document.** Building the project means you'll have real experience to back up the answers.

---

*Document version: 1.2 | Project: Ripple | Stack: Python · FastAPI · PostgreSQL · NetworkX · React · Cytoscape.js · Docker*
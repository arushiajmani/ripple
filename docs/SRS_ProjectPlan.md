# Ripple — Software Requirements Specification & Project Plan

> **One-line pitch:** Paste a GitHub URL, instantly see which Python files matter most and what breaks if you touch them.

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

**Responsibility:** Accept a GitHub URL, clone the repository locally, validate it is a Python project, index all `.py` files.

**Key Design Decision — Where to clone?**
Options:

- Clone to disk (temp directory) → simple, fast, easy to read files
- Clone to memory → complex, unnecessary

Decision: Clone to a temp directory (`/tmp/ripple/{repo_id}/`). Clean up after analysis completes.

**Interface:**

```python
class IngestionService:
    def ingest(self, github_url: str) -> Repository:
        # Returns a Repository object with:
        # - repo_id (UUID)
        # - local_path (str)
        # - python_files (List[str])
        # - metadata (name, owner, language stats)
        ...
```

**System Design Concept — Idempotency:**
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
2. Frontend sends POST /api/analyze { "url": "https://github.com/..." }
        │
        ▼
3. FastAPI receives request, validates URL format
        │
        ▼
4. Check PostgreSQL: has this repo been analyzed before?
   ├── YES → return cached repo_id, skip to step 9
   └── NO  → continue
        │
        ▼
5. IngestionService.ingest(url)
   - git clone to /tmp/ripple/{repo_id}/
   - find all .py files
   - store file list in PostgreSQL (repos table)
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
9. API returns { repo_id, status: "complete" }
        │
        ▼
10. Frontend polls GET /api/graph/{repo_id}
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
13. Frontend calls GET /api/impact/{repo_id}?file=auth/session.py
        │
        ▼
14. Backend runs graph traversal:
    - Find all nodes with path TO this node (predecessors)
    - These are the files that will be affected by a change
        │
        ▼
15. Frontend highlights affected nodes in red
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

**Schema:**

```sql
-- Tracks each repository analysis job
CREATE TABLE repositories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_url  TEXT NOT NULL UNIQUE,
    owner       TEXT,
    name        TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    -- status: pending | processing | complete | failed
    created_at  TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Each Python file found in the repository
CREATE TABLE files (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id     UUID NOT NULL REFERENCES repositories(id),
    file_path   TEXT NOT NULL,   -- e.g., "auth/session.py"
    lines_count INTEGER,
    UNIQUE(repo_id, file_path)
);

-- Dependency edges between files
CREATE TABLE dependencies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id         UUID NOT NULL REFERENCES repositories(id),
    source_file_id  UUID NOT NULL REFERENCES files(id),
    target_file_id  UUID NOT NULL REFERENCES files(id),
    import_type     TEXT  -- 'import' or 'from_import'
);

-- Computed algorithm scores per file
CREATE TABLE node_scores (
    file_id             UUID PRIMARY KEY REFERENCES files(id),
    pagerank_score      FLOAT,
    betweenness_score   FLOAT,
    criticality_score   FLOAT,  -- composite
    in_degree           INTEGER,  -- how many files import this
    out_degree          INTEGER   -- how many files this imports
);

-- Detected circular dependency cycles
CREATE TABLE cycles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id     UUID NOT NULL REFERENCES repositories(id),
    cycle_files TEXT[]   -- array of file paths forming the cycle
);
```

**Index Strategy:**

```sql
-- Speed up all queries that filter by repo
CREATE INDEX idx_files_repo_id ON files(repo_id);
CREATE INDEX idx_dependencies_repo_id ON dependencies(repo_id);
CREATE INDEX idx_node_scores_criticality ON node_scores(criticality_score DESC);
```

---

## 8. API Design

### Why REST over GraphQL?

GraphQL is powerful when clients need to request exactly the fields they want across nested resources — useful for complex UIs with many data shapes. For Ripple, the frontend has exactly three data needs: the full graph, the impact analysis for a node, and the job status. REST is simpler, more universally understood, and requires no special client library. GraphQL would be overengineering here.

### Endpoints

```
POST   /api/analyze
       Request:  { "github_url": "https://github.com/owner/repo" }
       Response: { "repo_id": "uuid", "status": "processing" }
       Purpose:  Trigger analysis job

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
                   "criticality_score": 0.87,
                   "pagerank": 0.043,
                   "betweenness": 0.21,
                   "in_degree": 12,
                   "out_degree": 3
               }, ...
           ],
           "edges": [
               { "source": "auth/session.py", "target": "utils/crypto.py" }, ...
           ],
           "cycles": [
               ["auth.py", "session.py", "user.py"], ...
           ],
           "top_critical": [ ... top 10 nodes by criticality_score ... ]
       }
       Purpose:  Fetch complete graph for visualization

GET    /api/impact/{repo_id}?file=auth/session.py
       Response: {
           "target_file": "auth/session.py",
           "direct_dependents": ["api/routes.py", "tests/test_auth.py"],
           "all_dependents": ["api/routes.py", "tests/test_auth.py", "main.py"],
           "dependent_count": 3
       }
       Purpose:  Impact analysis for a specific file

GET    /api/repos
       Response: [ list of previously analyzed repos ]
       Purpose:  Show analysis history on homepage
```

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
criticality_score > 0.7   →  Red    (high risk)
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

Run all backend tests from `backend/`: `PYTHONPATH=. pytest tests/ -v` (**49 tests**). Use `-v` for verbose output (one line per test). Per-suite commands, pytest basics, and the full test catalog: [learn.md — Introduction to pytest](./learn.md#introduction-to-pytest) and [Testing overview](./learn.md#testing-overview). Quick commands: [README](../README.md#tests).


| Requirement                            | Status          | Verified by                                                                     |
| -------------------------------------- | --------------- | ------------------------------------------------------------------------------- |
| FR-02 Index `.py` files                | Partial         | `test_collect_python_files_skips_cache_dirs`, `test_parse_repository_mini_repo` |
| FR-03 Parse imports + dependency graph | Partial         | `test_parser.py` (11), `test_graph.py` (9), `test_pipeline.py` (9)              |
| FR-04 PageRank                         | Partial         | `test_scoring.py` (12) + pipeline; API/UI pending — [learn.md](./learn.md#phase-1-week-2--criticality-scoring) |
| FR-05 Betweenness                      | Partial         | same as FR-04                                                                   |
| FR-06 Circular dependencies            | Partial         | `test_cycles.py` (8) + `test_pipeline.py`; API/UI pending — [learn.md](./learn.md#phase-1-week-2--cycle-detection) |
| FR-07 REST API                         | Not implemented | `test_api.py` stub                                                              |
| FR-13 Pipeline metrics                 | Not implemented | —                                                                               |
| FR-14 Benchmark CLI                    | Not implemented | —                                                                               |


**Parser milestone (Week 1):** `PYTHONPATH=. pytest tests/test_parser.py -v`  
**Graph + cycles (Week 2):** `PYTHONPATH=. pytest tests/test_graph.py tests/algorithms/ tests/test_pipeline.py -v`

**Manual CLI check (FR-03):** run from `backend/` with the **project root**, e.g. `python -m app.parser.cli .` or `python -m app.parser.cli tests/fixtures/mini_repo`. Do not pass a package subfolder (`./app/parser`) — internal imports will be misclassified as external. See [learn.md — Analysis root convention](./learn.md#analysis-root-convention).

---

## 12. Project Plan & Milestones

### Phase 1 — Analysis Engine (Weeks 1–3)

*Goal: Pure Python. No web server. No frontend. Prove the analysis works.*

**Week 1: Parser**

- [x] Set up project structure and Git repo
- [x] Implement `ASTParser` — parse a single `.py` file and extract imports
- [x] Handle absolute imports (`import os`), from-imports (`from os import path`), and aliased imports (`import numpy as np`)
- [x] Write unit tests for the parser against 10+ edge case files — `tests/test_parser.py` (11 parametrized + integration cases)
- [x] Milestone: `python -m app.parser.cli path/to/file.py` prints all imports correctly

**Week 2: Graph Builder + Algorithms**

- [x] Implement `GraphBuilder` — assemble parsed files into a dependency graph (`GraphResult`)
- [x] Implement PageRank computation — `AlgorithmEngine` (`graph/algorithms/scoring.py`)
- [x] Implement Betweenness Centrality computation — same
- [x] Implement cycle detection — `CycleDetector` (`graph/algorithms/cycles.py`)
- [x] Write unit tests for graph algorithms — `test_graph.py`, `test_cycles.py`, `test_scoring.py`
- [x] Pipeline reports cycles + scores — `PipelineResult.cycles` / `.scores`; CLI prints top critical files
- [x] Milestone: `python -m app.pipeline <repo-path>` prints top critical files and any cycles

**Week 3: Ingestion + Integration**

- [ ] Implement `IngestionService` — clone a GitHub repo to temp directory
- [x] Walk repo and parse all `.py` files — `parse_repository()` (directory path, not zip)
- [x] Wire parse → graph → cycles → scores in `AnalysisPipeline`
- [ ] Wire full pipeline with pipeline stage instrumentation
- [ ] Add benchmark CLI: `python -m app.benchmark --repo path/to/project`
- [ ] Output results as JSON file
- [ ] Test against 3 different real Python repos
- [ ] Milestone: end-to-end CLI produces a valid `result.json` with scores and cycles

*At the end of Phase 1, the hard work is done. Everything after this is presentation.*

---

### Phase 2 — API Layer (Weeks 4–5)

*Goal: Wrap the analysis engine in FastAPI. Enable async job processing.*

**Week 4: FastAPI Setup + Database**

- [x] Set up FastAPI project, Docker Compose (FastAPI + PostgreSQL) — health endpoint only

- Implement PostgreSQL schema (migrations via Alembic)
- Implement `POST /api/analyze` — accepts URL, starts background job, returns repo_id
- Implement `GET /api/status/{repo_id}` — returns job status and `metrics[]` when complete
- Milestone: Can submit a URL via curl and poll for completion with stage timings

**Week 5: Graph + Impact Endpoints**

- Implement `GET /api/graph/{repo_id}` — returns full graph JSON
- Implement `GET /api/impact/{repo_id}?file=...` — returns impact analysis
- Implement `GET /api/repos` — returns history
- Test all endpoints via FastAPI's auto-generated `/docs` UI
- Milestone: Full API functional, tested manually via Swagger UI

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

*Document version: 1.1 | Project: Ripple | Stack: Python · FastAPI · PostgreSQL · NetworkX · React · Cytoscape.js · Docker*
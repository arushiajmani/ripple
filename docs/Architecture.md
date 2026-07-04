# Ripple — Architecture Document

> This document explains every architectural decision made for Ripple: what was chosen, what was considered, and why. It is designed to prepare you to answer any architecture question in an interview.

---

## Table of Contents

1. [Architecture Style](#1-architecture-style)
2. [Folder Structure](#2-folder-structure)
3. [Component Map](#3-component-map)
4. [Technology Decisions](#4-technology-decisions)
5. [Data Models](#5-data-models)
5a. [Parser–Graph Design (Shipped)](#5a-parsergraph-design-shipped)
6. [API Contract](#6-api-contract)
7. [Key Design Patterns](#7-key-design-patterns)
8. [Data Flow — Full Trace](#8-data-flow--full-trace)
9. [Infrastructure](#9-infrastructure)
10. [What Was Deliberately Left Out](#10-what-was-deliberately-left-out)
11. [How This Scales](#11-how-this-scales)

---

## 1. Architecture Style

### Decision: Modular Monolith

All backend code runs in a single Python process. Components are separated by module boundaries (folders with clear interfaces), not by network boundaries (separate services).

### Why Not Microservices

Microservices decompose a system into independently deployable services that communicate over a network. This makes sense when:
- Multiple teams need to deploy independently
- Different components have radically different scaling needs
- Services need to be written in different languages

None of these apply here. A solo developer building one project doesn't benefit from service isolation — they pay the full cost (network latency, distributed tracing, service discovery, deployment complexity) with none of the organizational benefit.

The honest rule: **don't use microservices until a monolith is causing you real pain.**

### Why Not a Pure Monolith (Single File)

A single `app.py` with no internal structure is hard to test, hard to extend, and looks like a script rather than a system. Component boundaries matter even in a monolith.

### Why Modular Monolith

Each component has a defined interface. The `AnalysisPipeline` doesn't know how the `IngestionService` got the files — it just receives a list of file paths. The API layer doesn't know how the graph was computed — it just queries PostgreSQL for results. These boundaries make each component independently testable and replaceable.

**Interview framing:** "I chose a modular monolith because the system has one deployment target, one team, and no scaling requirements that justify distributed complexity. The module boundaries are clean enough that individual components could become separate services later if needed — but I'm not paying that cost upfront."

---

## 2. Folder Structure

```
ripple/
│
├── docker-compose.yml          # Orchestrates all three services
├── README.md
├── ARCHITECTURE.md             # This document
├── ROADMAP.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                # Database migrations
│   │   └── versions/
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── config.py           # Environment variables, settings
│   │   ├── database.py         # PostgreSQL connection, session
│   │   │
│   │   ├── ingestion/          # Component 1: File intake
│   │   │   ├── __init__.py
│   │   │   └── service.py      # IngestionService class
│   │   │
│   │   ├── parser/             # Component 2: AST parsing
│   │   │   ├── __init__.py
│   │   │   ├── ast_parser.py   # ASTParser class
│   │   │   └── models.py       # FileAnalysis dataclass
│   │   │
│   │   ├── graph/              # Component 3: Graph construction + algorithms
│   │   │   ├── __init__.py
│   │   │   ├── builder.py      # GraphBuilder class
│   │   │   ├── algorithms.py   # AlgorithmEngine class
│   │   │   └── models.py       # GraphResult dataclass
│   │   │
│   │   ├── pipeline/           # Component 4: Orchestration
│   │   │   ├── __init__.py
│   │   │   └── pipeline.py     # AnalysisPipeline (parse → graph → cycles → scores)
│   │   ├── benchmark.py        # CLI: python -m app.benchmark --repo <path>
│   │   │
│   │   ├── api/                # Component 5: HTTP layer
│   │   │   ├── __init__.py
│   │   │   ├── routes.py       # All endpoint definitions
│   │   │   └── schemas.py      # Pydantic request/response models
│   │   │
│   │   └── db/                 # Component 6: Database models
│   │       ├── __init__.py
│   │       └── models.py       # SQLAlchemy ORM models
│   │
│   └── tests/
│       ├── test_parser.py       # ASTParser + parse_repository (11)
│       ├── test_graph.py        # GraphBuilder (9)
│       ├── test_pipeline.py     # AnalysisPipeline (9)
│       ├── test_api.py          # stub
│       ├── algorithms/
│       │   ├── test_cycles.py   # CycleDetector (8)
│       │   └── test_scoring.py  # AlgorithmEngine (12)
│       └── fixtures/
│           └── mini_repo/       # cyclic fixture (models ↔ utils)
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/
        │   └── client.js       # All API calls centralized here
        ├── components/
        │   ├── HomePage.jsx
        │   ├── AnalysisPage.jsx
        │   ├── GraphCanvas.jsx  # Cytoscape.js wrapper
        │   ├── Sidebar.jsx
        │   ├── CriticalFilesList.jsx
        │   ├── NodeDetail.jsx
        │   ├── ImpactPanel.jsx
        │   └── CycleWarnings.jsx
        └── hooks/
            ├── useGraph.js      # Graph data fetching + state
            └── useImpact.js     # Impact analysis fetching + state
```

### Why This Structure

Each top-level folder under `app/` is a component with a single responsibility. The dependency direction is strictly one-way:

```
api/ → pipeline/ → parser/ + graph/ + ingestion/
                          ↓
                       db/ (via pipeline)
```

No component imports from a component "above" it in this hierarchy. The API layer calls the pipeline. The pipeline calls the parser and graph builder. The parser and graph builder don't know the API exists. This is the **dependency inversion principle** applied structurally.

### Test layout and isolation

Tests mirror component boundaries so each layer can be verified without pulling in the full stack:

| Layer | Test file | Count | Isolates |
|-------|-----------|-------|----------|
| Parser | `tests/test_parser.py` | 11 | `ASTParser`, `parse_repository` — no graph |
| Graph | `tests/test_graph.py` | 9 | `GraphBuilder` — synthetic `FileAnalysis`, no parser |
| Pipeline | `tests/test_pipeline.py` | 9 | `AnalysisPipeline` — parse → graph → cycles → scores |
| Cycles | `tests/algorithms/test_cycles.py` | 8 | `CycleDetector` — synthetic `GraphResult` only |
| Scoring | `tests/algorithms/test_scoring.py` | 12 | `AlgorithmEngine` — PageRank, betweenness, criticality |

**49 tests total.** Run from `backend/`: `PYTHONPATH=. pytest tests/ -v` (`-v` = verbose — lists each test name and PASSED/FAILED).

- **Quick commands:** [README — Tests](../README.md#tests)
- **Full catalog (every test name):** [learn.md — Testing overview](./learn.md#testing-overview)
- **Milestone gates:** [Roadmap](./Roadmap.md) (Week 1–2 milestone checks)
---

## 3. Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React)                           │
│                                                                     │
│  ┌──────────────┐    ┌─────────────────────────────────────────┐   │
│  │   HomePage   │    │             AnalysisPage                │   │
│  │              │    │                                         │   │
│  │  zip upload  │    │  ┌───────────────┐  ┌───────────────┐  │   │
│  │  repo list   │    │  │  GraphCanvas  │  │    Sidebar    │  │   │
│  └──────┬───────┘    │  │  (Cytoscape)  │  │               │  │   │
│         │            │  │               │  │ CriticalFiles │  │   │
│         │            │  │  nodes+edges  │  │ NodeDetail    │  │   │
│         │            │  │  click events │  │ ImpactPanel   │  │   │
│         │            │  │  highlighting │  │ CycleWarnings │  │   │
│         │            │  └───────────────┘  └───────────────┘  │   │
│         │            └─────────────────────────────────────────┘   │
└─────────┼───────────────────────────────────────────────────────────┘
          │ HTTP/REST
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                       API Layer                              │  │
│  │  POST /analyze  GET /status/:id  GET /graph/:id              │  │
│  │  GET /impact/:id?file=...        GET /repos                  │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐  │
│  │                    AnalysisPipeline                          │  │
│  │         (orchestrates all components below)                  │  │
│  └────────┬──────────────────────────────────────┬─────────────┘  │
│           │                                      │                 │
│  ┌────────▼────────┐  ┌──────────────┐  ┌───────▼─────────────┐  │
│  │ IngestionService│  │  ASTParser   │  │   AlgorithmEngine   │  │
│  │                 │  │              │  │                     │  │
│  │ unzip file      │  │ ast.parse()  │  │ PageRank            │  │
│  │ find .py files  │  │ walk AST     │  │ Betweenness         │  │
│  │ clean up temp   │  │ extract deps │  │ Cycle detection     │  │
│  └─────────────────┘  └──────┬───────┘  │ Criticality score  │  │
│                              │           └─────────────────────┘  │
│                     ┌────────▼────────┐                           │
│                     │  GraphBuilder   │                           │
│                     │                 │                           │
│                     │ nx.DiGraph()    │                           │
│                     │ resolve imports │                           │
│                     │ add edges       │                           │
│                     └─────────────────┘                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      PostgreSQL                              │  │
│  │  repositories | files | dependencies | node_scores | cycles  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Decisions

### Python

**Chosen because:** The `ast` module — Python's own parser — is the most accurate way to parse Python. NetworkX and FastAPI are Python-native. The entire stack aligns around one language.

**Alternatives considered:** Java (weaker parser/graph ecosystem for this use case), Node.js (no serious graph algorithm library comparable to NetworkX).

---

### Python `ast` Module

**Chosen because:** It's CPython's own parser — handles every valid Python syntax by definition. Zero external dependencies. Deterministic and accurate.

**Alternatives considered:**

| Library | Reason Not Chosen |
|---|---|
| Tree-sitter | Excellent for multi-language, but requires learning query language + grammar binaries. Overhead not justified for Python-only. |
| LibCST | Better for code transformation (codemods). Overkill for read-only analysis. |
| Regex | Fragile. Breaks on multiline imports, aliases, conditional imports. |

**Design decision:** `ASTParser` is behind a clean interface class. If multi-language support is added in v2, only this class changes.

---

### NetworkX

**Chosen because:** The standard Python graph library. Ships with all required algorithms — PageRank, Betweenness Centrality, cycle detection — in single-line calls. Widely used in academia and industry.

**Alternatives considered:**

| Library | Reason Not Chosen |
|---|---|
| Neo4j GDS | Graph database, not a computation library. Adds operational overhead for algorithms NetworkX handles in memory. |
| igraph | Faster for very large graphs (millions of nodes). Our graphs have hundreds to low thousands of nodes. NetworkX is sufficient. |
| Manual implementation | Implementing PageRank from scratch is a valid learning exercise but not worth the time here — the algorithms are not the novel part of this project. |

---

### PostgreSQL

**Chosen because:** The data model is relational — repositories contain files, files have dependencies referencing other files, files have scores. Relational data belongs in a relational database. PostgreSQL is production-grade, ACID-compliant, and universally recognized.

**Alternatives considered:**

| Database | Reason Not Chosen |
|---|---|
| Neo4j | Would make graph traversal queries elegant (Cypher). But graph computation happens in NetworkX, not in the database. Two graph systems for the same data is redundant. Neo4j adds operational complexity without replacing NetworkX. |
| MongoDB | Document store. Our data has clear foreign key relationships — relational is the better fit. |
| SQLite | File-based, no server, breaks under concurrent access. Fine for local prototypes, wrong for a containerized system. |
| Redis | In-memory key-value store. Not a primary database. Appropriate for caching in v2, not as the main store. |

**Interview answer to "why not Neo4j for a graph project?":**
"Neo4j is compelling for graph traversal queries, but I'm running graph algorithms in NetworkX — not in the database. The database's job is persistence, not computation. PostgreSQL handles relational persistence well, and I can always add Neo4j if I need Cypher-style traversal queries at scale. Using both would mean maintaining two graph representations of the same data."

---

### FastAPI

**Chosen because:** Automatic OpenAPI documentation at `/docs` (invaluable for development and demos), Pydantic models for request/response validation, native async support for long-running background jobs, type hints throughout.

**Alternatives considered:**

| Framework | Reason Not Chosen |
|---|---|
| Django | Full web framework with ORM, admin, templates, sessions. None of these are needed for a pure API. Brings significant complexity that doesn't serve this project. |
| Flask | Too minimal — requires manually adding validation, documentation, async support. For a new project, FastAPI gives all of this out of the box. |
| Django REST Framework | Better than Flask, but still inherits Django's weight. FastAPI is cleaner for API-only projects. |

---

### React

**Chosen because:** The graph UI has multiple pieces of interconnected state: selected node, highlighted nodes, sidebar content, loading status, analysis job status. React's component model keeps this state manageable and synchronized across components.

**Alternatives considered:**

| Framework | Reason Not Chosen |
|---|---|
| Vue.js | Equally valid. React chosen for larger ecosystem, more employer recognition, more Stack Overflow coverage. |
| Svelte | Excellent performance, smaller bundles. Less widely known, fewer integrations. |
| Vanilla HTML/JS | Sufficient for a static page. Not sufficient for an interactive graph with multiple synchronized UI states — quickly becomes unmanageable. |

---

### Cytoscape.js

**Chosen because:** Purpose-built for node-edge graph visualization. Provides force-directed layout, click events, programmatic highlighting, zoom/pan out of the box. A working interactive graph in one day rather than three weeks.

**Alternatives considered:**

| Library | Reason Not Chosen |
|---|---|
| D3.js | Low-level — you implement force simulation, tick function, drag, zoom, click handlers from scratch. Appropriate when you need a completely custom visualization. Overkill when a network graph is the standard use case. Higher learning value, higher risk of not shipping. |
| vis.js | Similar positioning to Cytoscape. Cytoscape has better documentation, more active maintenance, more layout algorithms. |
| Recharts / Chart.js | For rectangular data (bar, line, pie charts). Not designed for arbitrary node-edge graphs. Wrong tool category. |

---

### Docker + Docker Compose

**Chosen because:**
1. One-command setup (`docker-compose up`) for anyone cloning the repo
2. Environment isolation — exact Python version, exact package versions, exact PostgreSQL version
3. Professional signal — shows understanding of how software gets deployed, not just developed
4. Three services (frontend, backend, database) need to communicate — Compose handles networking automatically

**Docker Compose services:**

```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ripple
      POSTGRES_USER: ripple
      POSTGRES_PASSWORD: ripple
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://ripple:ripple@db:5432/ripple

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

---

## 5a. Parser–Graph Design (Shipped)

> **Current code** differs from some fields below (e.g. `GraphResult` is nodes + edges only until `AlgorithmEngine` ships). See [learn.md](./learn.md) for the up-to-date study guide.

### Architecture (V1)

```
Repository
    ↓
RepositoryParser          parse_repository() in repository.py
    ↓
dict[str, FileAnalysis]   canonical parsed record per file
    ↓
GraphBuilder              reads resolved_deps only (V1)
    ↓
GraphResult               nodes + edges
    ↓
CycleDetector             nx.simple_cycles + normalize
    ↓
AlgorithmEngine           PageRank, betweenness, criticality
    ↓
PipelineResult            analyses + graph + cycles + scores
```

`AnalysisPipeline` wires RepositoryParser → GraphBuilder → CycleDetector → AlgorithmEngine and returns `PipelineResult(analyses, graph, cycles, scores)`.

### Layer responsibilities

| Layer | Components | Role |
|-------|------------|------|
| Parser | `ASTParser`, `FileAnalysis`, RepositoryParser | Single AST pass; emit all structured facts |
| Graph | `GraphBuilder`, `GraphResult`, `CycleDetector`, `AlgorithmEngine` | Import graph, cycles, criticality scores |
| Pipeline | `AnalysisPipeline`, `PipelineResult` | Orchestrate parse → graph → cycles → scores |

### Design decisions

1. **`FileAnalysis` is richer than V1 `GraphBuilder` needs** — one parse produces data for file, class, function, and library views later.
2. **File import graphs only require `resolved_deps`** — edges are cross-file import relationships; internal structure and third-party packages are different graph types.
3. **Unused fields are kept** — avoids reparsing and breaking CLI/tests when V2 builders arrive.
4. **Future builders share the same `dict[str, FileAnalysis]`** — parse once, run `GraphBuilder`, `ClassGraphBuilder`, etc.
5. **Analysis always runs from the project root** — `parse_repository(root)` indexes paths relative to `root`. Import resolution maps package names (`app.parser.models`) to those paths (exact + suffix). Pointing at a package subfolder (e.g. `app/parser/`) yields bare names like `models.py`, so in-repo imports are misclassified as `external_deps`. Production (zip/clone) uses the uploaded project root; the CLI must do the same. Detail: [learn.md — Analysis root convention](./learn.md#analysis-root-convention).
6. **`CycleDetector` is a separate algorithm unit** — reads `GraphResult`, uses NetworkX `simple_cycles`, normalizes rotations, returns `CircularDependencyResult`. Wired into `AnalysisPipeline` as `PipelineResult.cycles`; also unit-tested in isolation (`tests/algorithms/test_cycles.py`, 8 cases). Detail: [learn.md — Cycle Detection](./learn.md#phase-1-week-2--cycle-detection).
7. **`AlgorithmEngine` scores criticality** — PageRank = how depended-on (importance flows importer→imported); betweenness = bridge/bottleneck; criticality = `0.6 * norm(PR) + 0.4 * norm(BT)` relative change-risk; in/out degree = direct importers / imports. Wired as `PipelineResult.scores`; CLI prints top 10. Tests: `tests/algorithms/test_scoring.py` (12). Glossary: [learn.md — What each property means](./learn.md#1-what-each-property-means).

### Future scope

| Version | Capabilities |
|---------|----------------|
| **V1 (current)** | File-level graph; cycles + criticality scores on `PipelineResult` |
| **V2** | Class graph (inheritance, dependencies), function/call graphs, impact analysis, `external_deps` analytics |
| **V3** | AI-assisted explanations, architectural insights, change-risk estimation |

Detail: [learn.md — Design Decisions](./learn.md#design-decisions) · [learn.md — Future Scope](./learn.md#future-scope)

---

## 5. Data Models

### Python Dataclasses (Internal)

```python
# parser/models.py
@dataclass
class FileAnalysis:
    file_path: str              # Relative path: "auth/session.py"
    imports: List[str]          # Raw import strings
    resolved_deps: List[str]    # Resolved file paths of internal imports
    external_deps: List[str]    # Third-party packages (unresolvable)
    classes: List[str]          # Class names defined in this file
    functions: List[str]        # Function names defined in this file
    line_count: int
    has_syntax_error: bool

# graph/models.py
@dataclass
class NodeScore:
    file_path: str
    pagerank: float
    betweenness: float
    criticality: float          # 0.6 * norm_pagerank + 0.4 * norm_betweenness
    in_degree: int              # How many files import this
    out_degree: int             # How many files this imports

@dataclass
class GraphResult:
    repo_id: str
    nodes: List[NodeScore]
    edges: List[Tuple[str, str]]    # (source, target) file path pairs
    cycles: List[List[str]]         # Each cycle is a list of file paths
    top_critical: List[NodeScore]   # Top 10 by criticality score
```

### PostgreSQL Schema

```sql
CREATE TABLE repositories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_url   TEXT,                    -- NULL for zip uploads
    file_hash    TEXT UNIQUE,             -- SHA256 of uploaded zip (idempotency)
    name         TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    error_msg    TEXT,                    -- Set if status = 'failed'
    created_at   TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE files (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id     UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    file_path   TEXT NOT NULL,
    line_count  INTEGER,
    UNIQUE(repo_id, file_path)
);

CREATE TABLE dependencies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id         UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    source_file_id  UUID NOT NULL REFERENCES files(id),
    target_file_id  UUID NOT NULL REFERENCES files(id),
    import_type     TEXT    -- 'absolute' | 'relative' | 'from'
);

CREATE TABLE node_scores (
    file_id             UUID PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    pagerank_score      FLOAT NOT NULL,
    betweenness_score   FLOAT NOT NULL,
    criticality_score   FLOAT NOT NULL,
    in_degree           INTEGER NOT NULL,
    out_degree          INTEGER NOT NULL
);

CREATE TABLE cycles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id     UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    cycle_files TEXT[] NOT NULL
);

-- Indexes for query performance
CREATE INDEX idx_files_repo ON files(repo_id);
CREATE INDEX idx_deps_repo ON dependencies(repo_id);
CREATE INDEX idx_deps_source ON dependencies(source_file_id);
CREATE INDEX idx_deps_target ON dependencies(target_file_id);
CREATE INDEX idx_scores_criticality ON node_scores(criticality_score DESC);
```

---

## 6. API Contract

### POST /api/analyze
Accepts a zip file upload. Creates an analysis job.

```
Request:  multipart/form-data
          file: <zip file>

Response 202 Accepted:
{
  "repo_id": "uuid",
  "status": "processing"
}

Response 400 Bad Request:
{
  "error": "No Python files found in uploaded archive"
}
```

### GET /api/status/{repo_id}
Returns current job status. Once analysis is complete, includes per-stage timing metrics.

```
Response 200 (processing or failed):
{
  "repo_id": "uuid",
  "status": "pending | processing | complete | failed",
  "error": "string | null"
}

Response 200 (complete):
{
  "repo_id": "uuid",
  "status": "complete",
  "error": null,
  "metrics": [
    { "stage_name": "file_discovery", "duration_ms": 45, "files_processed": null },
    { "stage_name": "ast_parsing", "duration_ms": 8400, "files_processed": 247 },
    { "stage_name": "import_resolution", "duration_ms": 2100, "files_processed": 247 },
    { "stage_name": "graph_construction", "duration_ms": 120, "files_processed": 247 },
    { "stage_name": "pagerank_computation", "duration_ms": 890, "files_processed": null },
    { "stage_name": "betweenness_computation", "duration_ms": 3200, "files_processed": null },
    { "stage_name": "score_normalization", "duration_ms": 15, "files_processed": null }
  ]
}

Response 404: repo_id not found
```

**Instrumented stages:** `file_discovery`, `ast_parsing`, `import_resolution`, `graph_construction`, `pagerank_computation`, `betweenness_computation`, `score_normalization`

**Benchmark CLI (no HTTP):**
```bash
python -m app.benchmark --repo path/to/project
```
Runs the full pipeline locally and prints the same stage breakdown to stdout. Used for performance testing on large repos without starting the API server.

### GET /api/graph/{repo_id}
Returns complete graph data for visualization.

```
Response 200:
{
  "repo_id": "uuid",
  "node_count": 47,
  "edge_count": 89,
  "nodes": [
    {
      "id": "auth/session.py",
      "criticality_score": 0.87,
      "pagerank": 0.043,
      "betweenness": 0.21,
      "in_degree": 12,
      "out_degree": 3
    }
  ],
  "edges": [
    { "source": "auth/session.py", "target": "utils/crypto.py" }
  ],
  "cycles": [
    ["auth/session.py", "auth/user.py", "auth/permissions.py"]
  ],
  "top_critical": [ /* top 10 nodes by criticality_score */ ]
}

Response 404: repo not found
Response 409: analysis not yet complete
```

### GET /api/impact/{repo_id}?file={file_path}
Returns impact analysis for a specific file.

```
Query params:
  file: "auth/session.py"   (URL-encoded)

Response 200:
{
  "target_file": "auth/session.py",
  "criticality_score": 0.87,
  "direct_dependents": ["api/routes.py", "tests/test_auth.py"],
  "all_dependents": ["api/routes.py", "tests/test_auth.py", "main.py"],
  "direct_count": 2,
  "total_count": 3
}

Response 404: file not found in this repo's graph
```

### GET /api/repos
Returns list of previously analyzed repositories.

```
Response 200:
[
  {
    "repo_id": "uuid",
    "name": "myproject",
    "status": "complete",
    "node_count": 47,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

## 7. Key Design Patterns

### Pattern 1: Async Job Processing

**Problem:** Analysis takes 30–120 seconds. A synchronous HTTP request would time out.

**Solution:** The POST endpoint immediately returns a `repo_id` and starts analysis as a background task. The client polls the status endpoint until complete.

```
Client                          Server
  │                               │
  ├── POST /analyze ─────────────►│
  │◄── 202 { repo_id } ───────────┤  (immediate response)
  │                               │  (background: clone, parse, compute...)
  ├── GET /status/{id} ──────────►│
  │◄── { status: "processing" } ──┤
  ├── GET /status/{id} ──────────►│  (poll every 2 seconds)
  │◄── { status: "complete", metrics: [...] } ──┤
  ├── GET /graph/{id} ───────────►│
  │◄── { nodes, edges, scores } ──┤
```

This is the **async job pattern** used by every system with long-running processing: video encoding pipelines, ML training APIs, report generation services.

**FastAPI implementation:**
```python
@app.post("/api/analyze")
async def analyze(file: UploadFile, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo = create_repo_record(db)
    background_tasks.add_task(run_analysis, repo.id, file, db)
    return { "repo_id": str(repo.id), "status": "processing" }
```

---

### Pattern 2: Idempotent Ingestion

**Problem:** If the same zip file is uploaded twice, don't repeat the full analysis.

**Solution:** Hash the zip file content (SHA-256) on upload. Before starting analysis, check if a repo with this hash already exists and is complete. If yes, return the existing result immediately.

```python
file_hash = hashlib.sha256(file_content).hexdigest()
existing = db.query(Repository).filter_by(file_hash=file_hash, status='complete').first()
if existing:
    return { "repo_id": str(existing.id), "status": "complete" }
```

This is the **idempotency pattern** — making the same request multiple times produces the same result without side effects. Standard in data pipelines and payment systems.

---

### Pattern 3: Clean Interface for the Parser

**Problem:** You want to swap the parser (from `ast` to Tree-sitter) later without changing the rest of the system.

**Solution:** Define an abstract interface that the parser must implement. The rest of the system depends on the interface, not the implementation.

```python
# parser/base.py
from abc import ABC, abstractmethod

class BaseParser(ABC):
    @abstractmethod
    def parse_file(self, file_path: str, content: str) -> FileAnalysis:
        pass

# parser/ast_parser.py
class ASTParser(BaseParser):
    def parse_file(self, file_path: str, content: str) -> FileAnalysis:
        # ast module implementation
        ...

# In future: parser/treesitter_parser.py
class TreeSitterParser(BaseParser):
    def parse_file(self, file_path: str, content: str) -> FileAnalysis:
        # Tree-sitter implementation
        ...
```

The `AnalysisPipeline` accepts a `BaseParser` — you can swap implementations without changing the pipeline. This is the **strategy pattern**.

---

### Pattern 4: Separation of Computation and Persistence

**Problem:** Should graph algorithms run inside the database (Neo4j GDS) or in application code (NetworkX)?

**Decision:** Application code (NetworkX). The database stores raw data and results. Application code does computation.

**Why this matters:** Databases are optimized for storage, indexing, and querying — not arbitrary algorithm execution. NetworkX is optimized for graph computation. Using each tool for what it's good at is the correct separation.

```
PostgreSQL:    stores nodes, edges, scores        (persistence layer)
NetworkX:      computes PageRank, centrality      (computation layer)
FastAPI:       orchestrates, serves results       (API layer)
```

This pattern is called **compute-storage separation** and is how most real analytical systems work (think: Spark for computation, S3 for storage).

---

## 8. Data Flow — Full Trace

Complete trace from zip upload to graph appearing on screen.

```
1.  User selects zip file in React frontend
         │
         ▼
2.  Frontend: POST /api/analyze (multipart form with zip)
         │
         ▼
3.  FastAPI: receive file, compute SHA-256 hash
         │
         ├── Hash exists in DB + status=complete? → return existing repo_id
         │
         └── New hash → continue
         │
         ▼
4.  Create Repository record in PostgreSQL (status='processing')
         │
         ▼
5.  Return 202: { repo_id, status: "processing" } immediately
         │
         ▼ (background task starts)
6.  IngestionService:
    - Extract zip to /tmp/ripple/{repo_id}/
    - Walk directory tree
    - Collect all .py files (exclude venv/, __pycache__/, etc.)
    - Store file list in PostgreSQL (files table)
         │
         ▼
7.  ASTParser (for each .py file):
    - Read file content
    - ast.parse(content) → AST
    - Walk AST nodes:
        ImportFrom → extract module + names
        Import → extract module names
        ClassDef → extract class name, bases
        FunctionDef → extract function name
    - Resolve relative imports using file path + package root
    - Return FileAnalysis dataclass
         │
         ▼
8.  GraphBuilder:
    - Create nx.DiGraph()
    - Add node for each Python file
    - Add directed edge for each resolved dependency
      (source=importer, target=imported)
    - Track external deps separately (not graph nodes)
         │
         ▼
9.  AlgorithmEngine:
    - pagerank_scores = nx.pagerank(G, alpha=0.85)
    - betweenness_scores = nx.betweenness_centrality(G)
    - Normalize both score sets to [0, 1]
    - criticality = 0.6 * norm_pagerank + 0.4 * norm_betweenness
    - cycles = list(nx.simple_cycles(G))
    - Each stage records duration (file_discovery through score_normalization)
         │
         ▼
10. Write results to PostgreSQL:
    - dependencies table (all edges)
    - node_scores table (all scores)
    - cycles table (all detected cycles)
    - Update repositories.status = 'complete'
    - Clean up /tmp/ripple/{repo_id}/
         │
         ▼
11. Frontend polling detects status='complete' (metrics[] available in response)
         │
         ▼
12. Frontend: GET /api/graph/{repo_id}
         │
         ▼
13. FastAPI: query PostgreSQL, assemble GraphResult JSON, return
         │
         ▼
14. Cytoscape.js renders graph:
    - nodes colored by criticality (red/orange/green)
    - nodes sized by pagerank score
    - force-directed layout applied
         │
         ▼
15. User clicks node "auth/session.py"
         │
         ▼
16. Frontend: GET /api/impact/{repo_id}?file=auth/session.py
         │
         ▼
17. FastAPI:
    - Load graph from PostgreSQL into NetworkX
    - ancestors = nx.ancestors(G, "auth/session.py")
    - predecessors = list(G.predecessors("auth/session.py"))
    - Return impact result
         │
         ▼
18. Frontend highlights:
    - Direct dependents: orange
    - Transitive dependents: light red
    - Unaffected nodes: dimmed
    - Sidebar shows: "3 files depend on auth/session.py"
```

---

## 9. Infrastructure

### docker-compose.yml Structure

```
┌─────────────────────────────────────────────────┐
│                Docker Network                   │
│                                                 │
│  ┌────────────┐    ┌──────────┐    ┌─────────┐  │
│  │  frontend  │    │ backend  │    │   db    │  │
│  │            │    │          │    │         │  │
│  │ React+Vite │    │ FastAPI  │    │Postgres │  │
│  │ port 3000  │───►│ port8000 │───►│ port5432│  │
│  └────────────┘    └──────────┘    └─────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
          │
          ▼ exposed to host machine
    localhost:3000 (frontend)
    localhost:8000 (backend API + /docs)
```

### Environment Variables

```bash
# backend/.env
DATABASE_URL=postgresql://ripple:ripple@db:5432/ripple
TEMP_DIR=/tmp/ripple
MAX_REPO_SIZE_MB=100
```

### Backend Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

---

## 10. What Was Deliberately Left Out

These are features that were considered and explicitly deferred. This section exists so you can explain *why* something is missing, not just that it's missing.

| Feature | Why Excluded from MVP |
|---|---|
| GitHub URL ingestion | Adds operational complexity (rate limits, auth, clone time) before the analysis engine is proven. File upload is simpler and gets to the interesting part faster. |
| Function-level graph nodes | File-level is sufficient to demonstrate the algorithms. Function-level parsing requires handling method calls, dynamic dispatch, and class resolution — a significantly harder problem. |
| User authentication | No multi-user scenario in the demo. Adds complexity (session management, password hashing) that doesn't serve the portfolio goal. |
| AI/LLM chat interface | The graph must be accurate before AI can usefully explain it. Adding AI before validating the graph produces confidently wrong answers. |
| Multi-language support | Each language is a separate parser. Java, TypeScript, and Go each have their own AST representations. Supporting multiple languages dilutes the parser quality for each. |
| Real-time analysis progress | WebSockets or SSE add implementation complexity. Polling every 2 seconds is sufficient for this use case. |
| Private GitHub repositories | Requires OAuth flow, token management, and GitHub API integration. Deferred to v2. |

---

## 11. How This Scales

You likely won't need to scale this project. But knowing how you *would* scale it is an important interview topic.

### Current Bottlenecks

**Analysis time:** Large repos (1000+ files) could take several minutes. The entire analysis runs synchronously in one background task.

**Memory:** NetworkX holds the entire graph in memory. For very large repos, this could be gigabytes.

**Concurrent analyses:** FastAPI's BackgroundTasks runs in the same process. Many simultaneous analysis jobs would compete for CPU.

**Benchmarking:** `python -m app.benchmark --repo path/to/project` runs the full pipeline and prints per-stage timing to stdout. Use this to profile large repos before optimizing; watch for `ast_parsing` dominating wall time on 1000+ file codebases.

### How You Would Scale

**Problem: slow analysis**
Solution: Break the analysis pipeline into stages. Parse files in parallel using Python's `multiprocessing` or `concurrent.futures`. Each file is independent during parsing — perfect for parallelization.

**Problem: memory pressure**
Solution: For graphs with 10,000+ nodes, switch from in-memory NetworkX to Neo4j with the Graph Data Science plugin. This is the point where Neo4j becomes the right choice.

**Problem: concurrent jobs**
Solution: Add a proper job queue (Celery + Redis). Instead of running analysis in FastAPI's background tasks, push jobs to a queue and have separate worker processes consume them. This is the standard pattern for background job processing at scale.

**Interview answer:** "The current architecture runs analysis in FastAPI background tasks, which is fine for a demo but wouldn't scale to concurrent production traffic. The natural evolution is a task queue — Celery with Redis as the broker — so analysis workers are separate from the API process and can be scaled independently. I'd also parallelize the per-file parsing step since each file is independent."

---

*Architecture version: 1.1 | Project: Ripple | Stack: Python · FastAPI · PostgreSQL · NetworkX · React · Cytoscape.js · Docker*

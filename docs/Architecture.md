# Ripple — Architecture Document

> **Reorganized.** Primary docs: [architecture/README.md](architecture/README.md) · [reference/](reference/) · [development/cli-reference.md](development/cli-reference.md)

| Section | New doc |
|---------|---------|
| Architecture style, components | [architecture/README.md](architecture/README.md) |
| API contracts | [reference/api-schema.md](reference/api-schema.md) |
| CLI reference | [development/cli-reference.md](development/cli-reference.md) |
| Database DDL | [reference/database-schema.md](reference/database-schema.md) |

*Archive below — full original architecture document.*

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
12. [CLI Reference](#12-cli-reference)

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
│   ├── alembic.ini             # Alembic config (URL overridden in env.py)
│   ├── alembic/                # Database migrations
│   │   ├── env.py              # Loads Base.metadata + DATABASE_URL
│   │   ├── script.py.mako      # Template for new revisions
│   │   └── versions/
│   │       └── 63207e50c596_initial_schema.py  # All 8 SRS tables
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── config.py           # Environment variables, settings
│   │   ├── database.py         # Engine, SessionLocal, Base, get_db()
│   │   │
│   │   ├── ingestion/          # Component 1: File intake
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # RepositoryHandle (job_id, local_path, source, name)
│   │   │   ├── protocol.py     # IngestionServiceProtocol
│   │   │   ├── zip.py          # ZipIngestion
│   │   │   ├── github.py       # GitHubIngestion (clone + remote check)
│   │   │   ├── validation.py   # parse_github_url
│   │   │   ├── exceptions.py
│   │   │   └── service.py      # IngestionService facade
│   │   │
│   │   ├── parser/             # Component 2: AST parsing
│   │   │   ├── __init__.py
│   │   │   ├── ast_parser.py   # ASTParser class
│   │   │   └── models.py       # FileAnalysis dataclass
│   │   │
│   │   ├── graph/              # Component 3: Graph construction + algorithms
│   │   │   ├── __init__.py
│   │   │   ├── builder.py      # GraphBuilder class
│   │   │   ├── adapter.py      # GraphAdapter — GraphResult → nx.DiGraph
│   │   │   ├── models.py       # GraphResult, ScoringResult, …
│   │   │   └── algorithms/
│   │   │       ├── cycles.py   # CycleDetector
│   │   │       ├── scoring.py  # AlgorithmEngine (PageRank, betweenness)
│   │   │       └── impact.py   # ImpactAnalyzer (on-demand blast radius)
│   │   │
│   │   ├── pipeline/           # Component 4: Orchestration
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py     # AnalysisPipeline (parse → graph → adapter → algorithms)
│   │   │   ├── serialize.py  # JSON export (metadata/summary/statistics/graph/…)
│   │   │   ├── store.py        # AnalysisStore (in-memory PipelineResult by repo_id)
│   │   │   └── __main__.py   # python -m app.pipeline <repo> [--json PATH]
│   │   ├── benchmark/
│   │   │   └── __main__.py     # python -m app.benchmark --repo <path>
│   │   ├── metrics.py          # StageMetric, StageTimer, format_metrics_table
│   │   │
│   │   ├── api/                # Component 5: HTTP layer
│   │   │   ├── __init__.py
│   │   │   ├── routes.py       # POST /api/analyze (legacy fat JSON)
│   │   │   ├── repos.py        # POST /api/repos/analyze, GET /api/repos[/{id}/graph|scores|impact]
│   │   │   ├── analyze_request.py  # shared analyze request runner (both endpoints)
│   │   │   ├── errors.py       # centralized domain-exception → HTTP handlers
│   │   │   ├── analysis.py     # ingest → pipeline orchestration
│   │   │   ├── impact.py       # on-demand impact from stored artifacts
│   │   │   └── deps.py         # FastAPI dependencies
│   │   │
│   │   └── db/                 # Component 6: Database models (schema shipped)
│   │       ├── __init__.py
│   │       └── models.py       # SQLAlchemy ORM — 8 SRS tables
│   │
│   └── tests/
│       ├── test_parser.py       # ASTParser + parse_repository (11)
│       ├── test_graph.py        # GraphBuilder (9)
│       ├── test_adapter.py      # GraphAdapter (4)
│       ├── test_pipeline.py     # AnalysisPipeline (9)
│       ├── test_ingestion.py    # zip extract (8)
│       ├── test_github_ingestion.py  # GitHub clone (17)
│       ├── test_api.py          # API integration (31)
│       ├── test_db_schema.py    # ORM metadata vs SCHEMA_TABLES (2)
│       ├── algorithms/
│       │   ├── test_cycles.py   # CycleDetector (8)
│       │   ├── test_scoring.py  # AlgorithmEngine (13)
│       │   └── test_impact.py   # ImpactAnalyzer (8)
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
| Parser | `tests/test_parser.py` | 15 | `ASTParser`, `parse_repository` — no graph |
| Graph | `tests/test_graph.py` | 9 | `GraphBuilder` — synthetic `FileAnalysis`, no parser |
| Adapter | `tests/test_adapter.py` | 4 | `GraphAdapter` — `GraphResult` → `nx.DiGraph` |
| Pipeline | `tests/test_pipeline.py` | 9 | `AnalysisPipeline` — parse → graph → adapter → algorithms |
| Benchmark | `tests/test_benchmark.py` | 16 | Stage metrics, grouped CLI table, `metrics_iterator`, edge cases |
| Ingestion (zip) | `tests/test_ingestion.py` | 8 | Zip extract, zip-slip, cleanup, pipeline |
| Ingestion (GitHub) | `tests/test_github_ingestion.py` | 17 | URL validation, mocked clone, live integration |
| API | `tests/test_api.py` | 31 | `POST /api/analyze`, `POST /api/repos/analyze`, repo list/detail, graph/scores/impact |
| DB schema | `tests/test_db_schema.py` | 2 | ORM metadata registers all 8 SRS tables + key FKs / PKs |
| Serialize | `tests/test_serialize.py` | 18 | JSON (metadata, repository, statistics, graph, …) |
| Cycles | `tests/algorithms/test_cycles.py` | 8 | `CycleDetector` — synthetic `nx.DiGraph` only |
| Scoring | `tests/algorithms/test_scoring.py` | 13 | `AlgorithmEngine` — PageRank, betweenness, criticality, warm-up |
| Impact | `tests/algorithms/test_impact.py` | 9 | `ImpactAnalyzer` — layers, cycles, score lookup, metrics |

**165 tests total.** Run from `backend/`: `pytest tests/ -v` (`pythonpath = .` in `pytest.ini`).

- **CLI commands (all tools + tests):** [§12 CLI Reference](#12-cli-reference)
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
│  │  zip / GitHub │    │  ┌───────────────┐  ┌───────────────┐  │   │
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
│  │  POST /analyze  GET /impact/:id?file=...  GET /repos (planned)   │  │
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
│  │ zip / git clone │  │ ast.parse()  │  │ PageRank            │  │
│  │ find .py files  │  │ walk AST     │  │ Betweenness         │  │
│  │ clean up temp   │  │ extract deps │  │ Criticality score   │  │
│  └─────────────────┘  └──────┬───────┘  └──────────▲──────────┘  │
│                              │                     │              │
│                     ┌────────▼────────┐  ┌─────────┴───────────┐  │
│                     │  GraphBuilder   │  │    CycleDetector    │  │
│                     │                 │  │  (nx.simple_cycles) │  │
│                     │ GraphResult     │  └─────────▲───────────┘  │
│                     └────────┬────────┘            │              │
│                              │           ┌─────────┴───────────┐  │
│                     ┌────────▼────────┐  │    GraphAdapter     │  │
│                     │  GraphResult    │  │ GraphResult→DiGraph │  │
│                     │  (nodes+edges)  │──►  (built once/run)   │  │
│                     └────────┬────────┘  └─────────────────────┘  │
│                              │                                    │
│                     ┌────────▼────────┐  ┌─────────────────────┐  │
│                     │ AnalysisStore   │  │   ImpactAnalyzer    │  │
│                     │ (in-memory)     │──►  (on-demand query)  │  │
│                     └─────────────────┘  └─────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      PostgreSQL                              │  │
│  │  repositories | analysis_jobs | files | dependencies |      │  │
│  │  node_scores | cycles | cycle_members | analysis_statistics │  │
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
| --- | --- |
| Tree-sitter | Excellent for multi-language, but requires learning query language + grammar binaries. Overhead not justified for Python-only. |
| LibCST | Better for code transformation (codemods). Overkill for read-only analysis. |
| Regex | Fragile. Breaks on multiline imports, aliases, conditional imports. |

**Design decision:** `ASTParser` is behind a clean interface class. If multi-language support is added in v2, only this class changes.

---

### NetworkX

**Chosen because:** The standard Python graph library. Ships with all required algorithms — PageRank, Betweenness Centrality, cycle detection — in single-line calls. Widely used in academia and industry.

**Alternatives considered:**

| Library | Reason Not Chosen |
| --- | --- |
| Neo4j GDS | Graph database, not a computation library. Adds operational overhead for algorithms NetworkX handles in memory. |
| igraph | Faster for very large graphs (millions of nodes). Our graphs have hundreds to low thousands of nodes. NetworkX is sufficient. |
| Manual implementation | Implementing PageRank from scratch is a valid learning exercise but not worth the time here — the algorithms are not the novel part of this project. |

---

### PostgreSQL

**Chosen because:** The data model is relational — repositories contain files, files have dependencies referencing other files, files have scores. Relational data belongs in a relational database. PostgreSQL is production-grade, ACID-compliant, and universally recognized.

**Alternatives considered:**

| Database | Reason Not Chosen |
| --- | --- |
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
| --- | --- |
| Django | Full web framework with ORM, admin, templates, sessions. None of these are needed for a pure API. Brings significant complexity that doesn't serve this project. |
| Flask | Too minimal — requires manually adding validation, documentation, async support. For a new project, FastAPI gives all of this out of the box. |
| Django REST Framework | Better than Flask, but still inherits Django's weight. FastAPI is cleaner for API-only projects. |

---

### React

**Chosen because:** The graph UI has multiple pieces of interconnected state: selected node, highlighted nodes, sidebar content, loading status, analysis job status. React's component model keeps this state manageable and synchronized across components.

**Alternatives considered:**

| Framework | Reason Not Chosen |
| --- | --- |
| Vue.js | Equally valid. React chosen for larger ecosystem, more employer recognition, more Stack Overflow coverage. |
| Svelte | Excellent performance, smaller bundles. Less widely known, fewer integrations. |
| Vanilla HTML/JS | Sufficient for a static page. Not sufficient for an interactive graph with multiple synchronized UI states — quickly becomes unmanageable. |

---

### Cytoscape.js

**Chosen because:** Purpose-built for node-edge graph visualization. Provides force-directed layout, click events, programmatic highlighting, zoom/pan out of the box. A working interactive graph in one day rather than three weeks.

**Alternatives considered:**

| Library | Reason Not Chosen |
| --- | --- |
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

> **Shipped:** `GraphResult` holds structural nodes + edges; scores and cycles live on `PipelineResult`. Algorithms consume `nx.DiGraph` via `GraphAdapter`. See [§5a](#5a-parsergraph-design-shipped) and [learn.md](./learn.md).

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
GraphResult               nodes + edges (Ripple domain model)
    ↓
GraphAdapter              single conversion to networkx.DiGraph
    ↓
networkx.DiGraph          shared by all graph algorithms (built once per run)
    ├── CycleDetector     nx.simple_cycles + normalize
    └── AlgorithmEngine   PageRank, betweenness, criticality
    ↓
PipelineResult            analyses + graph + cycles + scores
    ↓
AnalysisStore             in-memory cache by job_id (on-demand queries)  ← shipped today
    ↓                       Postgres write path planned → files, dependencies, node_scores, …
ImpactAnalyzer            ImpactAnalysisResult (per-file, not a batch stage)
```

**Today:** upload → pipeline → JSON response + `AnalysisStore`. **Next:** same pipeline, then persist `PipelineResult` to Postgres and return `job_id` for polling. Detail: [learn.md — Right now vs after persistence](./learn.md#right-now-vs-after-persistence).

`AnalysisPipeline` wires RepositoryParser → GraphBuilder → GraphAdapter → CycleDetector + AlgorithmEngine and returns `PipelineResult(analyses, graph, cycles, scores)`.

### Layer responsibilities

| Layer | Components | Role |
|-------|------------|------|
| Parser | `ASTParser`, `FileAnalysis`, RepositoryParser | Single AST pass; emit all structured facts |
| Graph | `GraphBuilder`, `GraphResult`, `GraphAdapter` | Domain graph; bridge to NetworkX |
| Algorithms | `CycleDetector`, `AlgorithmEngine`, `ImpactAnalyzer` | Operate on `nx.DiGraph` only — no `GraphResult`; impact is on-demand, not batch |
| Pipeline | `AnalysisPipeline`, `PipelineResult` | Orchestrate parse → graph → adapter → algorithms |

### Design decisions

1. **`FileAnalysis` is richer than V1 `GraphBuilder` needs** — one parse produces data for file, class, function, and library views later.
2. **File import graphs only require `resolved_deps`** — edges are cross-file import relationships; internal structure and third-party packages are different graph types.
3. **Unused fields are kept** — avoids reparsing and breaking CLI/tests when V2 builders arrive.
4. **Future builders share the same `dict[str, FileAnalysis]`** — parse once, run `GraphBuilder`, `ClassGraphBuilder`, etc.
5. **Analysis always runs from the project root** — `parse_repository(root)` indexes paths relative to `root`. Import resolution maps package names (`app.parser.models`) to those paths (exact + suffix). Pointing at a package subfolder (e.g. `app/parser/`) yields bare names like `models.py`, so in-repo imports are misclassified as `external_deps`. Production (zip/clone) uses the uploaded project root; the CLI must do the same. Detail: [learn.md — Analysis root convention](./learn.md#analysis-root-convention).
6. **`GraphAdapter` is the single NetworkX conversion point** — Ripple owns `GraphResult`; NetworkX is an implementation detail. The adapter converts once per pipeline run; all algorithms share the same `DiGraph`. Conversion only — no algorithm logic in the adapter.
7. **`CycleDetector` is a separate algorithm unit** — takes `nx.DiGraph`, uses NetworkX `simple_cycles`, normalizes rotations, returns `CircularDependencyResult`. Wired into `AnalysisPipeline` as `PipelineResult.cycles`; unit-tested in isolation (`tests/algorithms/test_cycles.py`, 8 cases). Detail: [learn.md — Cycle Detection](./learn.md#phase-1-week-2--cycle-detection).
8. **`AlgorithmEngine` scores criticality** — takes the shared `nx.DiGraph`; PageRank = how depended-on (importance flows importer→imported); betweenness = bridge/bottleneck; criticality = `0.6 * norm(PR) + 0.4 * norm(BT)` relative change-risk; in/out degree = direct importers / imports. Production analysis computes PageRank once; the benchmark CLI opts into an extra untimed PageRank warm-up (`AlgorithmEngine(warmup_pagerank=True)`) to exclude one-time SciPy/NetworkX backend initialization from its steady-state timings. Wired as `PipelineResult.scores`; CLI prints top 10. Tests: `tests/algorithms/test_scoring.py` (13). Glossary: [learn.md — What each property means](./learn.md#1-what-each-property-means).
9. **`ImpactAnalyzer` answers "what breaks if I change file F?"** — on-demand query, not a batch pipeline stage. Takes the shared `nx.DiGraph` plus optional `ScoringResult`; walks **predecessors** (reverse reachability: importer → imported, so dependents = who imports F). Uses `predecessors`, `ancestors`, and `single_source_shortest_path_length` on the reversed graph for hop-distance **layers** (each file in exactly one layer). Reuses existing `NodeScore` for the target — does not recompute criticality. Wired via `AnalysisStore` + `GET /api/repos/{repo_id}/impact?file=...`. Temp dirs cleaned after analyze; `PipelineResult` cached by `repo_id` in memory and persisted to PostgreSQL. Tests: `tests/algorithms/test_impact.py` (8). Detail: [learn.md — Impact Analysis](./learn.md#phase-1-week-2--impact-analysis).

### Future scope

| Version | Capabilities |
|---------|----------------|
| **V1 (current)** | File-level import graph (type: imports); cycles + criticality; JSON keeps class bases for V2 |
| **V2** | Class graph (inheritance), function/call graphs, `external_deps` analytics |
| **V3** | AI-assisted explanations, architectural insights, change-risk estimation |

**Why V1 does not emit `type: "inherits"` edges:** the parser records base **names** (`ClassInfo.bases`), not resolved class/file targets; inheritance is class→class while V1 nodes are file paths; reliable edges need a base resolver and class-level node IDs (`ClassGraphBuilder`). The JSON edge object shape is already extensible. Detail: [learn.md — Why not `type: "inherits"` yet](./learn.md#why-not-type-inherits-or-calls-yet).

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
```

Top critical files: use `ScoringResult.top(n)` in Python or `analysis.scores.slice(0, n)` in JSON clients — not a separate field.

### PostgreSQL Schema (implemented)

ORM: `backend/app/db/models.py`. Migrations: `backend/alembic/` (initial revision `63207e50c596_initial_schema`). Config: `app/config.py` (`DATABASE_URL`) + `app/database.py` (`Base`, `get_db`).

**Status:** Tables and indexes are defined and migratable. Pipeline results are **written to Postgres** on every successful analyze (`app/db/persist.py`); repo sub-routes reload via `app/db/load.py` when the in-memory store is cold.

#### Memory today → rows tomorrow

| `PipelineResult` field | Table(s) |
|------------------------|----------|
| `graph.nodes` + `analyses` | `files` |
| `graph.edges` | `dependencies` |
| `scores` | `node_scores` (`composite_score` = API `criticality`) |
| `cycles` | `cycles`, `cycle_members` |
| summary / counts | `analysis_statistics` |
| repo identity | `repositories`, `analysis_jobs` |

See [learn.md — Right now vs after persistence](./learn.md#right-now-vs-after-persistence) for flow diagrams.

See [SRS — Database Schema](./SRS_ProjectPlan.md#7-database-schema) for full rationale. Summary:

| Table | Role |
|-------|------|
| `repositories` | Stable identity: `owner`, `repo_name`, `branch`, `commit_sha` (not raw URL) |
| `analysis_jobs` | One row per analysis run (`status`, timings) |
| `files` | Per-job file index + `language`, `syntax_error`, `sha256` |
| `dependencies` | Edges with `dependency_type` (`import`, future: `inheritance`, `call`, …) |
| `node_scores` | `composite_score` (not `criticality_score`) + PageRank / betweenness |
| `cycles` + `cycle_members` | Normalized cycles (query by file via `cycle_members`) |
| `analysis_statistics` | Cached counts / density — avoid recomputing per request |

```sql
CREATE TABLE repositories (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source           TEXT NOT NULL,
    owner            TEXT,
    repo_name        TEXT NOT NULL,
    branch           TEXT,
    commit_sha       TEXT,
    default_branch   TEXT,
    file_hash        TEXT UNIQUE,
    analysis_version TEXT NOT NULL DEFAULT '1',
    created_by       TEXT,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (owner, repo_name, branch)
);

CREATE TABLE analysis_jobs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id       UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'pending',
    error_msg     TEXT,
    started_at    TIMESTAMP,
    completed_at  TIMESTAMP,
    duration_ms   INTEGER,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id        UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    file_path     TEXT NOT NULL,
    language      TEXT NOT NULL DEFAULT 'python',
    line_count    INTEGER,
    syntax_error  BOOLEAN NOT NULL DEFAULT FALSE,
    sha256        TEXT,
    UNIQUE (job_id, file_path)
);

CREATE TABLE dependencies (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id           UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    source_file_id   UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    target_file_id   UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    dependency_type  TEXT NOT NULL DEFAULT 'import',
    UNIQUE (job_id, source_file_id, target_file_id, dependency_type)
);

CREATE TABLE node_scores (
    file_id            UUID PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    job_id             UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    pagerank_score     FLOAT NOT NULL,
    betweenness_score  FLOAT NOT NULL,
    composite_score    FLOAT NOT NULL,
    in_degree          INTEGER NOT NULL,
    out_degree         INTEGER NOT NULL
);

CREATE TABLE cycles (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id   UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    length   INTEGER NOT NULL
);

CREATE TABLE cycle_members (
    cycle_id  UUID NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    file_id   UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    PRIMARY KEY (cycle_id, position),
    UNIQUE (cycle_id, file_id)
);

CREATE TABLE analysis_statistics (
    job_id                    UUID PRIMARY KEY REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    file_count                INTEGER NOT NULL,
    node_count                INTEGER NOT NULL,
    edge_count                INTEGER NOT NULL,
    cycle_count               INTEGER NOT NULL,
    external_dependency_count INTEGER NOT NULL DEFAULT 0,
    class_count               INTEGER NOT NULL DEFAULT 0,
    function_count            INTEGER NOT NULL DEFAULT 0,
    graph_density             FLOAT,
    computed_at               TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_analysis_jobs_repo ON analysis_jobs(repo_id);
CREATE INDEX idx_files_job ON files(job_id);
CREATE INDEX idx_cycle_members_file ON cycle_members(file_id);
CREATE INDEX idx_node_scores_composite ON node_scores(composite_score DESC);
```

Apply from `backend/` (Postgres must be running): `alembic upgrade head`. Source of truth for the shipped SQL is `alembic/versions/63207e50c596_initial_schema.py` (autogenerated from `app/db/models.py`).

**Quick verify** (project root):

```bash
docker compose up -d db
cd backend && source .venv/bin/activate && alembic upgrade head
docker compose exec db psql -U ripple -d ripple -c '\dt'
docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"
```

See [§12 — Database operations](#database-operations) for interactive `psql`, prompts, and troubleshooting.

---

## 6. API Contract

### POST /api/analyze

Accepts **either** a zip file upload **or** a public GitHub URL and runs analysis synchronously (schema exists; results still go to in-memory `AnalysisStore`, not Postgres yet).

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
  "summary": { ... },
  "statistics": { ... },
  "graph": { "nodes": [...], "edges": [...] },
  "analysis": { "cycles": {...}, "scores": [...] },
  "files": { ... }
}

Response 400 Bad Request:
  Empty upload, invalid zip, invalid GitHub URL, both inputs, no Python files

Response 404 Not Found:
  GitHub repository not found or not accessible

Response 502 Bad Gateway:
  git clone failed
```

**Manual tests (repo root, server in `backend/`, git required for GitHub):**

```bash
# Zip upload
curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool

# GitHub URL
curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pypa/sampleproject" | python3 -m json.tool
```

**pytest:**

```bash
cd backend && source .venv/bin/activate
PYTHONPATH=. pytest tests/test_api.py -v
```

**Future (Phase 4):** Return `202 Accepted` with `repo_id` + `status: "processing"`, poll `GET /api/jobs/{job_id}`. Impact queries use `GET /api/repos/{repo_id}/impact` (latest job) or `GET /api/jobs/{job_id}/impact` (specific run).

See also: [GET /api/repos/{repo_id}/impact](#get-apireposrepo_idimpact) (shipped).

```
Response 202 Accepted (planned):
{
  "repo_id": "uuid",
  "status": "processing"
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

Runs the full pipeline locally and prints per-stage timing to stdout. PageRank timings measure **steady-state** performance: one untimed warm-up call excludes one-time NetworkX/SciPy backend initialization. A performance note is printed at the end of the report. Used for profiling large repos without starting the API server.

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
      "composite_score": 0.87,
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
  ]
}
```

`scores` is a separate ordered list in the export schema (`analysis.scores`); top N = first N entries. Future `GET /api/graph/{repo_id}?top=10` may slice at the HTTP layer.

- Response 404: repo not found
- Response 409: analysis not yet complete

### GET /api/repos/{repo_id}/impact

On-demand blast-radius for one file in a **previously analyzed** repository (latest completed job). Uses `AnalysisStore` keyed by `repo_id`, falling back to PostgreSQL via `load_pipeline_result`. Does not re-parse source or rebuild the graph.

Full field reference: [SRS §8 — GET /api/repos/{repo_id}/impact](./SRS_ProjectPlan.md#get-apireposrepo_idimpact).

```
Path params:
  repo_id: repositories.id returned by POST /api/analyze or POST /api/repos/analyze

Query params:
  file: "mini_repo/myapp/models.py"   (URL-encoded repo-relative path)

Response 200:
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
Response 404: repository analysis not found (unknown repo_id)
Response 404: file not in graph (unknown or out-of-repo path)
```

**Manual test (server running on port 8000):**

```bash
# Analyze first; capture repo_id
REPO_ID=$(curl -s -X POST http://localhost:8000/api/repos/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -c "import sys,json; print(json.load(sys.stdin)['repo_id'])")

curl -s "http://localhost:8000/api/repos/${REPO_ID}/impact?file=mini_repo/myapp/models.py" | python3 -m json.tool
```

**pytest:**

```bash
cd backend && source .venv/bin/activate
PYTHONPATH=. pytest tests/algorithms/test_impact.py -v    # ImpactAnalyzer (9)
PYTHONPATH=. pytest tests/test_api.py -k impact -v         # API integration
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
GraphAdapter:  GraphResult → nx.DiGraph           (conversion layer)
NetworkX:      computes PageRank, centrality      (computation layer)
FastAPI:       orchestrates, serves results       (API layer)
```

This pattern is called **compute-storage separation** and is how most real analytical systems work (think: Spark for computation, S3 for storage).

---

## 8. Data Flow — Full Trace

Complete trace from zip upload or GitHub URL to graph appearing on screen.

```
1.  User submits zip file or GitHub URL in React frontend
         │
         ▼
2.  Frontend: POST /api/analyze (multipart: `file` or `github_url`)
         │
         ▼
3.  FastAPI: receive file, compute SHA-256 hash
         │
         ├── Hash exists in DB + status=complete? → return existing repo_id
         │
         └── New hash → continue
         │
         ▼
4.  Upsert `repositories` (owner/repo_name/branch or zip file_hash); create `analysis_jobs` row (status='processing')
         │
         ▼
5.  Return 202: { job_id, repo_id, status: "processing" } immediately
         │
         ▼ (background task starts)
6.  IngestionService:
    - Zip: extract to /tmp/ripple/{job_id}/  —  GitHub: shallow clone to same path
    - Walk directory tree
    - Collect all .py files (exclude venv/, __pycache__/, etc.)
    - Store file list in PostgreSQL (files table)  [planned]
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
    - Build GraphResult (sorted nodes + directed import edges)
    - Edges: (importer, imported) for each resolved_deps entry
         │
         ▼
9.  GraphAdapter:
    - Convert GraphResult → nx.DiGraph (once per pipeline run)
    - CycleDetector: nx.simple_cycles + rotation normalization
    - AlgorithmEngine:
        - Untimed PageRank warm-up (benchmark CLI only; excludes cold-start from metrics)
        - pagerank_scores = nx.pagerank(G, alpha=0.85)  [timed]
        - betweenness_scores = nx.betweenness_centrality(G)  [timed]
        - Normalize both score sets to [0, 1]
        - criticality = 0.6 * norm_pagerank + 0.4 * norm_betweenness
    - Each stage records duration (file_discovery through score_normalization)
         │
         ▼
10. Write results to PostgreSQL:
    - files (with sha256, syntax_error), dependencies (dependency_type='import')
    - node_scores (composite_score), cycles + cycle_members
    - analysis_statistics (file_count, edge_count, density, …)
    - Update analysis_jobs.status = 'complete', duration_ms
    - Clean up /tmp/ripple/{job_id}/
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
16. Frontend: GET /api/repos/{repo_id}/impact?file=auth/session.py
         │
         ▼
17. FastAPI:
    - Load PipelineResult from AnalysisStore (Postgres write path planned)
    - GraphAdapter → nx.DiGraph (reuse stored graph + scores)
    - ImpactAnalyzer.analyze(digraph, file, scores=result.scores)
    - Return impact result (target, direct/indirect dependents, labeled layers, summary)
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
| --- | --- |
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

**Benchmarking:** `python -m app.benchmark --repo path/to/project` runs the full pipeline and prints per-stage timing to stdout. Timings reflect steady-state algorithm performance after an untimed PageRank warm-up. Use this to profile large repos before optimizing; watch for `ast_parsing` dominating wall time on 1000+ file codebases.

### How You Would Scale

**Problem: slow analysis**
Solution: Break the analysis pipeline into stages. Parse files in parallel using Python's `multiprocessing` or `concurrent.futures`. Each file is independent during parsing — perfect for parallelization.

**Problem: memory pressure**
Solution: For graphs with 10,000+ nodes, switch from in-memory NetworkX to Neo4j with the Graph Data Science plugin. This is the point where Neo4j becomes the right choice.

**Problem: concurrent jobs**
Solution: Add a proper job queue (Celery + Redis). Instead of running analysis in FastAPI's background tasks, push jobs to a queue and have separate worker processes consume them. This is the standard pattern for background job processing at scale.

**Interview answer:** "The current architecture runs analysis in FastAPI background tasks, which is fine for a demo but wouldn't scale to concurrent production traffic. The natural evolution is a task queue — Celery with Redis as the broker — so analysis workers are separate from the API process and can be scaled independently. I'd also parallelize the per-file parsing step since each file is independent."

---

## 12. CLI Reference

Every command below is written **in full** at least once (including `cd`, venv activation, and real fixture paths).

**Working directory:** almost all backend commands run from `backend/`. Docker commands run from the project root (`ripple/`).

### Command sheet (all inputs)

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
| Impact for one file | `repo_id` + file path | `curl "…/api/repos/{repo_id}/impact?file=path/to/file.py"` | on-demand blast radius (after analyze) |
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

### Pipeline stages vs repo input

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
| `impact_analysis` | On-demand only | `GET /api/repos/{repo_id}/impact?file=…` or `ImpactAnalyzer().analyze(digraph, file)` |
| Zip extract | No | `IngestionService.ingest_zip*` or `pytest tests/test_ingestion.py` |
| Git clone | No | `IngestionService.ingest_github` or `pytest tests/test_github_ingestion.py` |

**Why one repo argument:** `AnalysisPipeline.run(repo_path)` orchestrates every stage. The parser CLI stops before graph building; the benchmark adds timing on top of the same pipeline.

### One-time setup (full commands)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

After that, keep the venv active in your shell. Re-run `source .venv/bin/activate` in new terminals.

---

### Analysis CLIs (with input)

These commands take **paths as arguments** — a `.py` file, a project directory, or `--repo` for the benchmark.

#### Parser — inspect imports and structure

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

#### Pipeline — full analysis report (+ optional JSON)

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

#### Benchmark — per-stage timings

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

**Project root rule:** pass the directory that owns all relative paths (the repo root), not a package subfolder like `app/parser/`. See [§5a — Analysis root convention](#5a-parsergraph-design-shipped).

---

### Ingestion (zip and GitHub)

Ripple has **`IngestionService`** — every path produces a `RepositoryHandle` with `local_path` for `AnalysisPipeline.run()`. Zip and GitHub are invisible to the analysis engine. There is **no `python -m app.ingestion` CLI**; use the API, Python API, or pytest.

**Design:** `{base_dir}/{job_id}/` (default `/tmp/ripple/`). Zip extracts archive contents; GitHub shallow-clones (`git clone --depth 1`) into the job dir. Validation: zip-slip protection; GitHub URL parse + `git ls-remote` existence check.

#### Run ingestion tests

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_ingestion.py -v          # zip (8)
PYTHONPATH=. pytest tests/test_github_ingestion.py -v   # GitHub (17)
PYTHONPATH=. pytest tests/test_api.py -v                 # HTTP API (31)
```

Skip the live GitHub clone in CI or offline runs:

```bash
PYTHONPATH=. pytest tests/test_github_ingestion.py -v -m "not integration"
```

#### Zip tests (`test_ingestion.py`)

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

#### GitHub tests (`test_github_ingestion.py`)

| Test | What it proves |
|------|----------------|
| `test_parse_github_url_*` | URL validation (common forms + rejections) |
| `test_ingest_github_clones_to_job_directory` | Mocked clone lands under job dir |
| `test_ingest_github_rejects_missing_repository` | Remote check failure before clone |
| `test_ingest_github_removes_partial_directory_on_clone_failure` | Failed clone cleans up |
| `test_ingested_github_repo_runs_through_pipeline` | Clone → full pipeline |
| `test_ingest_github_integration_clones_public_repository` | Live clone of `pypa/sampleproject` (`@pytest.mark.integration`) |

#### API — analyze via HTTP

```bash
# Server in backend/
uvicorn app.main:app --reload

# Zip (from repo root)
curl -s -X POST http://localhost:8000/api/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -m json.tool

# GitHub (requires git on server)
curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pypa/sampleproject" | python3 -m json.tool

# Impact (after analyze — use repo_id from response)
REPO_ID=$(curl -s -X POST http://localhost:8000/api/repos/analyze \
  -F "file=@backend/tests/fixtures/mini_repo.zip" | python3 -c "import sys,json; print(json.load(sys.stdin)['repo_id'])")
curl -s "http://localhost:8000/api/repos/${REPO_ID}/impact?file=mini_repo/myapp/models.py" | python3 -m json.tool
```

**Note (zip):** if the zip contains a top-level folder (e.g. `myproject/...`), paths in the graph will include that prefix unless you point the pipeline at the inner root.

---

### Server & infrastructure

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

### Database operations

Ripple's Postgres container uses user/database `ripple` / `ripple` (see `docker-compose.yml`). Default URL for local Alembic: `postgresql://ripple:ripple@localhost:5432/ripple`.

#### Apply migrations

```bash
docker compose up -d db
cd backend && source .venv/bin/activate
alembic upgrade head
```

#### Inspect schema (one-liners from project root)

```bash
docker compose exec db psql -U ripple -d ripple -c '\dt'
docker compose exec db psql -U ripple -d ripple -c '\d alembic_version'
docker compose exec db psql -U ripple -d ripple -c "SELECT * FROM alembic_version;"
docker compose exec db psql -U ripple -d ripple -c "SELECT COUNT(*) FROM repositories;"
```

#### Interactive `psql`

```bash
docker compose exec db psql -U ripple -d ripple
```

| Command | Purpose |
|---------|---------|
| `\dt` | List tables |
| `\d tablename` | Describe columns and indexes (e.g. `\d alembic_version`) |
| `\q` | Quit |
| `SELECT * FROM files;` | Run SQL — **must end with `;`** |

#### Prompts and troubleshooting

| Prompt | Meaning |
|--------|---------|
| `ripple=#` | Ready for input |
| `ripple-#` | Continuation — previous statement not terminated. Type `;` + Enter, or **Ctrl+C** to cancel |

| Problem | Cause | Fix |
|---------|-------|-----|
| `bash: SELECT: command not found` | Ran SQL in bash, not in `psql` | Use `docker compose exec db psql …` or open interactive `psql` first |
| `ripple-#` stuck | Forgot semicolon on previous line | `;` + Enter, or Ctrl+C |
| `alembic` can't connect | Postgres not running | `docker compose up -d db` |
| Empty data tables | Expected today | Schema only — API still uses in-memory `AnalysisStore` |

After a successful `alembic upgrade head`, expect **9 tables**: the 8 SRS tables plus `alembic_version` with `version_num = 63207e50c596`.

---

### Automated tests (pytest)

Run from `backend/` with `pytest` (`pythonpath = .` in `pytest.ini`). Integration tests use **in-repo fixtures** (`tests/fixtures/mini_repo/`) and **temp directories** created by pytest — you do not pass paths on the CLI for those.

#### Run the full suite

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Runs all **141** tests. `-v` prints one line per test (`PASSED` / `FAILED`).

#### Run one suite (full commands)

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
pytest tests/test_api.py -v         # API integration (31)
```

See [Command sheet](#command-sheet-all-inputs) for which pytest file maps to which capability. Zip-specific tests are **only** in `test_ingestion.py` (no zip CLI exists yet).

#### Run a single test or filter by name

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

#### Roadmap milestone gates (full commands)

```bash
cd backend
source .venv/bin/activate

PYTHONPATH=. pytest tests/test_parser.py -v

PYTHONPATH=. pytest tests/test_graph.py tests/algorithms/ tests/test_pipeline.py -v
```

#### Manual CLI checks (same inputs tests use)

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

*Architecture version: 1.4 | Project: Ripple | Stack: Python · FastAPI · PostgreSQL · NetworkX · React · Cytoscape.js · Docker*

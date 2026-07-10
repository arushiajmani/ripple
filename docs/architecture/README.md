# Architecture

## Modular monolith

All backend code runs in one Python process. Components live in separate packages (`parser/`, `graph/`, `pipeline/`, `api/`) with one-way dependencies:

```text
api/ → pipeline/ → parser/ + graph/ + ingestion/
                          ↓
                       db/
```

**Why not microservices?** One team, one deployment, no scaling pain that justifies distributed complexity.

**Why not a single script?** Module boundaries enable isolated tests and future extraction.

## Pipeline overview

```text
Repository
    ↓
parse_repository()          # batch AST parse
    ↓
FileAnalysis (per file)
    ↓
GraphBuilder                # V1: resolved_deps only
    ↓
GraphResult
    ↓
GraphAdapter                # → networkx.DiGraph (once per run)
    ↓
networkx.DiGraph
    ├── CycleDetector
    └── AlgorithmEngine     # PageRank, betweenness, criticality
    ↓
PipelineResult
    ↓
AnalysisStore + PostgreSQL  # persist on analyze; impact on demand
    ↓
ImpactAnalyzer              # not a batch stage
```

`FileAnalysis` is richer than V1 `GraphBuilder` needs — one parse feeds future class/call graphs without reparsing. See [parser-graph design](#parser-graph-design).

## API resources

HTTP API follows **repository → analysis jobs → results**:

- **Repository routes** (`GET /api/repos/{repo_id}/…`) — default UX; latest completed job
- **Job routes** (`GET /api/jobs/{job_id}/…`) — history, comparisons, async polling (planned)

Full matrix and rollout: [api-resources.md](api-resources.md).

## Component map

```text
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (React + Cytoscape.js) — planned visualization    │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP
┌─────────────────────────▼───────────────────────────────────┐
│  FastAPI: Repository Analysis + Quick Analysis (POST),          │
│           GET /api/repos/{repo_id}/graph|scores|impact         │
│  AnalysisPipeline → IngestionService, Parser, Graph, DB       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                    PostgreSQL
```

Shipped API: sync analyze, repo list/detail, graph/scores/impact sub-routes. Planned: job APIs, `GET /api/status`, async 202.

Module docs: [backend/](../backend/).

## Parser–graph design

1. **`FileAnalysis` is the parser's full contract** — V1 graph reads only `resolved_deps`; V2 builders reuse the same parse.
2. **File graphs use `resolved_deps` only** — external packages are not nodes.
3. **Unused fields are kept** — avoids reparsing when V2 ships.
4. **Analysis runs from project root** — not a package subfolder. Detail: [backend/parser.md](../backend/parser.md#analysis-root-convention).
5. **`GraphAdapter` is the single NetworkX conversion** — algorithms share one `DiGraph` per run.
6. **Impact is on-demand** — `ImpactAnalyzer` is not a pipeline batch stage.

## Technology choices

| Choice | Why |
|--------|-----|
| Python `ast` | CPython's parser; accurate for all valid syntax |
| NetworkX | PageRank, betweenness, `simple_cycles` in-process |
| PostgreSQL | Relational persistence; graph compute stays in NetworkX |
| FastAPI | OpenAPI at `/docs`, Pydantic, async-ready |
| React + Cytoscape.js | Interactive graph UI (frontend in progress) |
| Docker Compose | One-command setup for reviewers |

**Why not Neo4j?** Algorithms run in NetworkX; Postgres persists results. Neo4j would duplicate the graph without replacing computation.

Interview depth: [product/README.md](../product/README.md#interview-guide).

## Design patterns

| Pattern | Use in Ripple |
|---------|----------------|
| Async job processing | Planned: 202 + poll `GET /api/status` |
| Idempotent ingestion | Planned: zip `file_hash` dedupe |
| Strategy (parser interface) | `ASTParser` swappable for Tree-sitter later |
| Compute / storage separation | NetworkX computes; Postgres stores |

## Data flow (shipped today)

1. User uploads zip or GitHub URL → **Repository Analysis** (`POST /api/repos/analyze`) or **Quick Analysis** (`POST /api/analyze`)
2. `IngestionService` → temp dir `/tmp/ripple/{job_id}/`
3. `AnalysisPipeline.run(local_path)` → `PipelineResult`
4. Persist to PostgreSQL + `AnalysisStore.save(repo_id, result)`
5. Return JSON; `cleanup()` removes temp dir
6. `GET /api/repos/{repo_id}/impact?file=...` (or `/graph`, `/scores`) loads stored artifacts (memory or DB)

Full 18-step trace (including planned frontend): see historical [Architecture.md](../Architecture.md) or expand in a future split doc.

## Infrastructure

```yaml
# docker-compose.yml (simplified)
services:
  db:        postgres:15, port 5432
  backend:   FastAPI, port 8000, DATABASE_URL → db
  frontend:  Vite, port 5173
```

Environment (`backend/.env`):

```bash
DATABASE_URL=postgresql://ripple:ripple@db:5432/ripple
```

## Scaling (interview topic)

| Bottleneck | Direction |
|------------|-----------|
| Slow parse on 1000+ files | Parallelize per-file parsing (`multiprocessing`) |
| Memory on huge graphs | Neo4j GDS at 10k+ nodes |
| Concurrent jobs | Celery + Redis queue instead of `BackgroundTasks` |

## Deliberately deferred (MVP)

| Feature | Reason |
|---------|--------|
| Function-level nodes | File-level proves algorithms; call graphs are harder |
| User auth | No multi-user demo requirement |
| AI chat | Graph must be accurate first |
| Multi-language | One parser quality target |
| Private GitHub | OAuth complexity |

Version ladder: [product/README.md](../product/README.md#version-ladder).

# Product

Vision, scope, roadmap, and interview preparation for Ripple.

## Problem and vision

When you land in an unfamiliar Python codebase, two questions dominate:

- Which files are most critical to understand?
- What breaks if I change this file?

Ripple statically analyzes a repository, builds a dependency graph, and applies graph algorithms (PageRank, betweenness, cycle detection) to surface architectural intelligence.

**Ripple is not:** a linter, a code search engine, or a chatbot.

**Ripple is:** a graph-theoretic structural analysis tool.

## MVP scope

### In scope

| Capability | Doc |
|------------|-----|
| GitHub + zip ingestion | [backend/ingestion.md](../backend/ingestion.md) |
| AST parsing | [backend/parser.md](../backend/parser.md) |
| Dependency graph | [backend/graph-builder.md](../backend/graph-builder.md) |
| Criticality scoring | [backend/graph-builder.md](../backend/graph-builder.md#criticality-scoring) |
| Cycle detection | [backend/graph-builder.md](../backend/graph-builder.md#cycle-detection) |
| Impact analysis | [backend/graph-builder.md](../backend/graph-builder.md#impact-analysis) |
| REST API (partial) | [backend/api.md](../backend/api.md) |
| PostgreSQL persistence | [backend/persistence.md](../backend/persistence.md) |
| Interactive graph UI | Planned — `frontend/` docs when built |

### Out of scope (MVP)

AI chat, git history, multi-language, user auth, function-level nodes, private GitHub repos.

Detail: [architecture/README.md](../architecture/README.md#deliberately-deferred-mvp).

## Roadmap

### Phase 0 — Setup ✓

Docker Compose (backend, db, frontend), health endpoint, Vite scaffold.

### Phase 1 — Analysis engine ✓ (mostly)

| Week | Focus | Status |
|------|-------|--------|
| 1 | AST parser | ✓ |
| 2 | Graph + algorithms | ✓ |
| 3 | Ingestion + API + JSON + benchmark | ✓ |
| — | Validate on 3+ real repos | Open |

### Phase 2 — API layer (in progress)

| Item | Status |
|------|--------|
| Sync `POST /api/analyze` | ✓ |
| `GET /api/impact` | ✓ |
| PostgreSQL schema + persist | ✓ |
| Async 202 + `GET /api/status` | Planned |
| `GET /api/graph`, `GET /api/repos` | Planned |

### Phase 3 — Frontend (not started)

Cytoscape graph, sidebar (critical files, impact, cycles), upload flow, polling.

Future docs will live under `docs/frontend/` (e.g. `graph-visualization.md`).

## Version ladder

| Version | Focus |
|---------|--------|
| **V1 (current)** | File-level import graph; cycles; criticality; impact API |
| **V2** | Class/call graphs, `external_deps` analytics, richer edges (`inherits`, `calls`) |
| **V3** | AI-assisted explanations grounded in graph context |

## Requirements (summary)

| ID | Requirement | Verified by |
|----|-------------|-------------|
| FR-01 | Public GitHub URL | `test_github_ingestion.py`, `test_api.py` |
| FR-03 | Import graph | `test_parser.py`, `test_graph.py`, `test_pipeline.py` |
| FR-04–06 | PageRank, betweenness, cycles | `test_scoring.py`, `test_cycles.py` |
| FR-07 | REST JSON | `test_api.py`, `test_serialize.py` |
| FR-09 | Impact on demand | `test_impact.py`, `test_api.py` |
| FR-14 | Benchmark CLI | `test_benchmark.py` |

Full FR/NFR tables: historical [SRS_ProjectPlan.md](../SRS_ProjectPlan.md).

## Interview guide

**Architecture**

- Why modular monolith? → [architecture/README.md](../architecture/README.md)
- Why PostgreSQL not Neo4j? → compute in NetworkX, persist relationally
- Async jobs? → 202 + poll; see [backend/api.md](../backend/api.md#planned-endpoints)

**Algorithms**

- PageRank on code: importance flows along import edges (importer → imported)
- Betweenness: bridge files on shortest paths
- Criticality: `0.6 * norm(PR) + 0.4 * norm(BT)`
- Cycles: `nx.simple_cycles` + rotation normalization
- Impact: reverse reachability (`predecessors`, `ancestors`, hop layers)

**System design**

- Scale parse: parallelize per-file AST (independent)
- Scale jobs: Celery + Redis
- File vs function nodes: file-level proves the pipeline; calls need resolution

**Static analysis limits**

- Dynamic imports, `getattr`, `importlib` may be missed
- `ast` chosen over Tree-sitter for Python-only accuracy

## Risk register

| Risk | Mitigation |
|------|------------|
| Import resolution breaks on complex projects | Graceful skip; mark unresolved |
| Phase 1 slips | File-level only; don't expand scope |
| Large graph UI slow | Filter by criticality; top-N nodes |
| Scope creep to v2/v3 | Refer to version ladder |

## Weekly check-in

1. Did I meet this week's milestone?
2. Am I building MVP scope?
3. Is my blocker technical or avoidance?
4. What one thing blocks all future weeks if skipped?

---

*Consolidated from Roadmap.md and SRS_ProjectPlan.md. Detailed week-by-week tasks: [Roadmap.md](../Roadmap.md).*

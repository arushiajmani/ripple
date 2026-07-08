# Ripple

Ripple is a code dependency analysis platform that parses Python repositories, constructs dependency graphs, and identifies critical files, architectural bottlenecks, and change impact paths.

## Features

**Shipped:** AST parser · repo batch parsing · file-level import graph · cycle detection · PageRank / betweenness criticality · on-demand impact analysis · zip + GitHub ingestion · sync REST API · PostgreSQL persistence · pipeline JSON export · benchmark CLI

**Planned:** Interactive graph UI · async analyze (202 + poll) · `GET /api/graph` / `/api/repos`

Detail: [docs/backend/](docs/backend/) · [product roadmap](docs/product/README.md)

## Architecture

```
Repository → parse_repository() → FileAnalysis
    → GraphBuilder → GraphResult → GraphAdapter → nx.DiGraph
    → CycleDetector + AlgorithmEngine → PipelineResult
    → PostgreSQL + AnalysisStore → ImpactAnalyzer (on demand)
```

Full diagrams and decisions: [docs/architecture/](docs/architecture/README.md)

## Quick start

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Backend  | http://localhost:8000 |
| Frontend | http://localhost:5173 |

Health: `curl http://localhost:8000/health` → `{"status":"ok"}`

Local dev, database, and first commands: [docs/getting-started/](docs/getting-started/README.md)

## Tech stack

Python 3.11 · FastAPI · PostgreSQL · SQLAlchemy · NetworkX · React · Vite · Cytoscape.js · Docker

## Documentation

| | |
|---|---|
| [Documentation hub](docs/README.md) | Start here |
| [Getting started](docs/getting-started/README.md) | Setup and project layout |
| [Backend modules](docs/backend/) | Parser, graph, pipeline, API, … |
| [Architecture](docs/architecture/README.md) | Design and data flow |
| [CLI reference](docs/development/cli-reference.md) | All commands |
| [Reference](docs/reference/) | API schema, JSON, DB, glossary |
| [Examples](docs/examples/) | mini_repo, click, flask, django |
| [Product](docs/product/README.md) | Roadmap and interview prep |

## Try it

From `backend/` with venv active:

```bash
python -m app.pipeline tests/fixtures/mini_repo
python -m app.benchmark --repo tests/fixtures/mini_repo
pytest tests/ -v
```

Walkthrough: [docs/examples/mini_repo.md](docs/examples/mini_repo.md)

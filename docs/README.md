# Ripple Documentation

Ripple is a Python dependency analysis platform: parse repositories, build import graphs, score architectural criticality, and compute change impact.

## Start here

| I want to… | Go to |
|------------|-------|
| Run the project locally | [Getting started](getting-started/README.md) |
| Understand a backend module | [Backend](backend/) |
| Understand a frontend feature | [Frontend](frontend/) |
| See architecture decisions | [Architecture](architecture/README.md) |
| API resource model (repo vs job) | [API resources](architecture/api-resources.md) |
| Copy-paste commands | [CLI reference](development/cli-reference.md) |
| Look up schemas or terms | [Reference](reference/) |
| Walk through a real repo | [Examples](examples/) |
| Roadmap, requirements, interviews | [Product](product/README.md) |
| Implement repo-centric API | [Repo-centric API plan](product/repo-centric-api-plan.md) |
| Why two POST analyze endpoints? | [API — Two ways to analyze](backend/api.md#two-ways-to-analyze) |

## Frontend features

| Doc | What it covers |
|-----|----------------|
| [Product design](frontend/product-design.md) | Vision, personas, IA, API gaps |
| [Design system](frontend/design-system.md) | Tokens, primitives, data colors |
| [API client](frontend/api-client.md) | Fetch layer, React Query, endpoint mapping |
| [Import flow](frontend/import-flow.md) | Landing, upload, processing |
| [Workspace shell](frontend/workspace-shell.md) | Layout, nav, routing |
| [Overview](frontend/overview.md) | Repository story, health heuristics |
| [Dependency graph](frontend/dependency-graph.md) | Cytoscape flagship view |
| [File detail](frontend/file-detail.md) | Selected file side panel |
| [Critical files](frontend/critical-files.md) | Ranked criticality table |
| [State management](frontend/state-management.md) | Query cache, selection context |

## Backend modules

| Doc | What it covers |
|-----|----------------|
| [Parser](backend/parser.md) | AST parsing, import resolution, `parse_repository` |
| [Graph builder](backend/graph-builder.md) | `GraphBuilder`, `GraphAdapter`, cycles, scoring, impact |
| [Pipeline](backend/pipeline.md) | `AnalysisPipeline`, JSON export, benchmark CLI |
| [Ingestion](backend/ingestion.md) | Zip upload, GitHub clone, `IngestionService` |
| [API](backend/api.md) | REST endpoints (current + [planned repo-centric API](product/repo-centric-api-plan.md)) |
| [Persistence](backend/persistence.md) | PostgreSQL schema, Alembic, `persist.py` |

## Reference

| Doc | What it covers |
|-----|----------------|
| [API schema](reference/api-schema.md) | Request/response shapes, status codes |
| [JSON format](reference/json-format.md) | Pipeline export document layout |
| [Database schema](reference/database-schema.md) | Tables, indexes, example queries |
| [Glossary](reference/glossary.md) | Terms used across Ripple |
| [Performance metrics](reference/performance-metrics.md) | Pipeline stages, benchmark output |

## Examples

| Repo | Notes |
|------|-------|
| [mini_repo](examples/mini_repo.md) | Built-in cyclic fixture — full walkthrough |
| [click](examples/click.md) | Analyze pallets/click |
| [django](examples/django.md) | Large-repo benchmark target |
| [flask](examples/flask.md) | Medium-repo example |

## Documentation lifecycle

Every [backend module doc](backend/) starts with a standard header:

- **Status** — Implemented, Partial, or Planned
- **Owner** — Backend (frontend docs use `Frontend`)
- **Last Updated** — date of last substantive edit
- **Related components**, **Tests**, **Source files**

When you change a module, update its doc header date and the relevant reference pages.

## Legacy paths

Older single-file docs redirect here:

- [learn.md](learn.md) — study guide (split into `backend/` + `architecture/`)
- [Architecture.md](Architecture.md) — architecture (now `architecture/` + `reference/`)
- [Roadmap.md](Roadmap.md) — now `product/README.md`
- [SRS_ProjectPlan.md](SRS_ProjectPlan.md) — now `product/README.md` + `reference/`

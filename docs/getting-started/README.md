# Getting Started

## Prerequisites

- **Docker & Docker Compose** — full stack
- **Python 3.11+** — local backend / parser development
- **git** — GitHub URL ingestion (`git clone`, `git ls-remote`)
- **Node.js 20+** — local frontend development

## Quick start (Docker)

From the project root:

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Backend  | http://localhost:8000 |
| Frontend | http://localhost:5173 |

Health check: `GET http://localhost:8000/health` → `{"status": "ok"}`

Interactive API docs: http://localhost:8000/docs

## Local backend (no Docker)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Local frontend

```bash
cd frontend
npm install
npm run dev
```

See also the upstream [Vite + React template README](../frontend/README.md).

## Database (schema only)

Run from the **project root** unless noted.

```bash
docker compose up -d db
cd backend && source .venv/bin/activate && alembic upgrade head
docker compose exec db psql -U ripple -d ripple -c '\dt'
```

Expected: 8 SRS tables + `alembic_version` (`version_num = 63207e50c596`).

Full Alembic and `psql` troubleshooting: [CLI reference — Database operations](../development/cli-reference.md#database-operations).

## Project structure

```text
ripple/
├── backend/
│   ├── alembic/                 # Migrations
│   ├── app/
│   │   ├── parser/              # AST parsing
│   │   ├── graph/               # Graph builder + algorithms
│   │   ├── pipeline/            # Orchestration + JSON export
│   │   ├── ingestion/           # Zip + GitHub
│   │   ├── api/                 # FastAPI routes
│   │   ├── db/                  # ORM + persist/load
│   │   └── benchmark/           # Per-stage timing CLI
│   └── tests/
│       └── fixtures/mini_repo/  # Shared cyclic fixture
├── frontend/
├── docs/                        # This documentation tree
└── docker-compose.yml
```

Detail and rationale: [Architecture](../architecture/README.md).

## First commands to try

From `backend/` with venv active:

```bash
python -m app.parser.cli tests/fixtures/mini_repo
python -m app.pipeline tests/fixtures/mini_repo
python -m app.benchmark --repo tests/fixtures/mini_repo
pytest tests/ -v
```

Walkthrough with expected output: [examples/mini_repo.md](../examples/mini_repo.md).

Full command sheet: [development/cli-reference.md](../development/cli-reference.md).

## Next steps

- [Backend parser](../backend/parser.md) — how imports are resolved
- [Backend pipeline](../backend/pipeline.md) — end-to-end analysis
- [Backend API](../backend/api.md) — zip/GitHub upload over HTTP
- [Examples](../examples/) — analyze real open-source repos

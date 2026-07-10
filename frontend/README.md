# Ripple Frontend

React workspace for exploring analyzed Python repositories.

## Quick start

```bash
# Terminal 1 — backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — API requests proxy to http://localhost:8000.

Or with Docker:

```bash
docker compose up --build
# Frontend http://localhost:5173 · Backend http://localhost:8000
```

## Documentation

Feature docs mirror the backend layout: [docs/frontend/](../docs/frontend/README.md)

| Doc | Topic |
|-----|-------|
| [product-design.md](../docs/frontend/product-design.md) | Vision, IA, API gaps |
| [design-system.md](../docs/frontend/design-system.md) | Tokens, primitives |
| [api-client.md](../docs/frontend/api-client.md) | Fetch + React Query |
| [import-flow.md](../docs/frontend/import-flow.md) | Landing, upload |
| [workspace-shell.md](../docs/frontend/workspace-shell.md) | Nav, routing |
| [overview.md](../docs/frontend/overview.md) | Repository story |
| [dependency-graph.md](../docs/frontend/dependency-graph.md) | Cytoscape graph |
| [file-detail.md](../docs/frontend/file-detail.md) | File side panel |
| [critical-files.md](../docs/frontend/critical-files.md) | Ranked table |

## Stack

- React 19 + Vite 8
- React Router 7
- TanStack Query
- Cytoscape.js + fcose layout
- Lucide icons

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Dev server (port 5173) |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run preview` | Preview production build |

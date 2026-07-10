# Frontend

Ripple's React workspace — repository import, exploration, and dependency intelligence.

| Doc | Feature |
|-----|---------|
| [product-design.md](product-design.md) | Vision, personas, IA, page map, API gaps |
| [design-system.md](design-system.md) | Tokens, typography, primitives |
| [api-client.md](api-client.md) | HTTP client, React Query, backend mapping |
| [state-management.md](state-management.md) | Server vs UI state, selection, cache keys |
| [import-flow.md](import-flow.md) | Landing, import, processing |
| [workspace-shell.md](workspace-shell.md) | Layout, navigation, routing |
| [overview.md](overview.md) | Repository overview and health narrative |
| [dependency-graph.md](dependency-graph.md) | Cytoscape graph — flagship experience |
| [file-detail.md](file-detail.md) | Selected file side panel |
| [critical-files.md](critical-files.md) | Ranked criticality table |

Each doc uses the [documentation lifecycle](../README.md#documentation-lifecycle) header (status, owner, tests, source files).

**Backend contract:** [backend/api.md](../backend/api.md) · [reference/api-schema.md](../reference/api-schema.md)

**Commands:** run from `frontend/` — `npm run dev` (Vite on port 5173, proxies `/api` to backend)

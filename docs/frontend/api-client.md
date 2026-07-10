# API Client

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [backend/api.md](../backend/api.md) · [reference/api-schema.md](../reference/api-schema.md) · [state-management.md](state-management.md)

**Source files:** `frontend/src/api/client.js` · `frontend/src/api/repos.js` · `frontend/src/api/graph.js`

---

## Overview

All HTTP calls go through a thin `fetch` wrapper. React Query caches server state. The UI uses **Repository Analysis** only — never `POST /api/analyze`.

```text
Component → hook (useQuery / useMutation) → api/repos.js | api/graph.js → client.js → /api/…
```

## Base URL

| Environment | Base |
|-------------|------|
| Development | `""` (relative) — Vite proxies `/api` → `http://localhost:8000` |
| Production | `VITE_API_URL` or same-origin reverse proxy |

Configured in `vite.config.js`:

```javascript
proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
```

## Endpoints used

| Function | Method | Path | Response use |
|----------|--------|------|--------------|
| `analyzeRepo` | POST | `/api/repos/analyze` | `repo_id` → navigate to workspace |
| `listRepos` | GET | `/api/repos` | Landing recent list |
| `getRepo` | GET | `/api/repos/{repo_id}` | Overview, header |
| `getRepoGraph` | GET | `/api/repos/{repo_id}/graph` | Graph, cycles (embedded) |
| `getRepoScores` | GET | `/api/repos/{repo_id}/scores` | Critical files, graph styling |
| `getRepoImpact` | GET | `/api/repos/{repo_id}/impact?file=` | Impact view (MVP-2) |

### Analyze request

`multipart/form-data` — **either** `file` (zip) **or** `github_url`, never both.

```javascript
const form = new FormData()
form.append('file', zipFile)
// or
form.append('github_url', 'https://github.com/owner/repo')
await analyzeRepo(form)
```

### Error handling

All error bodies: `{ "detail": "..." }`. `client.js` throws `ApiError` with `status` and `detail`.

| Status | Typical cause |
|--------|---------------|
| 400 | Both/neither input, empty zip, no Python files |
| 404 | Unknown repo, file not in graph |
| 502 | Git clone failed |

## React Query keys

```javascript
['repos']
['repos', repoId]
['repos', repoId, 'graph']
['repos', repoId, 'scores']
['repos', repoId, 'impact', filePath]  // enabled when filePath set
```

### Cache policy

| Query | staleTime |
|-------|-----------|
| repos list | 30s |
| repo detail, graph, scores | 5min |
| impact | 10min |

Invalidate `['repos', repoId]` subtree after re-analyze (MVP-3).

## Client-side joins

Graph nodes are path strings; scores are a separate list. `useRepoGraph` merges:

```javascript
scoresByPath[file_path] → { pagerank, betweenness, criticality, in_degree, out_degree }
```

Dependents / dependencies for File Detail are derived from `graph.edges` — no extra API.

## Not used in UI

| Endpoint | Reason |
|----------|--------|
| `POST /api/analyze` | Fat JSON — CLI/scripts |
| `GET /health` | Optional dev indicator only |

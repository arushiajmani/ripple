# Dependency Graph

| | |
|---|---|
| **Status** | Implemented (MVP-1 core interactions) |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [api-client.md](api-client.md) · [file-detail.md](file-detail.md) · [state-management.md](state-management.md)

**Source files:** `frontend/src/routes/workspace/GraphPage.jsx` · `frontend/src/components/domain/GraphCanvas.jsx` · `GraphToolbar.jsx` · `GraphLegend.jsx` · `frontend/src/lib/graph/`

---

## Question answered

**How is everything connected?**

Ripple's flagship experience.

## Data

Parallel fetch via `useRepoGraph`:

- `GET /api/repos/{repo_id}/graph` — `nodes`, `edges`, `cycles`
- `GET /api/repos/{repo_id}/scores` — joined by `file_path`

## Layout

Split pane: canvas (~70%) + optional toolbar strip. File Detail opens as workspace-level side panel on node click.

## Cytoscape configuration

| Property | Mapping |
|----------|---------|
| Node label | Short path (last segment) |
| Node size | `criticality` (min/max clamped) |
| Node color | Risk band from criticality |
| Edge | `#CAD2C5`, arrow, importer → imported |
| Layout | `fcose` force-directed |

Built in `lib/graph/buildCyElements.js`.

## Interactions (MVP-1)

| Action | Behavior |
|--------|----------|
| Pan / zoom | Native cytoscape + toolbar fit |
| Click node | `setSelectedFilePath` → File Detail |
| Hover | Tooltip: full path, criticality, degrees |
| Show dependencies | Highlight successors (out-edges) |
| Show dependents | Highlight predecessors (in-edges) |
| Focus mode | Hide nodes not in 1-hop neighborhood |
| Search filter | Text filter on path |
| Min criticality | Slider hides low-score nodes |

## Highlight modes

`lib/graph/highlights.js` — classes on cytoscape elements:

- `.highlighted` — accent border
- `.dimmed` — reduced opacity
- `.target` — selected file ring

## URL deep link

`/repos/:repoId/graph?focus=path/to/file.py`

On load: select node, center viewport, open File Detail.

## Performance

Large repos (500+ nodes): default `minCriticality` filter excludes bottom quartile. Warning banner when `node_count > 200`.

**Future API:** `GET /graph?min_criticality=&limit=` — not shipped; client-side only today.

## Legend

`GraphLegend` explains size = criticality, color = risk band, edge direction.

## MVP-2 additions

- Package collapse (group by first path segment)
- Impact blast-radius overlay from Impact view
- Cycle subgraph highlight from Cycles view

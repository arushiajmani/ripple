# Workspace Shell

| | |
|---|---|
| **Status** | Implemented (MVP-1 nav); MVP-2 routes stubbed |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [product-design.md](product-design.md) · [state-management.md](state-management.md)

**Source files:** `frontend/src/routes/workspace/WorkspaceLayout.jsx` · `frontend/src/components/layout/`

---

## Question answered

**How do I navigate a analyzed repository without losing context?**

## Route structure

```text
/repos/:repoId                 → redirect to overview
/repos/:repoId/overview
/repos/:repoId/graph
/repos/:repoId/critical
/repos/:repoId/impact          (MVP-2)
/repos/:repoId/cycles          (MVP-2)
/repos/:repoId/explorer        (MVP-2)
/repos/:repoId/architecture    (MVP-2)
/repos/:repoId/settings        (MVP-3)
```

Deep links: `/repos/:repoId/graph?focus=myapp/models.py`

## Layout

```text
┌──────────────────────────────────────────────────────────┐
│ Header: [← Repos]  name · N files · analyzed_at  [⌘K]  │
├────────────┬─────────────────────────────────────────────┤
│ Sidebar    │  Page content (Outlet)                      │
│ Overview   │                                             │
│ Graph      │                                             │
│ Critical   │                                             │
│ …          │                                             │
└────────────┴─────────────────────────────────────────────┘
                              │
                    FileDetailPanel (overlay, right)
```

`WorkspaceShell` provides sidebar + header. `SelectionProvider` wraps outlet.

## Header

Data from `GET /api/repos/{repo_id}`:

- Display name (`owner/repo` or zip name)
- `summary.file_count`
- `analyzed_at` (relative time)

Actions: back to landing; command palette (MVP-2).

## Sidebar navigation

Order follows the understanding funnel (see [product-design.md](product-design.md)).

MVP-1 active routes: Overview, Dependency Graph, Critical Files.

MVP-2 items render as disabled or hidden until implemented.

## Selection propagation

`SelectionContext` at layout level. Any child can:

```javascript
const { selectedFilePath, setSelectedFilePath } = useSelection()
```

`FileDetailPanel` renders when `selectedFilePath !== null`.

## Responsive

| Breakpoint | Behavior |
|------------|----------|
| `< 1024px` | Collapsible sidebar (hamburger) |
| `< 640px` | Bottom sheet for File Detail |

Desktop-first; see [product-design.md](product-design.md).

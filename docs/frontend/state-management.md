# State Management

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [api-client.md](api-client.md) · [workspace-shell.md](workspace-shell.md) · [file-detail.md](file-detail.md)

**Source files:** `frontend/src/context/SelectionContext.jsx` · `frontend/src/hooks/`

---

## Three layers

```text
Server state (TanStack Query)     ← GET responses, mutations
Workspace UI state (Context)      ← selection, panel, graph filters
Ephemeral local state (useState)  ← forms, modals, sort column
```

No Redux. No global store beyond React Query cache + one selection context.

## Server state

Owned by `@tanstack/react-query`. Hooks:

| Hook | Query key | Notes |
|------|-----------|-------|
| `useRepos` | `['repos']` | List |
| `useRepo` | `['repos', id]` | Detail |
| `useRepoGraph` | graph + scores | Parallel fetch, merged map |
| `useRepoScores` | `['repos', id, 'scores']` | Standalone table |
| `useImpact` | `['repos', id, 'impact', file]` | Lazy, MVP-2 |

`QueryClientProvider` wraps the app in `main.jsx`.

## Selection context

`SelectionContext` lives at `WorkspaceLayout` level.

| State | Type | Propagates to |
|-------|------|---------------|
| `selectedFilePath` | `string \| null` | File Detail panel, graph selection |
| `setSelectedFilePath` | function | Graph click, table row, explorer |

```text
Graph click ──┐
Table row  ──┼──► setSelectedFilePath ──► FileDetailPanel
URL ?file=   ──┘
```

Impact page (MVP-2) syncs `?file=` query param with selection.

## Graph UI state

Kept **inside** `GraphCanvas` + `useGraphHighlight` — not in React state for the Cytoscape instance.

| State | Location |
|-------|----------|
| Cytoscape ref | `useRef` in GraphCanvas |
| Highlight mode | `deps` \| `dependents` \| `impact` \| `cycle` \| null |
| Filters | min criticality, hide leaves |

Imperative cytoscape API for performance; React re-renders only on selection/filter changes.

## Folder structure

```text
src/
├── api/           # fetch + endpoint functions
├── hooks/         # React Query wrappers
├── context/       # SelectionContext
├── lib/           # pure derivations (health, cy elements, format)
├── components/
│   ├── ui/
│   ├── layout/
│   └── domain/
└── routes/
```

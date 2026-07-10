# Critical Files

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [api-client.md](api-client.md) · [file-detail.md](file-detail.md) · [overview.md](overview.md)

**Source files:** `frontend/src/routes/workspace/CriticalFilesPage.jsx` · `frontend/src/components/domain/CriticalFileRow.jsx`

---

## Question answered

**Which files matter the most?**

## Data

`GET /api/repos/{repo_id}/scores` — ordered list, `scores[0]` most critical.

API field `criticality` maps from DB `composite_score`.

## UI

Sortable table (default: API order = criticality desc):

| Column | Field |
|--------|-------|
| File | `file_path` |
| Criticality | `criticality` + bar |
| PageRank | `pagerank` |
| Betweenness | `betweenness` |
| Imported by | `in_degree` |
| Imports | `out_degree` |

Row click → `setSelectedFilePath` + File Detail panel.

Secondary action per row: **View in graph** → navigate with `?focus=`.

## UX rationale

Table beats graph for **ranking comparison**. Engineers scanning a new repo want a sorted list, not spatial layout.

Overview shows top 5; this page is the full ranked inventory.

## Empty / loading

`Skeleton` rows while loading. `EmptyState` if scores array empty (should not happen for completed analysis).

## Formatting

Scores displayed to 4 decimal places (matches API rounding). Paths use mono font, truncated with full path in `title` tooltip.

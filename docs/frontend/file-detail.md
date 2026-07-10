# File Detail

| | |
|---|---|
| **Status** | Implemented (graph-derived data) |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [dependency-graph.md](dependency-graph.md) · [state-management.md](state-management.md) · [api-client.md](api-client.md)

**Source files:** `frontend/src/components/domain/FileDetailPanel.jsx`

---

## Question answered

**Why is this file important? What depends on it? What does it depend on? How risky is modifying it?**

Never dump raw JSON.

## Trigger

`selectedFilePath` from `SelectionContext` — set by graph click, critical files table, overview list, URL `?focus=`.

Panel slides from right (`Panel` primitive). `Esc` or close button clears selection.

## Data (no extra API in MVP-1)

| Section | Source |
|---------|--------|
| Path | `selectedFilePath` |
| Metrics | scores map: pagerank, betweenness, criticality, in/out degree |
| Rank | index in scores list + 1 |
| Dependencies | `edges` where `source === file` → targets |
| Dependents | `edges` where `target === file` → sources |
| Role heuristic | path patterns (`models`, `utils`, `__init__`) + metrics |

## Sections

1. **Header** — mono path, syntax badge placeholder (needs `/files` API)
2. **Why important** — prose from rank + in_degree + criticality band
3. **Metrics** — four `MetricBlock`s
4. **Dependencies** — linked list (click → re-select)
5. **Dependents** — linked list
6. **Actions** — View in graph; Analyze impact (MVP-2 → `/impact?file=`)

## Risk bands

| criticality | Label |
|-------------|-------|
| ≥ 0.7 | High |
| ≥ 0.4 | Medium |
| < 0.4 | Low |

## Backend gap

Rich parser fields (`classes`, `functions`, `line_count`, `syntax_error`) require:

```http
GET /api/repos/{repo_id}/files/{path}
```

Until shipped, File Detail uses graph topology only. Document in UI as "import relationships" not full file analysis.

## Accessibility

`role="complementary"`, `aria-label="File details"`, labelled metric sections. Selection changes announced via `aria-live="polite"`.

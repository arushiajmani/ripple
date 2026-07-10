# Overview

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [api-client.md](api-client.md) · [critical-files.md](critical-files.md) · [dependency-graph.md](dependency-graph.md)

**Source files:** `frontend/src/routes/workspace/OverviewPage.jsx` · `frontend/src/components/domain/HealthSummary.jsx` · `KeyFindings.jsx` · `frontend/src/lib/health/computeHealth.js`

---

## Question answered

**Where should I start in this codebase?**

## Data sources

| Block | API |
|-------|-----|
| Repository summary | `GET /api/repos/{repo_id}` |
| Top critical files | `GET /api/repos/{repo_id}/scores` (slice 0–5) |
| Cycle presence | `graph` prefetch or scores + detail `summary.cycle_count` |

No KPI card grid — narrative layout top to bottom.

## Page sections

### 1. Repository summary

Name, source badge (github / zip), counts: files, edges, cycles. From `summary` + `repository`.

### 2. Architecture health

`HealthSummary` — derived client-side in `computeHealth.js`:

| Signal | Rule |
|--------|------|
| Cycles | `cycle_count > 0` → warning |
| Density | `statistics.graph_density > 0.05` → note |
| Concentration | top file `criticality > 0.8` → note |

Overall band: healthy / attention / at-risk (text + color, never color alone).

### 3. Key findings

`KeyFindings` — 2–4 plain-language bullets from health + top scores + cycles.

Examples:

- "3 circular import loops detected — start with Cycles view."
- "`myapp/models.py` is the most critical file (imported by 12 modules)."

### 4. Most critical files

Mini list (top 5) with criticality bar. Row click → selection + File Detail.

### 5. Largest risks

Cycles count + highest-betweenness file if notable.

### 6. Quick navigation

Links to Graph, Critical Files, Cycles (when MVP-2).

## UX rationale

Overview tells a **story** before dropping users into the graph. New team members get orientation; architects get health signals without chart overload.

Architecture charts move to dedicated Architecture page (MVP-2) — not duplicated here.

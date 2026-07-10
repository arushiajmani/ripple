# Product Design

| | |
|---|---|
| **Status** | Implemented (MVP-1); MVP-2/3 planned |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [workspace-shell.md](workspace-shell.md) · [backend/api.md](../backend/api.md) · [product/README.md](../product/README.md)

---

## What Ripple answers

Ripple is an **engineering intelligence platform** for Python repositories — not a CRUD dashboard, chatbot, or admin panel.

Every screen answers developer questions:

| Question | Primary view |
|----------|--------------|
| Where should I start? | Overview |
| Which files matter most? | Critical Files, Overview |
| What breaks if I modify this? | Impact Analysis (MVP-2), File Detail |
| Why is this file important? | File Detail |
| Where are architectural bottlenecks? | Architecture (MVP-2), Overview |
| Which modules are overly coupled? | Cycles (MVP-2), Graph |
| How healthy is this repository? | Overview, Architecture |

## Application flow

```text
Landing → Import (GitHub / ZIP) → Processing → Repository Workspace → Exploration
```

The **repository workspace** (`/repos/:repoId`) is mission control. Primary navigation:

1. Overview
2. Architecture *(MVP-2)*
3. Dependency Graph
4. Critical Files
5. Impact Analysis *(MVP-2)*
6. Cycles *(MVP-2)*
7. Repository Explorer *(MVP-2)*
8. Settings *(MVP-3)*

**Search** is a global command palette overlay (`⌘K`) — MVP-2.

## User personas

| Persona | Goal | Primary workflow |
|---------|------|------------------|
| **Jordan** (new team member) | Orient in unfamiliar code | Overview → Critical Files → Graph |
| **Sam** (refactoring engineer) | Safe module changes | Select file → Impact → Graph highlight |
| **Alex** (tech lead) | Assess structural health | Overview health → Cycles → Architecture charts |
| **Riley** (OSS explorer) | Quick repo analysis | GitHub import → workspace |

## Visual identity — Warm Paper × Forest

Calm, precise, craftsmanship. Inspired by Notion readability, Linear polish, Vercel restraint, GitHub density.

| Token | Value |
|-------|-------|
| Background | `#FDFBF7` |
| Surface | `#FFFFFF` |
| Primary text | `#2F3E46` |
| Secondary text | `#5B6B73` |
| Primary accent | `#52796F` |
| Secondary accent | `#84A98C` |
| Border | `#E9E5DD` |
| Success / Warning / Error | `#588157` / `#D4A017` / `#C14953` |

Avoid: neon colors, loud gradients, glassmorphism, generic admin templates.

Detail: [design-system.md](design-system.md).

## Information architecture

```text
App
├── Landing (/)
├── Import (/import)
├── Processing (/processing/:repoId)
└── Workspace (/repos/:repoId/…)
    ├── overview
    ├── graph
    ├── critical
    ├── impact      (MVP-2)
    ├── cycles      (MVP-2)
    ├── explorer    (MVP-2)
    ├── architecture (MVP-2)
    └── settings    (MVP-3)
```

**Context model:** `repo_id` scopes all workspace data. `selectedFilePath` propagates across views via `SelectionContext`.

## API mapping (shipped only)

| UI need | Endpoint |
|---------|----------|
| Import | `POST /api/repos/analyze` |
| Recent repos | `GET /api/repos` |
| Repo summary | `GET /api/repos/{repo_id}` |
| Graph + cycles | `GET /api/repos/{repo_id}/graph` |
| Criticality ranks | `GET /api/repos/{repo_id}/scores` |
| Blast radius | `GET /api/repos/{repo_id}/impact?file=` |

**Do not use** `POST /api/analyze` (fat JSON) in the UI — scripts only.

## Identified backend gaps

| Gap | UI workaround | Proposed contract |
|-----|---------------|-------------------|
| No per-file metadata | Graph-derived deps in File Detail | `GET /api/repos/{id}/files` |
| Sync analyze only | Spinner on POST | `202` + `GET /api/jobs/{job_id}` |
| No re-analyze source | Re-import from landing | `source_ref` on repo detail |
| No CORS | Vite dev proxy | `CORSMiddleware` or proxy in prod |

Await backend approval before implementing workarounds that invent APIs.

## Delivery phases

| Phase | Scope |
|-------|-------|
| **MVP-1** ✓ | Landing, import, processing, workspace shell, overview, graph, file detail, critical files |
| **MVP-2** | Impact, cycles, explorer, command palette, architecture charts |
| **MVP-3** | Settings, re-analyze, responsive polish, a11y audit |

## Responsive & accessibility

- **Desktop-first** — graph exploration targets engineers at workstations
- **Mobile** — landing, import, overview, critical list; graph shows simplified fallback
- **WCAG 2.1 AA** — color + label for risk bands, keyboard nav, `aria-live` for selection
- **`prefers-reduced-motion`** — disable layout animations

Detail: [state-management.md](state-management.md) · [design-system.md](design-system.md).

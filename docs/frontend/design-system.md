# Design System

| | |
|---|---|
| **Status** | Implemented (MVP-1 primitives) |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [product-design.md](product-design.md) · [workspace-shell.md](workspace-shell.md)

**Source files:** `frontend/src/styles/tokens.css` · `frontend/src/components/ui/`

---

## Philosophy

Reusable primitives with a timeless, premium feel. Warm off-white backgrounds, thin borders over heavy shadows, 12–16px radius, muted forest accents for data — not decoration.

## Tokens

Defined in `src/styles/tokens.css` and consumed via CSS custom properties.

### Color

| Variable | Value | Use |
|----------|-------|-----|
| `--color-bg` | `#FDFBF7` | Page background |
| `--color-surface` | `#FFFFFF` | Cards, panels |
| `--color-text` | `#2F3E46` | Primary text |
| `--color-text-muted` | `#5B6B73` | Secondary text |
| `--color-accent` | `#52796F` | Primary actions, links |
| `--color-accent-light` | `#84A98C` | Low-risk data viz |
| `--color-accent-muted` | `#CAD2C5` | Graph edges, subtle fills |
| `--color-border` | `#E9E5DD` | Dividers |
| `--color-hover` | `#F5F1EA` | Interactive hover |
| `--color-selection` | `rgba(82,121,111,0.12)` | Selected rows/nodes |
| `--color-success` | `#588157` | Healthy states |
| `--color-warning` | `#D4A017` | Cycles, medium risk |
| `--color-error` | `#C14953` | Errors, high criticality |

### Typography

| Level | Size | Weight |
|-------|------|--------|
| Display | 1.5rem | 600 |
| Title | 1.25rem | 600 |
| Section | 1.125rem | 500 |
| Body | 1rem | 400 |
| Caption | 0.875rem | 400 |
| Mono | 0.875rem | — (JetBrains Mono, fallback ui-monospace) |

### Spacing & shape

- Base unit: 4px (`--space-1` … `--space-8`)
- Radius: `--radius-sm` 8px, `--radius-md` 12px, `--radius-lg` 16px
- Shadows: `--shadow-sm`, `--shadow-md` (subtle)
- Motion: `--duration-fast` 120ms, `--duration-normal` 200ms

## Semantic data colors

Graph and badges map **meaning**, not rainbow decoration:

| Meaning | Treatment |
|---------|-----------|
| Low criticality | `--color-accent-light` → `--color-accent-muted` |
| Medium | Warning at low opacity |
| High | `--color-error` sparingly |
| Cycle / warning | `--color-warning` |
| Selection | `--color-selection` + accent border |

Always pair color with a text label for accessibility.

## Component inventory

### Primitives (`components/ui/`)

| Component | Variants / notes |
|-----------|------------------|
| `Button` | primary, secondary, ghost, danger; sm/md |
| `Card` | default, interactive (hover) |
| `Panel` | side panel shell |
| `Badge` | default, success, warning, error, muted |
| `MetricBlock` | label + value + hint |
| `StatusIndicator` | dot + text (not color alone) |
| `Input` | text, file |
| `Table` | sortable header support |
| `Skeleton` | loading placeholder |
| `EmptyState` | icon + title + description + action |
| `Progress` | indeterminate bar |
| `Kbd` | keyboard hint chip |

### Layout (`components/layout/`)

| Component | Role |
|-----------|------|
| `AppShell` | Landing / marketing width |
| `WorkspaceShell` | Sidebar + header + outlet |
| `Sidebar` | Primary workspace nav |
| `Header` | Repo context bar |
| `PageHeader` | Title + question subtitle |

### Domain (`components/domain/`)

See feature docs: [overview.md](overview.md), [dependency-graph.md](dependency-graph.md), [file-detail.md](file-detail.md), [critical-files.md](critical-files.md), [import-flow.md](import-flow.md).

## Icons

[Lucide React](https://lucide.dev/) — 16–20px, stroke 1.75, functional only.

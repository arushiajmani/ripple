# Import Flow

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Frontend |
| **Last Updated** | 2026-07-10 |

**Related:** [api-client.md](api-client.md) · [workspace-shell.md](workspace-shell.md) · [backend/ingestion.md](../backend/ingestion.md)

**Source files:** `frontend/src/routes/LandingPage.jsx` · `ImportPage.jsx` · `ProcessingPage.jsx` · `frontend/src/components/domain/ImportForm.jsx` · `RepoCard.jsx` · `ProcessingView.jsx`

---

## Question answered

**How do I bring a Python codebase into Ripple?**

## Routes

| Route | Purpose |
|-------|---------|
| `/` | Landing — hero, CTA, recent repositories |
| `/import` | GitHub URL or ZIP upload form |
| `/processing/:repoId` | Wait state after analyze POST |

## Landing (`/`)

- Hero value prop + **Analyze a repository** CTA → `/import`
- **Recent repositories** from `GET /api/repos`
- `RepoCard`: name, source badge, file/cycle counts, `analyzed_at`
- Empty state when no repos analyzed yet

## Import (`/import`)

`ImportForm` with tabs:

| Tab | Input | API field |
|-----|-------|-----------|
| GitHub | URL text field | `github_url` |
| ZIP | File input | `file` |

Validation mirrors backend: exactly one input. Submit calls `POST /api/repos/analyze` via `useAnalyzeRepo` mutation.

On success → `navigate(/processing/${repo_id})`.

On error → inline alert with `detail` from `ApiError`.

## Processing (`/processing/:repoId`)

**Backend reality:** analysis is synchronous today; POST blocks until `status: complete`.

UI shows:

- Indeterminate `Progress` bar
- Honest stage copy (ingest → parse → graph → score)
- On mutation success (already complete) → immediate redirect to `/repos/:repoId`
- On error → link back to import with message

**Future:** when async ships (`202` + poll `GET /api/jobs/{job_id}`), same route polls until complete.

## UX decisions

| Decision | Rationale |
|----------|-----------|
| Separate import page | Focused flow; landing stays lightweight |
| No fake percentages | Sync POST has no progress API |
| Slim POST only | UI loads graph on demand in workspace |

## Error recovery

| Error | User action |
|-------|-------------|
| 400 invalid zip / URL | Fix input, retry |
| 404 GitHub not found | Check URL visibility |
| 502 clone failed | Retry or use ZIP |

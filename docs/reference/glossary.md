# Glossary

| Term | Definition |
|------|------------|
| **Analysis root** | Directory passed to `parse_repository` / pipeline CLI. All paths are relative to this root. Must be the project root, not a subpackage. |
| **FileAnalysis** | Parser output dataclass for one `.py` file. Canonical parse record for all graph builders. |
| **resolved_deps** | In-repo file paths this module imports (requires `project_files` context). |
| **external_deps** | Stdlib or third-party top-level package names (`os`, `requests`). Not graph nodes in V1. |
| **GraphResult** | Ripple domain graph: sorted `nodes` + directed `edges` `(importer, imported)`. |
| **GraphAdapter** | Converts `GraphResult` → `networkx.DiGraph` once per pipeline run. |
| **PageRank** | Iterative importance along import edges. High score = heavily depended-on file. |
| **Betweenness** | How often a file lies on shortest paths between other files. Bridge / bottleneck. |
| **criticality** | `0.6 * norm(pagerank) + 0.4 * norm(betweenness)` — relative rank within one repo. |
| **composite_score** | Database column name for `criticality`. |
| **in_degree** | Count of project files that import this file. |
| **out_degree** | Count of project files this file imports. |
| **Cycle** | Directed loop of imports (e.g. A→B→C→A). Detected via `nx.simple_cycles`. |
| **normalize_cycle** | Rotate cycle to lex-smallest start node; dedupe rotations. |
| **Impact / blast radius** | All files that directly or transitively import the target (reverse reachability). |
| **direct_dependents** | Hop-1 importers of the target. |
| **indirect_dependents** | Hop 2+ importers, excluding direct. |
| **layers** | Dependents grouped by hop distance from target. |
| **PipelineResult** | Full analysis artifact: `analyses`, `graph`, `cycles`, `scores`, `metrics`. |
| **AnalysisStore** | In-memory `repo_id` → `PipelineResult` cache for graph/scores/impact queries. |
| **Repository Analysis** | `POST /api/repos/analyze` — slim analyze response; fetch graph/scores/impact via repo sub-routes. |
| **Quick Analysis** | `POST /api/analyze` — full analysis JSON in one response (graph, scores, files inline). |
| **repo_id** | UUID for a repository (`repositories.id`); use in all GET URLs (`/api/repos/{repo_id}/…`). |
| **job_id** | UUID for one analyze run (`analysis_jobs.id`); returned on POST; job APIs (Phase 3) for history. |
| **RepositoryHandle** | Ingestion output: `local_path`, `job_id`, `python_files`. |
| **StageMetric** | One timed pipeline stage: `stage_name`, `duration_ms`, optional `files_processed`. |
| **V1 / V2 / V3** | File import graph → class/call graphs → AI insights. See [product](../product/README.md#version-ladder). |

## Edge direction mnemonic

`auth.py → models.py` means **auth imports models**.

- Forward = dependencies (what auth imports)
- Backward = dependents (what imports auth) — used by impact analysis

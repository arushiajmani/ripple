"""Serialize PipelineResult to an API-friendly JSON document.

This module is the only place that defines the public analysis JSON shape.
Business logic (parser, graph, algorithms, pipeline) stays free of JSON concerns.

Schema (v1) — hierarchical so future analyses extend ``analysis`` without
new top-level keys:

    {
      "metadata":    { "generated_at" },
      "repository":  { "name", "source" },
      "summary":     { graph-level counts },
      "statistics":  { parser / source-code counts },
      "graph":       { "nodes", "edges" },
      "analysis":    { "cycles", "scores", ...future... },
      "files":       { path → FileAnalysis fields }   # optional
    }

Design notes:
* **Nodes stay path strings** in V1 — the file graph identity *is* the path;
  scores and files already carry rich per-node data. Object nodes
  ``{"id", "type": "file"}`` can wait until multi-graph types share one payload.
* **Scores stay an ordered list** — ranking is part of the contract; clients
  iterate top-to-bottom without re-sorting.
* **Edges are objects** ``{source, target, type}`` — self-describing; ``type``
  is ``"imports"`` today. ``inherits`` / ``calls`` wait on class/call resolution
  (see docs/learn.md — Why not type inherits yet).
* **Deterministic ordering** — sorted file keys; scores already criticality-desc.
* **Rounded floats** — pagerank, betweenness, and criticality are rounded to
  four decimal places in JSON (``JSON_FLOAT_DECIMALS``); in-memory ``NodeScore``
  values keep full precision for sorting and tests.

Usage:
    data = pipeline_result_to_dict(result)
    write_pipeline_json(result, "result.json")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.graph.models import (
    CircularDependencyResult,
    GraphResult,
    NodeScore,
    ScoringResult,
)
from app.parser.models import (
    ClassInfo,
    FileAnalysis,
    FunctionInfo,
    ImportInfo,
    format_import_display,
)
from app.pipeline.pipeline import PipelineResult

# Edge kind for the file import graph (extensible later: calls, inherits, …).
EDGE_TYPE_IMPORTS = "imports"

# Decimal places for pagerank / betweenness / criticality in JSON export.
JSON_FLOAT_DECIMALS = 4


def round_json_float(value: float) -> float:
    """Round algorithm scores for API/JSON output (full precision kept in memory)."""
    return round(value, JSON_FLOAT_DECIMALS)


# --- Small field serializers (parser / graph models → plain dicts) ---


def import_info_to_dict(item: ImportInfo) -> dict[str, Any]:
    return {
        "module": item.module,
        "type": item.type,
        "alias": item.alias,
        "name": item.name,
        "display": format_import_display(
            import_type=item.type,
            module=item.module,
            alias=item.alias,
            name=item.name,
        ),
    }


def class_info_to_dict(item: ClassInfo) -> dict[str, Any]:
    return {
        "name": item.name,
        "bases": list(item.bases),
        "methods": list(item.methods),
    }


def function_info_to_dict(item: FunctionInfo) -> dict[str, Any]:
    return {
        "name": item.name,
        "parent_class": item.parent_class,
    }


def file_analysis_to_dict(analysis: FileAnalysis) -> dict[str, Any]:
    """Full FileAnalysis — kept rich for future class/function/call graphs."""
    return {
        "file_path": analysis.file_path,
        "imports": [import_info_to_dict(i) for i in analysis.imports],
        "resolved_deps": list(analysis.resolved_deps),
        "external_deps": list(analysis.external_deps),
        "classes": [class_info_to_dict(c) for c in analysis.classes],
        "functions": [function_info_to_dict(f) for f in analysis.functions],
        "methods": [function_info_to_dict(m) for m in analysis.methods],
        "line_count": analysis.line_count,
        "has_syntax_error": analysis.has_syntax_error,
    }


def node_score_to_dict(score: NodeScore) -> dict[str, Any]:
    """Per-file metrics (see NodeScore / learn.md glossary)."""
    return {
        "file_path": score.file_path,
        "pagerank": round_json_float(score.pagerank),
        "betweenness": round_json_float(score.betweenness),
        "criticality": round_json_float(score.criticality),
        "in_degree": score.in_degree,
        "out_degree": score.out_degree,
    }


# --- Section builders ---


def build_metadata(*, generated_at: datetime | None = None) -> dict[str, Any]:
    """When this document was produced (UTC ISO-8601)."""
    when = generated_at or datetime.now(timezone.utc)
    # Stable Z suffix for UTC (easier for clients than +00:00).
    timestamp = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"generated_at": timestamp}


def build_repository(*, name: str, source: str) -> dict[str, str]:
    """Where the analyzed code came from (zip, local path, GitHub, …)."""
    return {"name": name, "source": source}


def build_summary(result: PipelineResult) -> dict[str, Any]:
    """Graph-level counts (structure + cycles), not parser detail."""
    return {
        "file_count": len(result.analyses),
        "node_count": len(result.graph.nodes),
        "edge_count": len(result.graph.edges),
        "cycle_count": result.cycles.cycle_count,
    }


def build_statistics(result: PipelineResult) -> dict[str, Any]:
    """Cheap counts from parsed source (FileAnalysis), not the graph.

    Dependency fields are **repo-wide totals** (sum of list lengths across all
    files). Per-file lists live under ``files[path].resolved_deps`` /
    ``external_deps``. ``internal_dependency_count`` may exceed
    ``summary.edge_count`` when the parser lists the same dep more than once.
    """
    analyses = result.analyses.values()
    return {
        "class_count": sum(len(a.classes) for a in analyses),
        # Module-level functions only (methods live under classes).
        "function_count": sum(len(a.functions) for a in analyses),
        "internal_dependency_count": sum(len(a.resolved_deps) for a in analyses),
        "external_dependency_count": sum(len(a.external_deps) for a in analyses),
    }


def edge_to_dict(source: str, target: str, *, edge_type: str = EDGE_TYPE_IMPORTS) -> dict[str, str]:
    """Self-describing edge: source imports target (for the file graph)."""
    return {
        "source": source,
        "target": target,
        "type": edge_type,
    }


def build_graph(graph: GraphResult) -> dict[str, Any]:
    """Structural file import graph.

    Nodes are path strings in V1 (identity = path). Edges are objects
    ``{source, target, type: "imports"}`` so clients need not remember order,
    and future edge kinds (calls, inherits, …) share the same shape.
    """
    return {
        "nodes": list(graph.nodes),
        "edges": [
            edge_to_dict(source, target)
            for source, target in graph.edges
        ],
    }


def cycle_to_dict(cycle: list[str]) -> dict[str, Any]:
    """One circular dependency as a self-describing object.

    ``nodes`` is an open path (first does not repeat at the end); the cycle
    closes from the last node back to the first. ``edges`` lists each step
    with the same shape as ``graph.edges`` (type ``imports`` for the file graph).
    """
    nodes = list(cycle)
    n = len(nodes)
    edges: list[dict[str, str]] = []
    if n == 1:
        # Self-loop: file imports itself.
        edges.append(edge_to_dict(nodes[0], nodes[0]))
    elif n > 1:
        for i in range(n - 1):
            edges.append(edge_to_dict(nodes[i], nodes[i + 1]))
        edges.append(edge_to_dict(nodes[-1], nodes[0]))
    return {
        "nodes": nodes,
        "length": n,
        "edges": edges,
    }


def build_cycles(cycles: CircularDependencyResult) -> dict[str, Any]:
    return {
        "has_cycles": cycles.has_cycles,
        "cycle_count": cycles.cycle_count,
        "cycles": [cycle_to_dict(cycle) for cycle in cycles.cycles],
    }


def build_analysis(result: PipelineResult) -> dict[str, Any]:
    """Algorithm outputs. Add future keys here (impact_analysis, communities, …).

    ``scores`` is the full ranked list (criticality desc, then path). Consumers
    take the first N entries for a "top critical" view; use ``ScoringResult.top(n)``
    in Python or slice in clients. HTTP APIs can add ``?top=N`` later.
    """
    return {
        "cycles": build_cycles(result.cycles),
        # Ordered list: index 0 is most critical (ranking is intentional).
        "scores": [node_score_to_dict(s) for s in result.scores.scores],
    }


def build_files(analyses: dict[str, FileAnalysis]) -> dict[str, Any]:
    """Path → full FileAnalysis; keys sorted for stable diffs."""
    return {
        path: file_analysis_to_dict(analyses[path])
        for path in sorted(analyses)
    }


# --- Public entry points ---


def pipeline_result_to_dict(
    result: PipelineResult,
    *,
    include_files: bool = True,
    generated_at: datetime | None = None,
    repository: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Full analysis payload for JSON export or future API responses.

    Top-level keys (stable order for readability):
        metadata   — generated_at
        repository — name + source (zip, local, github, …)
        summary    — graph-level counts (files, nodes, edges, cycles)
        statistics — parser / source-code counts (classes, functions, deps)
        graph      — nodes + edges (structure only)
        analysis   — cycles, scores (+ future algorithms)
        files      — optional path → FileAnalysis (omit for a smaller file)
    """
    payload: dict[str, Any] = {
        "metadata": build_metadata(generated_at=generated_at),
    }
    if repository is not None:
        payload["repository"] = repository
    payload.update(
        {
            "summary": build_summary(result),
            "statistics": build_statistics(result),
            "graph": build_graph(result.graph),
            "analysis": build_analysis(result),
        }
    )
    if include_files:
        payload["files"] = build_files(result.analyses)
    return payload


def pipeline_result_to_json(
    result: PipelineResult,
    *,
    indent: int | None = 2,
    include_files: bool = True,
    generated_at: datetime | None = None,
    repository: dict[str, str] | None = None,
) -> str:
    """Serialize PipelineResult to a JSON string."""
    data = pipeline_result_to_dict(
        result,
        include_files=include_files,
        generated_at=generated_at,
        repository=repository,
    )
    return json.dumps(data, indent=indent, ensure_ascii=False) + "\n"


def write_pipeline_json(
    result: PipelineResult,
    path: str | Path,
    *,
    indent: int | None = 2,
    include_files: bool = True,
    generated_at: datetime | None = None,
    repository: dict[str, str] | None = None,
) -> Path:
    """Write analysis JSON to disk; returns the resolved path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = pipeline_result_to_json(
        result,
        indent=indent,
        include_files=include_files,
        generated_at=generated_at,
        repository=repository,
    )
    out.write_text(text, encoding="utf-8")
    return out.resolve()

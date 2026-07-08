from dataclasses import dataclass, field


@dataclass
class GraphResult:
    """Structural file import graph (no scores).

    Edges are (importer, imported): auth.py → models.py means auth imports models.
    """

    nodes: list[str]
    edges: list[tuple[str, str]]


@dataclass
class CircularDependencyResult:
    """Circular import loops found in the graph.

    Each cycle is an ordered list of file paths, e.g.
    ["a.py", "b.py", "c.py"] means a→b→c→a.
    """

    cycles: list[list[str]] = field(default_factory=list)

    @property
    def has_cycles(self) -> bool:
        return len(self.cycles) > 0

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)


@dataclass
class NodeScore:
    """Per-file metrics: how central / risky is this file in the import graph?

    Edge direction is importer → imported (auth.py → models.py).

    Attributes:
        file_path: Repo-relative path of the file.
        pagerank: How much "importance" lands on this file. Importance flows
            along edges toward files that others import. A shared utility
            imported by many modules scores high. Values are non-negative and
            sum to ~1.0 across the whole graph.
        betweenness: How often this file sits on shortest paths between other
            files. High = architectural bridge / bottleneck (changing it can
            affect many unrelated parts of the system). Range is typically
            [0, 1] after NetworkX's default normalization.
        criticality: Ripple's composite risk score in [0, 1] relative to this
            repo: ``0.6 * norm(pagerank) + 0.4 * norm(betweenness)`` after
            min-max normalizing each metric across nodes. Higher = more
            careful when changing this file. Used to rank "top critical" files.
        in_degree: How many other project files import this file (incoming
            edges). Direct dependents count, not transitive.
        out_degree: How many other project files this file imports (outgoing
            edges). Direct dependencies count.
    """

    file_path: str
    pagerank: float
    betweenness: float
    criticality: float
    in_degree: int
    out_degree: int


@dataclass
class ScoringResult:
    """All node scores, sorted by criticality (highest first), then file path.

    Use ``top(n)`` for the n most critical files (default 10).
    """

    scores: list[NodeScore] = field(default_factory=list)

    def top(self, n: int = 10) -> list[NodeScore]:
        """Highest-criticality files (default top 10)."""
        return self.scores[:n]


@dataclass
class ImpactLayer:
    """One hop-distance tier in the blast radius."""

    depth: int
    files: list[str]


@dataclass
class ImpactSummary:
    """Counts and percentage derived from direct and indirect dependents."""

    direct: int
    indirect: int
    total: int
    max_depth: int
    files_affected_percentage: float


@dataclass
class ImpactTarget:
    """Queried file and its existing batch score (if available)."""

    file: str
    score: NodeScore | None = None


@dataclass
class ImpactAnalysisResult:
    """On-demand blast-radius for one file in an already-built import graph.

    Edge direction is importer → imported. Dependents are found by walking
    predecessors (reverse reachability): files that import the target, directly
    or transitively.

    Attributes:
        target: Queried file path and optional existing ``NodeScore``.
        direct_dependents: Immediate importers (hop distance 1), sorted.
        indirect_dependents: Indirect importers only (depth 2+), sorted.
            Does not include ``direct_dependents``.
        layers: Blast radius by hop distance; each file appears in exactly one
            layer. ``depth`` 1 = direct importers.
        summary: ``direct``, ``indirect``, ``total``, ``max_depth``, and
            ``files_affected_percentage`` (3 decimal places).
    """

    target: ImpactTarget
    direct_dependents: list[str]
    indirect_dependents: list[str]
    layers: list[ImpactLayer]
    summary: ImpactSummary

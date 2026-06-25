from dataclasses import dataclass, field


@dataclass
class GraphResult:
    nodes: list[str]
    edges: list[tuple[str, str]]


@dataclass
class CircularDependencyResult:
    cycles: list[list[str]] = field(default_factory=list)

    @property
    def has_cycles(self) -> bool:
        return len(self.cycles) > 0

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

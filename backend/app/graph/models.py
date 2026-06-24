from dataclasses import dataclass


@dataclass
class GraphResult:
    nodes: list[str]
    edges: list[tuple[str, str]]

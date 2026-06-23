from dataclasses import dataclass, field


@dataclass
class ClassInfo:
    name: str
    bases: list[str] = field(default_factory=list)


@dataclass
class FunctionInfo:
    name: str
    parent_class: str | None = None


@dataclass
class FileAnalysis:
    file_path: str
    imports: list[str] = field(default_factory=list)
    resolved_deps: list[str] = field(default_factory=list)
    external_deps: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    line_count: int = 0
    has_syntax_error: bool = False

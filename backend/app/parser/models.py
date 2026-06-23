from dataclasses import dataclass, field

SKIP_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
})


@dataclass
class ImportInfo:
    module: str
    type: str  # "import" or "from_import"
    alias: str | None = None
    name: str | None = None  # imported symbol for from_import

    @property
    def display(self) -> str:
        if self.type == "import":
            if self.alias:
                return f"import {self.module} as {self.alias}"
            return f"import {self.module}"
        symbol = self.name or "*"
        if self.alias:
            symbol = f"{symbol} as {self.alias}"
        return f"from {self.module} import {symbol}"


@dataclass
class ClassInfo:
    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


@dataclass
class FunctionInfo:
    name: str
    parent_class: str | None = None


@dataclass
class FileAnalysis:
    file_path: str
    imports: list[ImportInfo] = field(default_factory=list)
    resolved_deps: list[str] = field(default_factory=list)
    external_deps: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    line_count: int = 0
    has_syntax_error: bool = False

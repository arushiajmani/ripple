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


def format_import_display(
    *,
    import_type: str,
    module: str,
    alias: str | None = None,
    name: str | None = None,
) -> str:
    """Human-readable import statement (e.g. ``import os``, ``from x import y``)."""
    if import_type == "import":
        if alias:
            return f"import {module} as {alias}"
        return f"import {module}"
    symbol = name or "*"
    if alias:
        symbol = f"{symbol} as {alias}"
    return f"from {module} import {symbol}"


@dataclass
class ImportInfo:
    module: str
    type: str  # "import" or "from_import"
    alias: str | None = None
    name: str | None = None  # imported symbol for from_import

    @property
    def display(self) -> str:
        return format_import_display(
            import_type=self.type,
            module=self.module,
            alias=self.alias,
            name=self.name,
        )


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

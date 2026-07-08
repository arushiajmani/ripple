# Parser

| | |
|---|---|
| **Status** | Implemented |
| **Owner** | Backend |
| **Last Updated** | 2026-07-08 |

**Related components:** [Pipeline](pipeline.md) · [Graph builder](graph-builder.md) · [Ingestion](ingestion.md)

**Tests:** `tests/test_parser.py` (15)

**Source files:** `app/parser/models.py` · `app/parser/ast_parser.py` · `app/parser/dependencies.py` · `app/parser/repository.py` · `app/parser/cli.py`

---

## Overview

The parser reads `.py` files via Python's `ast` module and returns a `FileAnalysis` per file: imports, classes, functions, methods, `resolved_deps`, `external_deps`, and syntax-error flags.

```text
backend/app/parser/
├── models.py         # FileAnalysis, ImportInfo, SKIP_DIRS
├── ast_parser.py     # ASTParser.parse_file
├── dependencies.py   # module → file resolution
├── repository.py     # collect_python_files, parse_repository
└── cli.py            # python -m app.parser.cli
```

## Output types

```python
@dataclass
class FileAnalysis:
    file_path: str
    imports: list[ImportInfo]
    resolved_deps: list[str]   # in-repo paths (needs project_files)
    external_deps: list[str]   # stdlib / third-party
    classes: list[ClassInfo]
    functions: list[FunctionInfo]   # module-level
    methods: list[FunctionInfo]     # class methods
    line_count: int
    has_syntax_error: bool
```

## API

**Single file** (no repo context — `resolved_deps` stays empty):

```python
from app.parser.ast_parser import ASTParser

parser = ASTParser()
analysis = parser.parse_file("myapp/auth.py", content)
```

**Whole repository:**

```python
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
analyses["myapp/auth.py"].resolved_deps  # ["myapp/models.py", "myapp/utils.py"]
```

`parse_repository(root)` walks the tree, skips `SKIP_DIRS` (`.git`, `venv`, `__pycache__`, …), builds `project_files`, and parses every `.py` file.

## Analysis root convention

Always pass the **project root**, not a package subfolder.

| Root you pass | Paths collected | `from app.parser.models` |
|---------------|-----------------|---------------------------|
| `backend/` (`.`) | `app/parser/models.py` | Resolves ✓ |
| repo root (`..`) | `backend/app/parser/models.py` | Suffix match ✓ |
| `app/parser/` | `models.py` only | **External** `app` ✗ |

Production analysis (zip, clone, pipeline) always uses the uploaded project root.

**Symptom of wrong root:** all in-repo imports appear under `external_deps`.

```bash
cd backend
python -m app.parser.cli tests/fixtures/mini_repo
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
python -m app.parser.cli tests/sample_file.py   # single file, no resolved_deps
```

## Import resolution

`dependencies.module_to_file_path` tries, in order:

1. `myapp/utils.py`
2. `myapp/utils/__init__.py`
3. Suffix match on `project_files` (e.g. `backend/app/parser/models.py` when root is above `backend/`)

Relative imports: `from .utils import x` in `auth/session.py` resolves using `level` + `module` from the AST.

Skipped: `from __future__ import annotations`, nested functions, nested classes.

## Syntax errors

Invalid syntax returns `has_syntax_error=True` without raising — the rest of the repo still parses.

## Design notes (parser iteration)

- **Structured `ImportInfo`** — not raw strings; `ImportInfo.display` for CLI.
- **No fake `resolved_deps`** without `project_files`.
- **Separate `functions` vs `methods`** — methods nested under classes in CLI output.
- **Suffix matching** — fixes `external_deps: app` when repo root sits above the package.

Cross-cutting rationale: [architecture/README.md](../architecture/README.md#parser-graph-design).

## CLI

Run from `backend/` with venv active:

```bash
python -m app.parser.cli tests/fixtures/mini_repo
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
python -m app.parser.ast_parser …   # backward-compatible alias
```

Use `python -m app.parser.cli`, not `python tests/...`, or Python won't find the `app` package.

## Example output

See [examples/mini_repo.md](../examples/mini_repo.md#parser-output).

## Further reading

- [CLI reference — Parser](../development/cli-reference.md#parser--inspect-imports-and-structure)
- [JSON format — files section](../reference/json-format.md)
- [Glossary — resolved_deps](../reference/glossary.md)

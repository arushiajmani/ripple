# Ripple — Code Study Guide

> Read this to understand **what the code does, why it's shaped this way, and how data flows through it.**
> One section per shipped component. Future phases are listed so you know what's coming.

*Last updated: 2026-06-24*

---

### Checklist (AST parser)

| Task | Done? |
|------|-------|
| `ASTParser` in `backend/app/parser/ast_parser.py` | Yes |
| Structured `ImportInfo` (module, alias, type) | Yes |
| Absolute / from / relative / aliased imports | Yes (logic in code; needs more tests) |
| Extract classes (name + bases + methods) | Yes |
| Separate module functions vs class methods | Yes |
| `resolved_deps` / `external_deps` classification | Yes (requires `project_files`) |
| `FileAnalysis` dataclass | Yes |
| CLI: `python -m app.parser.ast_parser <file>` | Yes |
| Unit tests in `tests/test_parser.py` | No |
| Repo ingestion / batch parsing | No |
| Test against 5 real open-source files | No |

---

## Big picture

Ripple turns a Python repo into a **dependency graph** and scores each file for architectural importance.

```
zip / repo  →  IngestionService  →  list of .py files
                                        │
                                        ▼
                                  ASTParser (per file)  →  FileAnalysis
                                        │
                                        ▼
                                  GraphBuilder  →  nx.DiGraph
                                        │
                                        ▼
                                  AlgorithmEngine  →  PageRank, cycles, scores
                                        │
                                        ▼
                                  PostgreSQL / JSON / API / React graph
```

**Only the parser box exists today.** Everything else is planned.

**Design choices worth remembering:**

- **Modular monolith** — one Python process, folders = components (`parser/`, `graph/`, `api/`).
- **Compute vs storage** — NetworkX computes graphs in memory; Postgres stores results later.
- **Parser is pure** — `parse_file(path, content)` takes a string; caller handles disk I/O.
- **Structured imports internally, readable strings for display** — `ImportInfo` in the model; `.display` for CLI.
- **No fake resolution** — `resolved_deps` only populated when `project_files` is set and a path actually exists in the project.

---

## Design choices & things we rectified

These decisions came from iterating on the parser output and data model.

### 1. Structured imports (`ImportInfo`)

**Before:** `imports: list[str]` like `"import numpy as np"`.

**Now:** each import is an `ImportInfo`:

```python
ImportInfo(module="numpy", alias="np", type="import")
ImportInfo(module="pathlib", name="Path", type="from_import")
```

`ImportInfo.display` reproduces the readable string for CLI. Downstream code can filter on `module` without parsing strings.

### 2. Don't fake `resolved_deps` for single-file parsing

**Before:** without project context, the parser guessed paths like `os.py`, `pathlib.py` and put them in `resolved_deps`. That implied `os` was a file in your repo — wrong.

**Now:**

| Context | `resolved_deps` | `external_deps` |
|---------|---------------|-----------------|
| Single file (no `project_files`) | `[]` | top-level packages from imports (`os`, `numpy`, …) |
| Repo (`project_files` set) | paths that exist in the project (`myapp/utils.py`) | everything else (`os`, `requests`, …) |

True file-to-file resolution only happens when you pass the full set of project `.py` paths. A future `IngestionService` will collect those and call `parse_file` per file.

We also removed a short-lived `modules` field — `imports` + `resolved_deps` + `external_deps` cover the use cases without a third redundant list.

### 3. Functions vs methods — separate lists, no CLI duplication

**Before:** one `functions` list mixed module-level defs and class methods; CLI showed methods twice (under `classes` and again under `functions`).

**Now:**

- `functions` — module-level only (`parent_class` is always `None`)
- `methods` — class methods (`parent_class` always set)
- `ClassInfo.methods` — method names for convenient grouping
- **CLI:** methods nested under their class; `functions` section lists module-level defs only

### 4. Clearer class output

**Before:** `User((none))` when a class had no base classes.

**Now:** `User` with no suffix; `Admin (bases: User)` when bases exist.

### 5. Correct parent-class detection for methods

**Before:** `_parent_class_name` returned the first top-level class whose subtree contained the node. That mis-attributed nested functions inside methods, and picked the outer class for nested inner classes.

**Now:** `_find_parent_class` recurses into nested classes and only returns a class if the function is a **direct** method in that class's body (not a nested function inside another method).

| Node | Result |
|------|--------|
| `def login():` at module level | `functions`, no parent |
| `User.get_name` | `methods`, `parent_class="User"` |
| `def helper():` inside `get_name` | skipped (nested function) |
| method on nested `Inner` class | `parent_class="Inner"`, not outer class |

---

## Phase 0 — Project setup (complete)

What exists and where:

| Piece | Location | Purpose |
|-------|----------|---------|
| FastAPI app | `backend/app/main.py` | `GET /health` → `{"status": "ok"}` |
| Docker stack | `docker-compose.yml` | `backend`, `db` (Postgres), `frontend` |
| Python deps | `backend/requirements.txt` | FastAPI, SQLAlchemy, NetworkX, pytest, … |
| React shell | `frontend/` | Vite + React (minimal) |

Local backend dev (no Docker):

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

---

## Phase 1, Week 1 — AST Parser

**Goal:** Read one `.py` file and return structured facts about its imports, classes, functions, and methods.

**Files to read in order:**

1. `backend/app/parser/models.py` — output shapes
2. `backend/app/parser/ast_parser.py` — parsing logic
3. `backend/tests/sample_file.py` — small file to try against

---

### 1. Output types (`models.py`)

These dataclasses are the **API of the parser** — everything downstream consumes `FileAnalysis`.

```python
@dataclass
class ImportInfo:
    module: str
    type: str              # "import" or "from_import"
    alias: str | None = None
    name: str | None = None  # symbol for from_import

    @property
    def display(self) -> str: ...  # "import numpy as np", etc.

@dataclass
class ClassInfo:
    name: str
    bases: list[str]       # e.g. ["User"] or []
    methods: list[str]     # method names defined on this class

@dataclass
class FunctionInfo:
    name: str
    parent_class: str | None = None  # set on methods only

@dataclass
class FileAnalysis:
    file_path: str
    imports: list[ImportInfo]
    resolved_deps: list[str]   # project file paths (only with project_files)
    external_deps: list[str]   # top-level packages (os, requests, …)
    classes: list[ClassInfo]
    functions: list[FunctionInfo]   # module-level
    methods: list[FunctionInfo]     # class methods
    line_count: int
    has_syntax_error: bool
```

**Example** — parsing `tests/sample_file.py` **without** `project_files`:

```python
FileAnalysis(
    file_path="tests/sample_file.py",
    imports=[
        ImportInfo(module="os", type="import"),
        ImportInfo(module="numpy", alias="np", type="import"),
        ImportInfo(module="pathlib", name="Path", type="from_import"),
        ImportInfo(module="collections", name="defaultdict", type="from_import"),
    ],
    resolved_deps=[],
    external_deps=["os", "numpy", "pathlib", "collections"],
    classes=[
        ClassInfo(name="User", bases=[], methods=["get_name"]),
        ClassInfo(name="Admin", bases=["User"], methods=["promote"]),
    ],
    functions=[
        FunctionInfo(name="login"),
        FunctionInfo(name="logout"),
    ],
    methods=[
        FunctionInfo(name="get_name", parent_class="User"),
        FunctionInfo(name="promote", parent_class="Admin"),
    ],
    line_count=20,
    has_syntax_error=False,
)
```

**Example** — same file's imports with `project_files={"myapp/utils.py"}` and `from myapp.utils import helper`:

```python
resolved_deps=["myapp/utils.py"]
external_deps=["os"]
```

---

### 2. Input to `parse_file`

```python
parser = ASTParser()
result = parser.parse_file(file_path: str, content: str) -> FileAnalysis
```

| Argument | Why it exists |
|----------|---------------|
| `file_path` | Relative path like `auth/session.py`. Used to resolve `from .utils import x` into `auth.utils`. |
| `content` | Raw source text. Parser never opens files — tests pass strings; CLI reads disk once. |

Optional constructor args (for graph building):

- `project_root: str | None` — reserved for future use
- `project_files: set[str]` — all `.py` paths in the repo (e.g. `{"myapp/auth.py", "myapp/utils.py"}`). When set, imports are split into `resolved_deps` vs `external_deps`.

**Single file vs repo today:**

| Mode | How | `resolved_deps` |
|------|-----|-----------------|
| CLI default | `ASTParser()` | always `[]` |
| Manual repo | collect `project_files`, one parser, loop `parse_file` | real internal paths |
| Future | `IngestionService` does the above automatically | same |

---

### 3. What is an AST?

**AST = Abstract Syntax Tree.** Python's `ast` module parses source code into a tree of objects. Each object is a **node** (one syntactic construct). Nodes can contain child nodes.

Source code is **text**. The AST is **structure** — grammar, not characters.

```
TEXT                              AST (conceptual)
────                              ────────────────
import os                    →    Import(names=[alias(name='os')])
class User:                  →    ClassDef(name='User', body=[...])
    def get_name(self):      →        FunctionDef(name='get_name', ...)
def login():                 →    FunctionDef(name='login', ...)
```

**Key idea:** `tree.body` is only **top-level statements**. Deeper nodes (`Pass`, `arguments`, nested `FunctionDef`) live inside those.

---

### 4. What `ast.walk` does

```python
for node in ast.walk(tree):
    ...
```

`ast.walk` performs a **depth-first preorder traversal**. We only **act** on nodes matching `isinstance` checks — everything else is ignored.

#### Nesting — what we keep vs skip

```python
class User:
    def get_name(self):      # method → methods[], ClassInfo.methods
        pass

def login():
    def inner():             # nested function → SKIP
        pass
```

| Node | Destination | Why |
|------|-------------|-----|
| `login` | `functions` | top-level |
| `get_name` | `methods` + `ClassInfo.methods` | direct child of `ClassDef` |
| `inner` | skipped | nested inside a function, not a class method |

Relevant code:

```python
elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
    parent = self._parent_class_name(tree, node)
    if parent is not None:
        methods.append(FunctionInfo(name=node.name, parent_class=parent))
    elif self._is_top_level(tree, node):
        functions.append(FunctionInfo(name=node.name))
```

**Classes** use the same top-level filter — a class defined inside a function is walked but not collected.

---

### 5. Node types the parser handles

| AST node | Python source | Extracted as |
|----------|---------------|--------------|
| `ast.Import` | `import os`, `import numpy as np` | `ImportInfo(type="import")` |
| `ast.ImportFrom` | `from pathlib import Path` | `ImportInfo(type="from_import")` |
| `ast.ImportFrom` (relative) | `from .utils import helper` | resolved module from path + `level` |
| `ast.ClassDef` | `class User(Base):` | `ClassInfo(name, bases, methods)` |
| `ast.FunctionDef` | `def login():` | `functions` or `methods` |
| `ast.AsyncFunctionDef` | `async def fetch():` | same as `FunctionDef` |

**Skipped:**

| Case | Why |
|------|-----|
| `from __future__ import annotations` | Compiler directive, not a dependency |
| Nested functions | Not module API surface (for now) |
| Nested classes | Not top-level definitions |

---

### 6. Import resolution & dependency classification

#### Absolute imports

| Source | `ImportInfo` | Module for deps |
|--------|--------------|-----------------|
| `import os` | `module="os", type="import"` | `os` |
| `import numpy as np` | `module="numpy", alias="np"` | `numpy` |
| `from os.path import join` | `module="os.path", name="join"` | `os.path` |

#### Relative imports

AST stores relative imports on `ImportFrom` with:

- `level` — number of dots (`from .` → 1, `from ..` → 2)
- `module` — rest of path (`utils` in `from .utils import x`)

File `auth/session.py` + `from .utils import helper`:

```
auth/session.py  →  parent dir = auth
level = 1        →  stay in auth
module = utils   →  auth.utils
```

#### Module → file path (`_module_to_file_path`)

Only runs when `project_files` is set. Module `myapp.utils` tries, in order:

1. `myapp/utils.py`
2. `myapp/utils/__init__.py`
3. `myapp.py` (edge case for `myapp.something`)

Returns `None` if no candidate is in `project_files` → import goes to `external_deps`.

**Without `project_files`:** no path guessing at all. Everything unidentified stays in `external_deps` (by top-level package name).

---

### 7. Syntax errors

```python
try:
    tree = ast.parse(content, filename=normalized_path)
except SyntaxError:
    return FileAnalysis(file_path=..., line_count=..., has_syntax_error=True)
```

No exception propagates. Callers can skip bad files and continue analyzing the rest of a repo.

---

### 8. End-to-end flow in `parse_file`

```
content, file_path
       │
       ▼
ast.parse() ──SyntaxError──► FileAnalysis(has_syntax_error=True)
       │
       ▼
   ast.walk(tree)
       │
       ├── Import / ImportFrom  → imports[], module_names[]
       ├── ClassDef (top-level) → classes[] (+ methods on ClassInfo)
       └── FunctionDef          → functions[] or methods[]
       │
       ▼
_classify_dependencies(module_names)
       │
       ▼
FileAnalysis (full)
```

---

### 9. Try it yourself

**CLI** (from `backend/`):

```bash
source .venv/bin/activate
python -m app.parser.ast_parser tests/sample_file.py
```

Expected sections: `imports`, `resolved_deps` (empty), `external_deps`, `classes` (with nested methods), `functions` (module-level only).

**Repo-aware parsing in a REPL:**

```python
from pathlib import Path
from app.parser.ast_parser import ASTParser

root = Path("path/to/your/repo")
project_files = {p.relative_to(root).as_posix() for p in root.rglob("*.py")}
parser = ASTParser(project_files=project_files)

for path in sorted(project_files):
    content = (root / path).read_text()
    analysis = parser.parse_file(path, content)
    print(path, "→", analysis.resolved_deps, "|", analysis.external_deps)
```

**Inspect the AST tree:**

```python
import ast
from pathlib import Path

content = Path("tests/sample_file.py").read_text()
tree = ast.parse(content)
print(ast.dump(tree, indent=2))
```

#### Common mistake

`ModuleNotFoundError: No module named 'app'` — you ran a script from `tests/` instead of using `-m` from `backend/`. Python puts the script's folder on `sys.path`, not `backend/`.

---

## Coming next (not implemented yet)

Read [Roadmap.md](./Roadmap.md) for full detail. Short preview:

| Week | Component | What it will do |
|------|-----------|-----------------|
| 2 | `GraphBuilder` | Many `FileAnalysis` → one `nx.DiGraph` (nodes = files, edges = imports) |
| 2 | `AlgorithmEngine` | PageRank, betweenness, cycle detection, criticality score |
| 3 | `IngestionService` | Unzip repo, walk tree, filter `venv/` / `__pycache__`, set `project_files` |
| 3 | `AnalysisPipeline` | Wire ingestion → parser → graph → algorithms → JSON |

---

## Dependency cheat sheet

| Package | Used for |
|---------|----------|
| `fastapi` + `uvicorn` | HTTP API |
| `sqlalchemy` + `psycopg2` | Postgres ORM |
| `networkx` | Graph algorithms (Week 2) |
| `pytest` + `httpx` | Tests |

---

*Add a new major section here each time a component ships (GraphBuilder, AlgorithmEngine, …).*

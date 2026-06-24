# Ripple — Code Study Guide

> Read this to understand **what the code does, why it's shaped this way, and how data flows through it.**
> One section per shipped component. Future phases are listed so you know what's coming.

*Last updated: 2026-06-24*

---

### Checklist (AST parser)

| Task | Done? |
|------|-------|
| `ASTParser` in `backend/app/parser/ast_parser.py` | Yes |
| `dependencies.py` — module → file resolution | Yes |
| `repository.py` — `parse_repository()` | Yes |
| `cli.py` — terminal output | Yes |
| Structured `ImportInfo` (module, alias, type) | Yes |
| Absolute / from / relative / aliased imports | Yes (logic in code; needs more tests) |
| Extract classes (name + bases + methods) | Yes |
| Separate module functions vs class methods | Yes |
| `resolved_deps` / `external_deps` classification | Yes (requires `project_files`) |
| Suffix path matching (`app.parser` → `backend/app/parser/…`) | Yes |
| `FileAnalysis` dataclass | Yes |
| CLI: `python -m app.parser.cli <file-or-repo>` | Yes |
| Unit tests in `tests/test_parser.py` | Yes |
| `IngestionService` (zip upload, filters) | No |
| Test against 5 real open-source files | No |

### Checklist (graph builder)

| Task | Done? |
|------|-------|
| `GraphBuilder` in `backend/app/graph/builder.py` | Yes |
| `GraphResult` dataclass (`nodes`, `edges`) | Yes |
| Directed edges: importer → imported | Yes |
| Filter deps to in-repo nodes only | Yes |
| Deduplicate edges, deterministic sort | Yes |
| Unit tests in `tests/test_graph.py` (9 cases) | Yes |
| `AlgorithmEngine` (PageRank, cycles, scores) | No |
| `nx.DiGraph` wrapper / conversion | No |

---

## Big picture

Ripple turns a Python repo into a **dependency graph** and scores each file for architectural importance.

```
zip / repo  →  IngestionService (planned)  →  list of .py files
                                                    │
                    parse_repository() ◄────────────┘  (shipped today)
                            │
                            ▼
                      ASTParser (per file)  →  FileAnalysis
                            │
                            ▼
                      GraphBuilder  →  GraphResult (nodes + edges)
                            │
                            ▼
                      AlgorithmEngine (planned)  →  PageRank, cycles, scores
                            │
                            ▼
                      PostgreSQL / JSON / API / React graph
```

**Parser, repo batch parsing, and graph construction exist today.** Ingestion and algorithms are planned.

**Design choices worth remembering:**

- **Modular monolith** — one Python process, folders = components (`parser/`, `graph/`, `api/`).
- **Compute vs storage** — NetworkX computes graphs in memory; Postgres stores results later.
- **Parser is pure** — `parse_file(path, content)` takes a string; caller handles disk I/O.
- **Structured imports internally, readable strings for display** — `ImportInfo` in the model; `.display` for CLI.
- **No fake resolution** — `resolved_deps` only populated when `project_files` is set and a path actually exists in the project.
- **Light module split** — `ast_parser.py` (walk tree), `dependencies.py` (resolve imports), `repository.py` (batch parse), `cli.py` (display). One concern per file.

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

True file-to-file resolution only happens when you pass the full set of project `.py` paths — `parse_repository()` does this automatically. A future `IngestionService` will add zip upload and smarter filtering.

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

### 6. Parser package split (light modular layout)

**Before:** one `ast_parser.py` (~330 lines) mixed AST walking, dependency resolution, repo walking, and CLI printing.

**Now:**

| File | Role |
|------|------|
| `models.py` | `FileAnalysis`, `ImportInfo`, `SKIP_DIRS` |
| `ast_parser.py` | `ASTParser.parse_file` — AST walk only |
| `dependencies.py` | `classify_dependencies`, `module_to_file_path` — pure functions |
| `repository.py` | `collect_python_files`, `parse_repository` |
| `cli.py` | `print_analysis`, `main` — `python -m app.parser.cli` |

`GraphBuilder` consumes `resolved_deps` from the parser — it does not re-run import resolution. `IngestionService` will eventually own file discovery; `repository.py` is the interim orchestrator.

### 7. Suffix matching for internal imports

When the repo root is above the Python package (e.g. ripple root contains `backend/app/parser/…`), an import like `from app.parser.models import X` must resolve to `backend/app/parser/models.py`, not be misclassified as external `app`.

`dependencies.module_to_file_path` tries exact path candidates first, then **suffix matches** on `project_files`. This fixed false `external_deps: app` when scanning the full project.

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
2. `backend/app/parser/ast_parser.py` — single-file AST parsing (`ASTParser`)
3. `backend/app/parser/dependencies.py` — module → file resolution
4. `backend/app/parser/repository.py` — repo walk + batch parse
5. `backend/app/parser/cli.py` — terminal output
6. `backend/tests/sample_file.py` — small file to try against

```text
backend/app/parser/
├── models.py         # FileAnalysis, ImportInfo, SKIP_DIRS
├── ast_parser.py     # ASTParser.parse_file
├── dependencies.py   # classify_dependencies, module_to_file_path
├── repository.py     # collect_python_files, parse_repository
└── cli.py            # python -m app.parser.cli
```

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
| CLI single file | `python -m app.parser.cli file.py` | `[]` |
| CLI repo | `python -m app.parser.cli path/to/repo` | internal paths per file |
| Python API | `parse_repository(root)` | same as CLI repo |
| Manual | `ASTParser(project_files=…)` + loop | same |

---

### 2b. `parse_repository` (`repository.py`)

Walks a directory, skips `SKIP_DIRS` (`.git`, `venv`, `__pycache__`, …), builds `project_files`, parses every `.py` file, returns:

```python
dict[str, FileAnalysis]  # keys are paths relative to repo root
```

```python
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
auth = analyses["myapp/auth.py"]
# auth.resolved_deps → ["myapp/models.py", "myapp/utils.py"]
# auth.external_deps → ["os", "requests"]
```

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

#### Module → file path (`dependencies.module_to_file_path`)

Lives in `dependencies.py` (not on `ASTParser`). Only runs when `project_files` is set.

Module `myapp.utils` tries, in order:

1. `myapp/utils.py`
2. `myapp/utils/__init__.py`
3. `myapp.py` (edge case for `myapp.something`)

If none match exactly, **suffix match**: any `project_files` entry ending in `/myapp/utils.py` (handles `backend/tests/fixtures/mini_repo/myapp/utils.py` when repo root is higher).

Returns `None` if no match → import goes to `external_deps`.

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

### 8. End-to-end flow

**Single file** (`ASTParser.parse_file`):

```
content, file_path
       │
       ▼
ast.parse() ──SyntaxError──► FileAnalysis(has_syntax_error=True)
       │
       ▼
   ast.walk(tree)  →  imports, classes, functions, methods
       │
       ▼
dependencies.classify_dependencies(module_names, project_files)
       │
       ▼
FileAnalysis
```

**Whole repo** (`parse_repository`):

```
repo_path
    │
    ▼
collect_python_files()  →  project_files set
    │
    ▼
ASTParser(project_files) + parse_file() for each .py
    │
    ▼
dict[str, FileAnalysis]
```

---

### 9. Try it yourself

**CLI** (from `backend/`):

```bash
source .venv/bin/activate
python -m app.parser.cli tests/sample_file.py
python -m app.parser.cli tests/fixtures/mini_repo
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
```

`python -m app.parser.ast_parser` still works (shim to the same CLI).

Expected sections: `imports`, `resolved_deps`, `external_deps`, `classes` (with nested methods), `functions` (module-level only).

For repo mode, `resolved_deps` paths are relative to the repo root you pass in.

**Repo-aware parsing in a REPL:**

```python
from pathlib import Path
from app.parser.repository import parse_repository

root = Path("path/to/your/repo")
analyses = parse_repository(root)

for path, analysis in analyses.items():
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

**Running tests** (always from `backend/`):

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v              # all tests
PYTHONPATH=. pytest tests/test_graph.py -v   # graph builder only
```

If you `cd tests/` first, use `PYTHONPATH=.. pytest . -v` — not `pytest tests/`.

---

## Phase 1, Week 2 — Graph Builder

**Goal:** Turn many `FileAnalysis` records into one dependency graph: nodes = files, edges = import relationships.

**Files to read in order:**

1. `backend/app/graph/models.py` — `GraphResult`
2. `backend/app/graph/builder.py` — `GraphBuilder.build`
3. `backend/tests/test_graph.py` — unit tests (synthetic `FileAnalysis` fixtures)

```text
backend/app/graph/
├── models.py      # GraphResult
├── builder.py     # GraphBuilder
└── algorithms.py  # AlgorithmEngine (planned)
```

### 1. Output type (`GraphResult`)

```python
@dataclass
class GraphResult:
    nodes: list[str]                  # sorted file paths
    edges: list[tuple[str, str]]      # (importer, imported)
```

This is the **structural** graph only — no scores yet. `AlgorithmEngine` will add PageRank, betweenness, and cycles on top.

### 2. Input and API

```python
from app.graph import GraphBuilder
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
result = GraphBuilder().build(analyses)

# result.nodes → ["myapp/auth.py", "myapp/models.py", "myapp/utils.py", "myapp/__init__.py"]
# result.edges → [
#     ("myapp/auth.py", "myapp/models.py"),
#     ("myapp/auth.py", "myapp/utils.py"),
#     ("myapp/utils.py", "myapp/models.py"),
# ]
```

| Input | Type | Notes |
|-------|------|-------|
| `analyses` | `dict[str, FileAnalysis]` | Keys are repo-relative paths — same shape as `parse_repository()` |

`GraphBuilder` only reads `resolved_deps` from each `FileAnalysis`. It ignores `external_deps`, `imports`, classes, functions, and `has_syntax_error` — those are parser concerns.

### 3. Edge direction (important for impact analysis later)

```
auth/session.py  →  utils/crypto.py
```

Means: **session.py imports crypto.py**. If `crypto.py` changes, **session.py** may break.

Direction is `(source, target)` = `(importer, imported)`. Impact analysis later walks **backwards** along edges to find "who depends on this file?"

### 4. What becomes a node vs an edge

| Data | Becomes graph node? | Becomes edge? |
|------|---------------------|---------------|
| Key in `analyses` dict | Yes (always) | — |
| Entry in `resolved_deps` where target is also in `analyses` | — | Yes |
| Entry in `resolved_deps` where target is **not** in `analyses` | No | Skipped |
| `external_deps` (`requests`, `os`, …) | No | No |

The parser already separates internal vs external. The builder trusts `resolved_deps` and filters to in-repo targets only:

```python
for dep in analysis.resolved_deps:
    if dep not in node_set:
        continue
    edge = (file_path, dep)
```

### 5. Design choices

**Dict keys are the source of truth for node identity.** Nodes come from `sorted(analyses)` — the dict keys — not from `analysis.file_path`. Edge sources use the dict key during iteration. If a key and `file_path` ever diverge, the graph follows the key. `parse_repository()` keeps them aligned; don't hand-build mismatched dicts in production.

**Deterministic output.** Nodes and edges are sorted so tests and diffs are stable across runs.

**Duplicate deps deduplicated.** If the parser lists the same `resolved_deps` path twice (multiple imports of one module), only one edge is kept.

**Cycles and self-loops are preserved, not rejected.** A→B→C→A or a file importing itself becomes an edge. Cycle *detection* is `AlgorithmEngine`'s job; the builder just records structure.

**Syntax-error files still participate.** A file with `has_syntax_error=True` is still a node if it's in the dict. Any `resolved_deps` the parser extracted before failing still become edges.

**No NetworkX yet.** `GraphResult` is plain lists. `AlgorithmEngine` can build an `nx.DiGraph` from nodes/edges when scoring — avoids storing the graph twice until needed.

### 6. End-to-end flow (parser → graph)

```
parse_repository(repo_path)
        │
        ▼
dict[str, FileAnalysis]     # each file has resolved_deps / external_deps
        │
        ▼
GraphBuilder().build(analyses)
        │
        ▼
GraphResult { nodes, edges }
```

### 7. How we test it

Graph tests are **unit tests** — they pass hand-built `FileAnalysis` dicts directly to `GraphBuilder`, without calling `parse_repository()`. That isolates graph rules from parser rules.

| Test | What it proves |
|------|----------------|
| Empty repository | `{}` → no nodes, no edges |
| Single file, no deps | isolated file is a node with zero edges |
| Simple dependency graph | fan-out + shared dependency, correct direction |
| Missing / external deps ignored | out-of-repo `resolved_deps` and `external_deps` produce no edges |
| Duplicate deps deduplicated | repeated `resolved_deps` → one edge |
| Cyclic imports preserved | A→B→C→A kept intact |
| Self-import | rare self-loop edge documented |
| Dict key vs `file_path` | node identity follows dict key |
| Syntax-error file | still a node; partial deps still become edges |

**What we deliberately don't test in `test_graph.py`:** import resolution (that's `test_parser.py`), NetworkX algorithms, or hardcoded `mini_repo` edge lists. One integration smoke test via `parse_repository` is optional; the suite focuses on graph construction rules.

### 8. Try it yourself

```python
from app.graph import GraphBuilder
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
result = GraphBuilder().build(analyses)

for source, target in result.edges:
    print(f"{source} imports {target}")
```

---

## Coming next (not implemented yet)

Read [Roadmap.md](./Roadmap.md) for full detail. Short preview:

| Week | Component | What it will do |
|------|-----------|-----------------|
| 2 | `AlgorithmEngine` | PageRank, betweenness, cycle detection, criticality score |
| 3 | `IngestionService` | Unzip repo, walk tree, filter `venv/` / `__pycache__`, set `project_files` |
| 3 | `AnalysisPipeline` | Wire ingestion → parser → graph → algorithms → JSON |

---

## Dependency cheat sheet

| Package | Used for |
|---------|----------|
| `fastapi` + `uvicorn` | HTTP API |
| `sqlalchemy` + `psycopg2` | Postgres ORM |
| `networkx` | Graph algorithms (`AlgorithmEngine`, planned) |
| `pytest` + `httpx` | Tests |

---

*Add a new major section here each time a component ships (GraphBuilder, AlgorithmEngine, …).*

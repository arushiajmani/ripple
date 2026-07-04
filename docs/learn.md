# Ripple — Code Study Guide

> Read this to understand **what the code does, why it's shaped this way, and how data flows through it.**
> One section per shipped component. Future phases are listed so you know what's coming.

*Last updated: 2026-06-26*

---

### Checklist (AST parser)

| Task | Done? |
|------|-------|
| `ASTParser` in `backend/app/parser/ast_parser.py` | Yes |
| `dependencies.py` — module → file resolution | Yes |
| `repository.py` — `parse_repository()` | Yes |
| `cli.py` — terminal output | Yes |
| Structured `ImportInfo` (module, alias, type) | Yes |
| Absolute / from / relative / aliased imports | Yes (covered in `test_parser.py`) |
| Extract classes (name + bases + methods) | Yes |
| Separate module functions vs class methods | Yes |
| `resolved_deps` / `external_deps` classification | Yes (requires `project_files`) |
| Suffix path matching (`app.parser` → `backend/app/parser/…`) | Yes |
| `FileAnalysis` dataclass | Yes |
| CLI: `python -m app.parser.cli <file-or-repo>` | Yes |
| Unit tests in `tests/test_parser.py` | Yes (11 cases) |
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
| `CycleDetector` + `tests/algorithms/test_cycles.py` (8 cases) | Yes |
| `AlgorithmEngine` (PageRank, betweenness, criticality) | No |

### Checklist (pipeline)

| Task | Done? |
|------|-------|
| `AnalysisPipeline` in `backend/app/pipeline/pipeline.py` | Yes |
| Wire `parse_repository` → `GraphBuilder` | Yes |
| `PipelineResult` (`analyses` + `graph`) | Yes |
| CLI: `python -m app.pipeline <repo-path>` | Yes |
| Unit tests in `tests/test_pipeline.py` | Yes (9 cases) |
| Wire `CycleDetector` into pipeline | No |

---

## Big picture

Ripple turns a Python repo into a **dependency graph** and scores each file for architectural importance.

```
Repository (directory)
        │
        ▼
RepositoryParser          ←  parse_repository() in repository.py
        │                   walks tree, calls ASTParser per file
        ▼
FileAnalysis (per file)   ←  canonical parsed representation
        │
        ▼
GraphBuilder              ←  file-level import graph (V1)
        │
        ▼
GraphResult               ←  nodes + edges today; scores later
        │
        ├──► CycleDetector (shipped)  →  CircularDependencyResult
        │         not yet in AnalysisPipeline
        ▼
AlgorithmEngine (planned) →  PageRank, betweenness, criticality
        │
        ▼
PostgreSQL / JSON / API / React
```

**Shipped today:** Parser layer, `GraphBuilder`, `AnalysisPipeline` (parser → graph). Ingestion, algorithms, and API are planned.

`FileAnalysis` is intended to remain the **canonical source of parsed code information** for all current and future graph builders. Parse once; build many graph views from the same `dict[str, FileAnalysis]`.

### Layer map

| Layer | Components | Responsibility |
|-------|------------|----------------|
| **Parser** | `ASTParser`, `FileAnalysis`, RepositoryParser (`parse_repository`) | Read source, walk AST, resolve imports, emit structured facts per file |
| **Graph** | `GraphBuilder`, `GraphResult` | Turn parsed files into a graph view (import graph in V1) |
| **Pipeline** | `AnalysisPipeline`, `PipelineResult` | Orchestrate parse → build without coupling layers |

---

## Design Decisions

Why the parser produces more data than the graph consumes today — and why that is intentional.

### 1. Why `FileAnalysis` contains more than `GraphBuilder` uses

`FileAnalysis` is the **parser's complete output contract**, not the graph's minimal input. A single AST walk can cheaply extract imports, classes, functions, methods, line counts, and syntax-error flags in one pass. Splitting that into separate dataclasses per future graph type would mean either **multiple AST walks** or **fragile partial models**.

The graph layer therefore receives the full record and **selects the fields it needs**. V1's `GraphBuilder` reads only `resolved_deps`. V2 class and function builders will read `classes`, `functions`, `methods`, and `imports` without any parser changes.

### 2. Why file-level dependency graphs only need `resolved_deps`

A **file import graph** models one relationship: *file A imports file B*. That is fully determined by which other project files each module depends on — already normalized into `resolved_deps` by the parser (with `project_files` context).

Fields like `classes` or `functions` describe **structure inside** a file, not **cross-file import edges**. `external_deps` names third-party packages that are deliberately **not** nodes in the file graph. `imports` is the raw structured form; `resolved_deps` is the graph-ready projection for internal files.

Edge direction: `(importer, imported)` — if `crypto.py` changes, files that import it are downstream in impact analysis.

### 3. Why unused fields are preserved, not removed

Removing fields because V1 ignores them would:

- Force a parser redesign when V2 ships
- Break the CLI and tests that already expose classes, functions, and external deps
- Couple graph evolution to parse-time concerns

Unused fields are **latent capability**: zero cost at graph-build time, high value when adding class graphs, library analytics, or enriched node metadata (`line_count`, `has_syntax_error` for UI warnings).

### 4. How this supports future graph types without reparsing

```
parse_repository(repo)  →  dict[str, FileAnalysis]   # once
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
     GraphBuilder      ClassGraphBuilder*    ExternalDepsIndex*
     (resolved_deps)    (classes.bases)       (external_deps)
            │                   │                   │
            ▼                   ▼                   ▼
     GraphResult         ClassGraphResult*     LibraryReport*
```

\*Planned — not implemented.

Each builder is a **pure function** over the same `FileAnalysis` dict. Repository walk and AST parsing happen once per analysis job; new views are additive. This is the main reason `AnalysisPipeline` returns both `analyses` and `graph` in `PipelineResult`.

---

## Future Scope

### V1 — Current

| Aspect | Detail |
|--------|--------|
| Graph type | File-level dependency graph |
| Nodes | Python file paths (`.py`) |
| Edges | Import relationships from `resolved_deps` |
| Components | `ASTParser`, RepositoryParser, `GraphBuilder`, `AnalysisPipeline` |
| Out of scope for V1 graph | External packages as nodes, class/function edges, scores |

### V2 — Richer structure graphs

| Capability | Data source | Example |
|------------|-------------|---------|
| **Class-level graph** | `ClassInfo`, `ClassInfo.bases` | `Admin → User` (inheritance) |
| **Class dependency analysis** | Type usage, constructors, cross-class references (TBD) | `Helper → User` |
| **Function-level graph** | `functions`, `methods` | Module-level call relationships |
| **Function call graph** | AST call-site extraction (new analysis pass or extended walk) | `login()` calls `hash_password()` |
| **Impact analysis** | File graph + traversal | "What breaks if I change file X?" |
| **Enriched file nodes** | `line_count`, class/function counts | Size and complexity in the UI |
| **Library analytics** | `external_deps` per file | Most-used libraries; files depending on `requests` or `numpy` |
| **Graph algorithms** | `GraphResult` → NetworkX | PageRank, betweenness, criticality scores (`CycleDetector` already shipped) |

V2 adds **new builders** and **AlgorithmEngine** (scoring) — not a new parser. Cycle detection is V1-ready as a standalone unit.

### V3 — AI-assisted insights

| Capability | Description |
|------------|-------------|
| **Repository explanations** | Natural-language summaries of architecture and module roles |
| **Architectural insights** | Detect layering violations, god modules, coupling hotspots |
| **Change-risk estimation** | Combine graph centrality, test coverage (if available), and history to score refactor risk |

V3 consumes V1/V2 structured outputs; it does not replace the parser-graph pipeline.

---

## Design choices & things we rectified (parser iteration)

These decisions came from iterating on the parser output and data model. For parser-vs-graph rationale and the V1–V3 roadmap, see [Design Decisions](#design-decisions) and [Future Scope](#future-scope) above.

**Cross-cutting choices:**

- **Modular monolith** — one Python process, folders = components (`parser/`, `graph/`, `pipeline/`, `api/`).
- **Compute vs storage** — NetworkX computes graphs in memory; Postgres stores results later.
- **Parser is pure** — `parse_file(path, content)` takes a string; caller handles disk I/O.
- **Parse once, graph many** — `FileAnalysis` is canonical; future builders share the same `dict[str, FileAnalysis]`.
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
| CLI project | `python -m app.parser.cli path/to/project` | internal paths per file (if root is correct) |
| Python API | `parse_repository(root)` | same as CLI project |
| Manual | `ASTParser(project_files=…)` + loop | same |

---

### 2b. `parse_repository` (`repository.py`)

Walks a directory, skips `SKIP_DIRS` (`.git`, `venv`, `__pycache__`, …), builds `project_files`, parses every `.py` file, returns:

```python
dict[str, FileAnalysis]  # keys are paths relative to the root you passed
```

```python
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
auth = analyses["myapp/auth.py"]
# auth.resolved_deps → ["myapp/models.py", "myapp/utils.py"]
# auth.external_deps → ["os", "requests"]
```

---

### Analysis root convention

**Always analyze from the project root**, not from a package subfolder.

`parse_repository(root)` (and the CLI when given a directory) stores every path **relative to `root`**. Import resolution then maps module names like `app.parser.models` onto those paths:

1. Exact candidates: `app/parser/models.py`, `app/parser/models/__init__.py`, …
2. Suffix match: any path ending in `/app/parser/models.py` (when the root sits *above* the package, e.g. the ripple repo root)

If you pass a **subpackage** as root, paths lose the package prefix and internal imports look external:

| Command (from `backend/`) | Paths collected | `from app.parser.models` |
|---------------------------|-----------------|--------------------------|
| `python -m app.parser.cli .` | `app/parser/models.py`, … | → `resolved_deps` ✓ |
| `python -m app.parser.cli ..` | `backend/app/parser/models.py`, … | → `resolved_deps` via suffix ✓ |
| `python -m app.parser.cli ./app/parser` | `models.py`, `ast_parser.py`, … | → `external_deps: app` ✗ |

The file `models.py` is on disk either way — but the matcher compares **import module strings** to **paths relative to your root**, not “same folder on disk.” `app.parser.models` does not equal `models.py`.

**Why we keep it this way:** production analysis (zip upload, clone, pipeline) always runs from the **uploaded project root**. Guessing package prefixes from a subfolder would add ambiguity (multiple `models.py` files) for a case the product should not hit. Prefer the correct root over smarter path guessing.

**Symptom of a wrong root:** every in-repo import shows up under `external_deps` as the top-level package (`app`), and `resolved_deps` is empty for all files.

**Correct local usage:**

```bash
cd backend
python -m app.parser.cli .                              # backend as project root
python -m app.parser.cli tests/fixtures/mini_repo       # fixture project root
python -m app.parser.cli tests/fixtures/mini_repo myapp/auth.py
```

Also see [README — Analysis root convention](../README.md#analysis-root-convention).

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

**Root must include the package path prefix.** Paths in `project_files` are relative to the analysis root. If the root is a package subfolder, you only get bare names like `utils.py`, which never match `myapp/utils.py`. See [Analysis root convention](#analysis-root-convention).

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
PYTHONPATH=. pytest tests/ -v                    # all 37 tests
PYTHONPATH=. pytest tests/test_parser.py -v      # parser only (11)
PYTHONPATH=. pytest tests/test_graph.py -v       # graph builder only (9)
PYTHONPATH=. pytest tests/test_pipeline.py -v    # pipeline only (9)
PYTHONPATH=. pytest tests/algorithms/ -v         # cycle detection only (8)
```

If you `cd tests/` first, use `PYTHONPATH=.. pytest . -v` — not `pytest tests/`.

**New to pytest?** See [Introduction to pytest](#introduction-to-pytest) (verbose mode, running one test, flags, fixtures, parametrization).

See [Testing overview](#testing-overview) for what each suite covers. For where to run tests in other docs: [README](../README.md#tests) (quick commands), [Roadmap](./Roadmap.md) (milestone checks), [SRS](./SRS_ProjectPlan.md) (requirements traceability).

### 10. Tests (`test_parser.py`)

**11 cases** — `ASTParser` unit tests (inline source) plus `parse_repository()` integration on `tests/fixtures/mini_repo` and the ripple repo root.

| Test | Style | What it proves |
|------|-------|----------------|
| `test_external_import_forms[absolute]` | unit | `import os`, `import numpy as np` → `ImportInfo` + `external_deps` |
| `test_external_import_forms[from_import]` | unit | `from os import path`, `from os.path import join` |
| `test_external_import_forms[aliased]` | unit | `import pandas as pd`, `from collections import defaultdict as dd` |
| `test_relative_imports_resolve_to_project_files[…]` | unit | `.`, `..`, and `from . import` resolve to in-repo paths |
| `test_future_import_ignored` | unit | `from __future__ import annotations` is skipped, not recorded |
| `test_syntax_error_returns_flag_without_raising` | unit | Invalid syntax → `has_syntax_error=True`, empty imports |
| `test_collect_python_files_skips_cache_dirs` | integration | `venv`, `__pycache__`, etc. excluded from file walk |
| `test_parse_repository_mini_repo` | integration | Full fixture walk, internal vs external deps on `auth.py` / `utils.py` |
| `test_module_resolution_matches_path_suffix` | integration | `from app.parser.models` → `backend/app/parser/models.py` when repo root is above `backend/` |

**Fixture:** `tests/fixtures/mini_repo/` — tiny `myapp` package for dependency classification.

**How to run only parser tests:** `PYTHONPATH=. pytest tests/test_parser.py -v`

---

## Phase 1, Week 2 — Graph Builder

**Goal:** Turn many `FileAnalysis` records into one dependency graph: nodes = files, edges = import relationships.

**Files to read in order:**

1. `backend/app/graph/models.py` — `GraphResult`
2. `backend/app/graph/builder.py` — `GraphBuilder.build`
3. `backend/tests/test_graph.py` — unit tests (synthetic `FileAnalysis` fixtures)

```text
backend/app/graph/
├── models.py              # GraphResult, CircularDependencyResult
├── builder.py             # GraphBuilder
└── algorithms/
    ├── base.py            # GraphAlgorithm protocol
    ├── digraph.py         # GraphResult → nx.DiGraph
    └── cycles.py          # CycleDetector (shipped)
```

### 1. Output type (`GraphResult`)

```python
@dataclass
class GraphResult:
    nodes: list[str]                  # sorted file paths
    edges: list[tuple[str, str]]      # (importer, imported)
```

This is the **structural** graph only — no scores yet. `CycleDetector` reads this structure to find circular dependencies. `AlgorithmEngine` will add PageRank, betweenness, and criticality later.

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

**Cycles and self-loops are preserved, not rejected.** A→B→C→A or a file importing itself becomes an edge. Cycle *detection* is `CycleDetector`'s job; the builder just records structure.

**Syntax-error files still participate.** A file with `has_syntax_error=True` is still a node if it's in the dict. Any `resolved_deps` the parser extracted before failing still become edges.

**`GraphResult` stays plain lists.** NetworkX is used only when an algorithm needs it (`graph_result_to_digraph` in `CycleDetector`). That avoids storing the graph twice until needed.

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

**9 unit tests** in `test_graph.py` — synthetic `FileAnalysis` dicts via `make_file()`, no filesystem, no parser. Full test list: [Testing overview — Graph builder tests](#graph-builder-tests-test_graphpy--full-list).

Deliberately **not** tested here: import resolution (`test_parser.py`), end-to-end pipeline (`test_pipeline.py`), cycle detection (`test_cycles.py`).

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

## Phase 1, Week 2 — Cycle Detection

**Goal:** Given a file import graph (`GraphResult`), find every circular dependency and report each loop once in a stable form.

**Files to read in order:**

1. `backend/app/graph/models.py` — `CircularDependencyResult`
2. `backend/app/graph/algorithms/digraph.py` — `graph_result_to_digraph`
3. `backend/app/graph/algorithms/cycles.py` — `normalize_cycle`, `CycleDetector`
4. `backend/tests/algorithms/test_cycles.py` — 8 unit tests

```text
backend/app/graph/algorithms/
├── base.py       # GraphAlgorithm protocol (run(graph) → T)
├── digraph.py    # GraphResult → nx.DiGraph
└── cycles.py     # CycleDetector
```

**Status:** Implemented and unit-tested. **Not** wired into `AnalysisPipeline` yet — call it yourself on a `GraphResult`.

### 1. Output type (`CircularDependencyResult`)

```python
@dataclass
class CircularDependencyResult:
    cycles: list[list[str]]   # each cycle is an ordered list of file paths

    @property
    def has_cycles(self) -> bool: ...

    @property
    def cycle_count(self) -> int: ...
```

Example: `[["myapp/a.py", "myapp/b.py", "myapp/c.py"]]` means A imports B, B imports C, C imports A.

### 2. API

```python
from app.graph import CycleDetector, GraphBuilder
from app.parser.repository import parse_repository

analyses = parse_repository("tests/fixtures/mini_repo")
graph = GraphBuilder().build(analyses)
result = CycleDetector().detect(graph)   # or .run(graph) — same method

# result.cycles, result.has_cycles, result.cycle_count
```

| Input | Type | Notes |
|-------|------|-------|
| `graph` | `GraphResult` | Nodes + directed edges only — no parser, no filesystem |

`detect` is an alias of `run` (`detect = run` on the class).

### 3. How detection works

```
GraphResult { nodes, edges }
        │
        ▼
graph_result_to_digraph()     # plain lists → nx.DiGraph
        │
        ▼
nx.simple_cycles(digraph)     # every simple cycle (may include rotations)
        │
        ▼
normalize_cycle(cycle)        # rotate to lex-smallest start node
        │
        ▼
dedupe via set[tuple]         # same loop once
        │
        ▼
sort by (length, path)        # stable output for tests / UI
        │
        ▼
CircularDependencyResult
```

**NetworkX `simple_cycles`:** finds directed cycles that do not repeat nodes (except start/end). For A↔B it may yield both `[A, B]` and `[B, A]` — those are the **same** loop starting at different nodes.

### 4. Why `normalize_cycle` exists

```python
def normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    start = cycle.index(min(cycle))
    rotated = cycle[start:] + cycle[:start]
    return tuple(rotated)
```

| Input rotation | After normalize |
|----------------|-----------------|
| `["b.py", "c.py", "a.py"]` | `("a.py", "b.py", "c.py")` |
| `["a.py", "b.py", "c.py"]` | `("a.py", "b.py", "c.py")` |
| `["c.py", "a.py", "b.py"]` | `("a.py", "b.py", "c.py")` |

Returns a **tuple** so it can live in a `set` for deduplication (lists are not hashable).

Without this, the UI and tests would see the same circular dependency multiple times.

### 5. Design choices

**Operates on `GraphResult` only.** No re-parsing. Graph builder preserves cycles as edges; this layer *labels* them.

**Self-loops count.** A file that imports itself (`auth.py` → `auth.py`) is a one-node cycle.

**Deterministic order.** Cycles are sorted by length, then by path list, so output is stable across runs.

**Not in the pipeline yet.** `AnalysisPipeline` still returns only `analyses` + `graph`. Wiring `CycleDetector` is the next integration step (attach cycles to `PipelineResult` / CLI / API).

### 6. Test cases (`test_cycles.py`)

**8 unit tests** — synthetic graphs only (no parser, no disk). Most use the `build_graph` fixture (`GraphBuilder` + `make_file`); normalization tests build `GraphResult` by hand.

Run from `backend/`:

```bash
PYTHONPATH=. pytest tests/algorithms/test_cycles.py -v
```

| Test | What it proves |
|------|----------------|
| `test_empty_graph_has_no_cycles` | Empty `GraphResult` → `cycles == []`, `has_cycles` false, `cycle_count == 0` |
| `test_acyclic_repository_has_no_cycles` | Tree-shaped imports (auth → utils/models) → no cycles |
| `test_simple_three_node_cycle` | A→B→C→A detected; path starts at lex-smallest node (`a.py`) |
| `test_self_loop_is_a_cycle` | File importing itself → `[["myapp/auth.py"]]` |
| `test_two_disjoint_cycles` | Independent A↔B and X↔Y both reported (`cycle_count == 2`) |
| `test_cycle_normalized_to_lexicographic_start` | Node list order does not change the reported start node |
| `test_detect_deduplicates_rotations` | A→B→A is **one** cycle, not two rotations |
| `test_run_matches_detect` | `run()` and `detect()` return the same result (alias) |

**What these tests deliberately skip:** pipeline wiring, API/JSON output, frontend cycle warnings, PageRank/scoring.

Also listed under [Testing overview — Cycle detection tests](#cycle-detection-tests-test_cyclespy--full-list).

### 7. Try it yourself

```python
from app.graph import CycleDetector, GraphBuilder, GraphResult

# Hand-built cycle: a → b → c → a
graph = GraphResult(
    nodes=["myapp/a.py", "myapp/b.py", "myapp/c.py"],
    edges=[
        ("myapp/a.py", "myapp/b.py"),
        ("myapp/b.py", "myapp/c.py"),
        ("myapp/c.py", "myapp/a.py"),
    ],
)
print(CycleDetector().detect(graph).cycles)
# [['myapp/a.py', 'myapp/b.py', 'myapp/c.py']]
```

Or on a real project root (see [Analysis root convention](#analysis-root-convention)):

```python
from app.graph import CycleDetector, GraphBuilder
from app.parser.repository import parse_repository

graph = GraphBuilder().build(parse_repository("."))
print(CycleDetector().detect(graph))
```

---

## Phase 1 — Analysis Pipeline

**Goal:** Connect parser and graph in one call — parse once, build graph, return both.

```python
from app.pipeline import AnalysisPipeline

result = AnalysisPipeline().run("tests/fixtures/mini_repo")
result.analyses   # dict[str, FileAnalysis]
result.graph      # GraphResult
```

CLI: `python -m app.pipeline <repo-path>` (directory only today).

### Tests (`test_pipeline.py`)

**9 tests** — mostly temp repos on disk (real parse → graph); one case uses pytest `monkeypatch` to stub `parse_repository`.

| Test | Style | What it proves |
|------|-------|----------------|
| `test_empty_graph` | temp repo | Empty directory → no analyses, empty graph |
| `test_single_node` | temp repo | One `.py` file → one node, zero edges |
| `test_simple_dependency_graph` | temp repo | Multi-file imports → correct edges end-to-end |
| `test_dedup_edges` | temp repo | Duplicate imports of same module → one edge |
| `test_ignore_missing_deps` | monkeypatch | `resolved_deps` pointing outside repo → no edges |
| `test_deterministic_ordering` | temp repo | Two runs return identical sorted nodes/edges |
| `test_small_cycle` | temp repo | `a → b → c → a` cycle preserved through pipeline |
| `test_run_parses_mini_repo_integration` | fixture | `mini_repo` parse + graph matches `expected_edges()` |
| `test_run_raises_for_non_directory` | error path | File path (not dir) → `NotADirectoryError` |

**Helpers:** `write_repo()` builds temp Python trees; `expected_edges()` derives edges from `analyses` for assertions.

**Monkeypatch note:** `test_ignore_missing_deps` temporarily replaces `parse_repository` with a lambda returning hand-built `FileAnalysis` dicts — the real parser cannot produce a `resolved_deps` entry for a file absent from the repo.

---

## Introduction to pytest

**pytest** is Python's most common test runner. You write small functions that call your code and use `assert` to check the result; pytest discovers those functions, runs them, and reports pass/fail.

Ripple uses pytest for all backend tests (`backend/tests/`). It is listed in `backend/requirements.txt` and installed when you set up the virtualenv.

### Setup (one time)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

After that, `pytest` is available inside the activated venv. You can also run it as `python -m pytest` (same thing).

### Where to run commands

Always run pytest from **`backend/`**, with **`PYTHONPATH=.`** so Python can import the `app` package:

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

| Mistake | What happens |
|---------|----------------|
| Run from repo root without `cd backend` | Paths like `tests/test_parser.py` may not resolve |
| Omit `PYTHONPATH=.` | `ModuleNotFoundError: No module named 'app'` |
| `cd tests/` then `pytest tests/` | Looks for `tests/tests/` — use `PYTHONPATH=.. pytest . -v` instead |

### What a test looks like

Pytest **auto-discovers** functions whose names start with `test_` in files named `test_*.py`:

```python
def test_two_plus_two():
    assert 2 + 2 == 4
```

If the assertion is true, the test **passes**. If it raises `AssertionError`, the test **fails** and pytest prints what went wrong.

Ripple example (from `test_parser.py`):

```python
def test_future_import_ignored(parser: ASTParser) -> None:
    analysis = parser.parse_file(
        "myapp/auth/session.py",
        "from __future__ import annotations\nimport os\n",
    )
    assert analysis.imports == [ImportInfo(module="os", type="import")]
    assert analysis.external_deps == ["os"]
```

No special test class or boilerplate — plain functions and `assert`.

### Output modes: default, verbose, quiet

| Flag | Command | What you see |
|------|---------|--------------|
| *(none)* | `pytest tests/` | One `.` per passed test; `F` for failure; summary at the end |
| **`-v`** (verbose) | `pytest tests/ -v` | **One line per test** with `PASSED` or `FAILED` and the full test name — best for learning and debugging |
| **`-q`** (quiet) | `pytest tests/ -q` | Minimal output: just a progress bar of dots and a one-line summary |

**Use `-v` while you're learning** — you see exactly which tests ran:

```text
tests/test_parser.py::test_external_import_forms[absolute] PASSED
tests/test_parser.py::test_external_import_forms[from_import] PASSED
...
======================== 37 passed in 0.47s ========================
```

Parametrized tests (see below) show the case name in brackets, e.g. `[absolute]`, `[from_import]`.

### Running a subset of tests

| Goal | Command |
|------|---------|
| All tests | `PYTHONPATH=. pytest tests/ -v` |
| One file | `PYTHONPATH=. pytest tests/test_parser.py -v` |
| One directory | `PYTHONPATH=. pytest tests/algorithms/ -v` |
| One test by name | `PYTHONPATH=. pytest tests/test_parser.py::test_future_import_ignored -v` |
| One parametrized case | `PYTHONPATH=. pytest tests/test_parser.py::test_external_import_forms[absolute] -v` |
| Name pattern (`-k`) | `PYTHONPATH=. pytest tests/ -k "cycle" -v` — runs tests whose names contain `cycle` |
| List without running | `PYTHONPATH=. pytest tests/ --collect-only` |

The `::` syntax is **file path :: function name** (and optionally `[param_id]` for parametrized cases).

### Useful flags when something breaks

| Flag | Meaning |
|------|---------|
| `-v` | Verbose — show each test name |
| `-q` | Quiet — fewer lines |
| `-x` | Stop on the **first** failure (don't run the rest) |
| `-s` | Show `print()` output (pytest normally captures it) |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | All tests passed |
| `1` | At least one test failed |
| `2` | Pytest itself errored (bad arguments, collection error, etc.) |
| `5` | No tests collected (wrong path or empty file) |

CI and scripts use this: `pytest` returning non-zero means "don't ship."

### Features Ripple tests use

**Fixtures** — reusable setup passed into tests by name:

```python
@pytest.fixture
def parser() -> ASTParser:
    return ASTParser(project_files=RELATIVE_IMPORT_FILES)

def test_future_import_ignored(parser: ASTParser) -> None:
    analysis = parser.parse_file(...)   # pytest injects the fixture
```

**Parametrize** — one test function, many input cases (counts as multiple tests):

```python
@pytest.mark.parametrize("content,expected", [("import os", ["os"]), ...], ids=["absolute", "from_import"])
def test_external_import_forms(parser, content, expected):
    ...
```

That is why `pytest --collect-only` reports **11** tests in `test_parser.py` even though there are fewer function definitions — parametrized cases each count separately.

**Monkeypatch** (in `test_pipeline.py`) — temporarily replace a function for one test without changing production code.

### Typical workflow

1. Change code in `backend/app/…`
2. Run the **smallest** relevant suite first (e.g. parser → `test_parser.py`)
3. Use **`-v`** to see which case failed; use **`::test_name`** to re-run only that test
4. When green, run **`PYTHONPATH=. pytest tests/ -v`** for the full suite before committing

### Further reading

- [pytest documentation](https://docs.pytest.org/) — official reference
- [Testing overview](#testing-overview) below — what each Ripple test file covers
- [README — Tests](../README.md#tests) — copy-paste command cheat sheet

---

## Testing overview

**37 tests** across four suites. Run all from `backend/` with `PYTHONPATH=. pytest tests/ -v`.

This section is the **detailed test catalog** — what each file proves and how layers are isolated. For pytest basics (first time using it), see [Introduction to pytest](#introduction-to-pytest). For copy-paste commands when developing, see [README](../README.md#tests). For which tests gate roadmap milestones, see [Roadmap](./Roadmap.md). For requirements-to-test mapping, see [SRS §10–12](./SRS_ProjectPlan.md#10-functional-requirements).

### Strategy by layer

| Suite | File | Tests | Style | What it isolates |
|-------|------|-------|-------|------------------|
| Parser | `test_parser.py` | 11 | Unit + integration | `ASTParser` import forms; `parse_repository` walk + resolution |
| Graph | `test_graph.py` | 9 | Unit | `GraphBuilder` rules via synthetic `FileAnalysis` dicts |
| Pipeline | `test_pipeline.py` | 9 | Integration + unit | `AnalysisPipeline` wiring; temp repos + one monkeypatch |
| Cycles | `tests/algorithms/test_cycles.py` | 8 | Unit | `CycleDetector` on synthetic `GraphResult` |

```
test_parser.py     →  ASTParser / parse_repository  →  FileAnalysis
test_graph.py      →  GraphBuilder                  →  GraphResult     (no parser)
test_pipeline.py   →  AnalysisPipeline              →  PipelineResult  (parse + graph)
test_cycles.py     →  CycleDetector                 →  CircularDependencyResult
```

Parser tests do **not** call `GraphBuilder`. Graph tests do **not** call `parse_repository`. Pipeline tests exercise parse → graph except where monkeypatch injects controlled parse output. Cycle tests use `GraphResult` only — not wired into `AnalysisPipeline` yet.

### Parser tests (`test_parser.py`) — full list

| Test | What it proves |
|------|----------------|
| `test_external_import_forms[absolute]` | Absolute imports recorded; classified as external without `project_files` |
| `test_external_import_forms[from_import]` | From-imports for stdlib modules |
| `test_external_import_forms[aliased]` | `as` aliases on import and from-import |
| `test_relative_imports_resolve_to_project_files[same_package]` | `from .utils import …` → in-repo file |
| `test_relative_imports_resolve_to_project_files[parent_package]` | `from ..config import …` → parent package file |
| `test_relative_imports_resolve_to_project_files[package_init]` | `from . import utils` |
| `test_future_import_ignored` | `__future__` imports omitted from `imports` |
| `test_syntax_error_returns_flag_without_raising` | Broken file does not crash parser |
| `test_collect_python_files_skips_cache_dirs` | `SKIP_DIRS` honored during walk |
| `test_parse_repository_mini_repo` | End-to-end fixture: all files parsed, deps classified |
| `test_module_resolution_matches_path_suffix` | Long repo paths resolve via suffix match |

### Graph builder tests (`test_graph.py`) — full list

| Test | What it proves |
|------|----------------|
| `test_empty_repository` | `{}` → no nodes, no edges |
| `test_single_file_no_dependencies` | Isolated file is a node with zero edges |
| `test_simple_dependency_graph` | Fan-out + shared dependency; correct edge direction |
| `test_missing_and_external_dependencies_ignored` | Out-of-repo `resolved_deps` and `external_deps` → no edges |
| `test_duplicate_resolved_deps_deduplicated` | Repeated `resolved_deps` → one edge |
| `test_cyclic_imports_preserved` | A→B→C→A kept intact |
| `test_self_import_creates_self_loop` | Self-loop edge when file imports itself |
| `test_dict_key_used_as_node_not_file_path_field` | Node identity follows dict key, not `file_path` field |
| `test_syntax_error_file_still_contributes_nodes_and_edges` | `has_syntax_error=True` still produces nodes/edges |

Uses `make_file()` helper for realistic `FileAnalysis` fixtures without touching the filesystem.

### Cycle detection tests (`test_cycles.py`) — full list

**Study guide (how `CycleDetector` / `normalize_cycle` work):** [Phase 1, Week 2 — Cycle Detection](#phase-1-week-2--cycle-detection).

| Test | What it proves |
|------|----------------|
| `test_empty_graph_has_no_cycles` | Empty `GraphResult` → no cycles |
| `test_acyclic_repository_has_no_cycles` | Tree-shaped graph → `has_cycles` false |
| `test_simple_three_node_cycle` | A→B→C→A detected and normalized |
| `test_self_loop_is_a_cycle` | Single-node cycle |
| `test_two_disjoint_cycles` | Multiple independent cycles |
| `test_cycle_normalized_to_lexicographic_start` | Rotation canonicalization |
| `test_detect_deduplicates_rotations` | Same cycle not reported twice |
| `test_run_matches_detect` | `run()` alias equals `detect()` |

Synthetic `GraphResult` only — no parser, no filesystem, no pipeline. Run only cycle tests: `PYTHONPATH=. pytest tests/algorithms/ -v`

### Not covered yet

| Area | Notes |
|------|-------|
| Single-file pipeline input | CLI accepts dirs only |
| PageRank / betweenness / criticality | Planned `AlgorithmEngine` |
| `CycleDetector` in `AnalysisPipeline` | Implemented but not wired |
| API / `test_api.py` | Stub only |
| Syntax-error files through pipeline | Covered in graph unit tests only |
| Five real open-source repos | Roadmap Week 1 milestone — manual / future |

---

## Coming next (not implemented yet)

Read [Roadmap.md](./Roadmap.md) for week-by-week tasks. Short preview:

| Component | What it will do |
|-----------|-----------------|
| Wire `CycleDetector` into `AnalysisPipeline` | Attach `CircularDependencyResult` to pipeline output / CLI |
| `AlgorithmEngine` | PageRank, betweenness, criticality score |
| `IngestionService` | Unzip repo, walk tree, filter `venv/` / `__pycache__` |
| REST API + Postgres | Persist results, async jobs, graph/impact endpoints |

`AnalysisPipeline` (parser → graph) and `CycleDetector` (standalone) are **shipped**. See [Future Scope](#future-scope) for V2/V3 capabilities.

---

## Dependency cheat sheet

| Package | Used for |
|---------|----------|
| `fastapi` + `uvicorn` | HTTP API |
| `sqlalchemy` + `psycopg2` | Postgres ORM |
| `networkx` | `CycleDetector` (`nx.simple_cycles`); PageRank/betweenness planned |
| `pytest` + `httpx` | Backend tests — see [Introduction to pytest](#introduction-to-pytest) |

---

*Add a new major section here each time a component ships (GraphBuilder, CycleDetector, AlgorithmEngine, …).*

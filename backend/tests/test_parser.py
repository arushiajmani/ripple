"""Parser layer tests.

Unit-style: ASTParser.parse_file() with inline source (import forms, edge cases).
Integration: parse_repository() / collect_python_files() on disk fixtures.

Run from backend/:
    PYTHONPATH=. pytest tests/test_parser.py -v

pytest primer (verbose mode, flags, fixtures): docs/learn.md#introduction-to-pytest
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.parser.ast_parser import ASTParser
from app.parser.models import ImportInfo
from app.parser.repository import collect_python_files, parse_repository

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"

# Project layout for relative-import resolution (unit tests only).
RELATIVE_IMPORT_FILES = {
    "myapp/__init__.py",
    "myapp/auth/session.py",
    "myapp/auth/utils.py",
    "myapp/config.py",
}


@pytest.fixture
def parser() -> ASTParser:
    return ASTParser(project_files=RELATIVE_IMPORT_FILES)


# --- External imports: absolute, from-import, aliased ---

@pytest.mark.parametrize(
    ("content", "expected_imports", "expected_external"),
    [
        (
            "import os\nimport numpy as np\n",
            [
                ImportInfo(module="os", type="import"),
                ImportInfo(module="numpy", alias="np", type="import"),
            ],
            ["os", "numpy"],
        ),
        (
            "from os import path\nfrom os.path import join\n",
            [
                ImportInfo(module="os", name="path", type="from_import"),
                ImportInfo(module="os.path", name="join", type="from_import"),
            ],
            ["os"],
        ),
        (
            "import pandas as pd\nfrom collections import defaultdict as dd\n",
            [
                ImportInfo(module="pandas", alias="pd", type="import"),
                ImportInfo(
                    module="collections",
                    name="defaultdict",
                    alias="dd",
                    type="from_import",
                ),
            ],
            ["pandas", "collections"],
        ),
    ],
    ids=["absolute", "from_import", "aliased"],
)
def test_external_import_forms(
    parser: ASTParser,
    content: str,
    expected_imports: list[ImportInfo],
    expected_external: list[str],
) -> None:
    analysis = parser.parse_file("standalone.py", content)

    assert analysis.imports == expected_imports
    assert analysis.external_deps == expected_external
    assert analysis.resolved_deps == []


@pytest.mark.parametrize(
    ("content", "expected_display"),
    [
        ("import os\n", "import os"),
        ("import requests\n", "import requests"),
        ("import numpy as np\n", "import numpy as np"),
        ("from os import path\n", "from os import path"),
    ],
    ids=["import_os", "import_requests", "import_aliased", "from_import"],
)
def test_import_display_strings(parser: ASTParser, content: str, expected_display: str) -> None:
    analysis = parser.parse_file("standalone.py", content)
    assert analysis.imports[0].display == expected_display


# --- Relative imports: same package, parent package, package __init__ ---

@pytest.mark.parametrize(
    ("content", "file_path", "expected_imports", "expected_resolved"),
    [
        (
            "from .utils import helper\n",
            "myapp/auth/session.py",
            [ImportInfo(module="myapp.auth.utils", name="helper", type="from_import")],
            ["myapp/auth/utils.py"],
        ),
        (
            "from ..config import settings\n",
            "myapp/auth/session.py",
            [ImportInfo(module="myapp.config", name="settings", type="from_import")],
            ["myapp/config.py"],
        ),
        (
            "from . import utils\n",
            "myapp/auth/session.py",
            [ImportInfo(module="myapp.auth.utils", name="utils", type="from_import")],
            ["myapp/auth/utils.py"],
        ),
    ],
    ids=["same_package", "parent_package", "package_init"],
)
def test_relative_imports_resolve_to_project_files(
    parser: ASTParser,
    content: str,
    file_path: str,
    expected_imports: list[ImportInfo],
    expected_resolved: list[str],
) -> None:
    analysis = parser.parse_file(file_path, content)

    assert analysis.imports == expected_imports
    assert analysis.resolved_deps == expected_resolved
    assert analysis.external_deps == []


# --- Edge cases: __future__, syntax errors ---

def test_future_import_ignored(parser: ASTParser) -> None:
    analysis = parser.parse_file(
        "myapp/auth/session.py",
        "from __future__ import annotations\nimport os\n",
    )

    assert analysis.imports == [ImportInfo(module="os", type="import")]
    assert analysis.external_deps == ["os"]
    assert not analysis.has_syntax_error


def test_syntax_error_returns_flag_without_raising(parser: ASTParser) -> None:
    analysis = parser.parse_file("broken.py", "def oops(\n")

    assert analysis.has_syntax_error
    assert analysis.imports == []
    assert analysis.classes == []
    assert analysis.functions == []


# --- Repository integration: file walk + mini_repo fixture ---

def test_collect_python_files_skips_cache_dirs() -> None:
    files = collect_python_files(FIXTURE_ROOT)

    assert "myapp/auth.py" in files
    assert "myapp/utils.py" in files
    assert not any("__pycache__" in path for path in files)


def test_parse_repository_mini_repo() -> None:
    """File walk + per-file analysis + internal/external classification on fixture."""
    analyses = parse_repository(FIXTURE_ROOT)
    expected_files = collect_python_files(FIXTURE_ROOT)

    assert set(analyses) == expected_files

    auth = analyses["myapp/auth.py"]
    assert "myapp/models.py" in auth.resolved_deps
    assert "myapp/utils.py" in auth.resolved_deps
    assert "os" in auth.external_deps
    assert "requests" in auth.external_deps

    utils = analyses["myapp/utils.py"]
    assert utils.resolved_deps == ["myapp/models.py"]
    assert utils.external_deps == ["json"]

    # models ↔ utils cycle (fixture is intentionally cyclic)
    models = analyses["myapp/models.py"]
    assert models.resolved_deps == ["myapp/utils.py"]


# --- Suffix resolution on real repo layout (ripple itself) ---

def test_module_resolution_matches_path_suffix() -> None:
    """Suffix matching: imports resolve when repo root is above backend/."""
    repo_root = Path(__file__).resolve().parents[2]
    analyses = parse_repository(repo_root)
    parser_init = analyses["backend/app/parser/__init__.py"]

    assert "backend/app/parser/models.py" in parser_init.resolved_deps
    assert "app" not in parser_init.external_deps

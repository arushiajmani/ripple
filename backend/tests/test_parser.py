from __future__ import annotations

from pathlib import Path

from app.parser.repo_parser import collect_python_files, parse_repository

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mini_repo"


def test_collect_python_files_skips_cache_dirs() -> None:
    files = collect_python_files(FIXTURE_ROOT)
    assert "myapp/auth.py" in files
    assert "myapp/utils.py" in files
    assert not any("__pycache__" in path for path in files)


def test_parse_repository_returns_all_files() -> None:
    analyses = parse_repository(FIXTURE_ROOT)
    assert set(analyses) == collect_python_files(FIXTURE_ROOT)
    assert all(analysis.file_path in analyses for analysis in analyses.values())


def test_parse_repository_resolves_internal_deps() -> None:
    analyses = parse_repository(FIXTURE_ROOT)
    auth = analyses["myapp/auth.py"]

    assert "myapp/models.py" in auth.resolved_deps
    assert "myapp/utils.py" in auth.resolved_deps
    assert "os" in auth.external_deps
    assert "requests" in auth.external_deps


def test_parse_repository_external_only_for_utils() -> None:
    analyses = parse_repository(FIXTURE_ROOT)
    utils = analyses["myapp/utils.py"]

    assert utils.resolved_deps == ["myapp/models.py"]
    assert utils.external_deps == ["json"]

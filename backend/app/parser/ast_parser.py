from __future__ import annotations

import ast
import logging
import time
from pathlib import Path

from app.parser.dependencies import classify_dependencies
from app.parser.models import (
    ClassInfo,
    FileAnalysis,
    FunctionInfo,
    ImportInfo,
)

logger = logging.getLogger(__name__)


class ASTParser:
    def __init__(
        self,
        project_root: str | None = None,
        project_files: set[str] | None = None,
    ) -> None:
        self.project_root = project_root
        self.project_files = project_files or set()

    def parse_file(self, file_path: str, content: str) -> FileAnalysis:
        analysis, _, _ = self.parse_file_timed(file_path, content)
        return analysis

    def parse_file_timed(
        self, file_path: str, content: str
    ) -> tuple[FileAnalysis, float, float]:
        """Parse one file; return ``(analysis, ast_ms, import_resolution_ms)``."""
        normalized_path = file_path.replace("\\", "/")
        line_count = content.count("\n") + (1 if content else 0)

        try:
            tree = ast.parse(content, filename=normalized_path)
        except SyntaxError:
            logger.warning("Syntax error in %s", normalized_path)
            return (
                FileAnalysis(
                    file_path=normalized_path,
                    line_count=line_count,
                    has_syntax_error=True,
                ),
                0.0,
                0.0,
            )

        ast_start = time.perf_counter()
        imports: list[ImportInfo] = []
        module_names: list[str] = []
        classes: list[ClassInfo] = []
        functions: list[FunctionInfo] = []
        methods: list[FunctionInfo] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    imports.append(
                        ImportInfo(
                            module=module,
                            alias=alias.asname,
                            type="import",
                        )
                    )
                    module_names.append(module)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    continue
                module = self._resolve_import_module(normalized_path, node)
                if module:
                    for alias in node.names:
                        imports.append(
                            ImportInfo(
                                module=module,
                                name=alias.name,
                                alias=alias.asname,
                                type="from_import",
                            )
                        )
                    module_names.append(module)
            elif isinstance(node, ast.ClassDef):
                if self._is_top_level(tree, node):
                    classes.append(
                        ClassInfo(
                            name=node.name,
                            bases=self._extract_base_names(node),
                            methods=self._extract_method_names(node),
                        )
                    )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parent = self._parent_class_name(tree, node)
                if parent is not None:
                    methods.append(
                        FunctionInfo(name=node.name, parent_class=parent)
                    )
                elif self._is_top_level(tree, node):
                    functions.append(FunctionInfo(name=node.name))

        ast_ms = (time.perf_counter() - ast_start) * 1000.0

        resolve_start = time.perf_counter()
        resolved_deps, external_deps = classify_dependencies(
            module_names, self.project_files
        )
        resolve_ms = (time.perf_counter() - resolve_start) * 1000.0

        return (
            FileAnalysis(
                file_path=normalized_path,
                imports=imports,
                resolved_deps=resolved_deps,
                external_deps=external_deps,
                classes=classes,
                functions=functions,
                methods=methods,
                line_count=line_count,
                has_syntax_error=False,
            ),
            ast_ms,
            resolve_ms,
        )

    def _extract_method_names(self, node: ast.ClassDef) -> list[str]:
        methods: list[str] = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(child.name)
        return methods

    def _resolve_import_module(
        self, file_path: str, node: ast.ImportFrom
    ) -> str | None:
        if node.level == 0:
            return node.module

        package_parts = Path(file_path).parent.as_posix().split("/")
        package_parts = [part for part in package_parts if part and part != "."]

        trim = max(0, node.level - 1)
        if trim:
            package_parts = package_parts[:-trim] if trim <= len(package_parts) else []

        if node.module:
            package_parts.extend(node.module.split("."))
        elif len(node.names) == 1 and node.names[0].name != "*":
            package_parts.append(node.names[0].name)

        return ".".join(package_parts) if package_parts else None

    def _extract_base_names(self, node: ast.ClassDef) -> list[str]:
        bases: list[str] = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(ast.unparse(base))
        return bases

    def _is_top_level(self, tree: ast.AST, node: ast.AST) -> bool:
        return any(child is node for child in tree.body)

    def _parent_class_name(
        self, tree: ast.AST, node: ast.AST
    ) -> str | None:
        return self._find_parent_class(tree.body, node)

    def _find_parent_class(
        self, body: list[ast.stmt], node: ast.AST
    ) -> str | None:
        for child in body:
            if isinstance(child, ast.ClassDef):
                if node in ast.walk(child) and node is not child:
                    if any(
                        stmt is node
                        for stmt in child.body
                        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ):
                        return child.name
                    nested = self._find_parent_class(child.body, node)
                    if nested is not None:
                        return nested
        return None


if __name__ == "__main__":
    from app.parser.cli import main

    main()

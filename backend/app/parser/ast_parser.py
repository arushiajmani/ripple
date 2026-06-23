from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

from app.parser.models import ClassInfo, FileAnalysis, FunctionInfo, ImportInfo

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
        normalized_path = file_path.replace("\\", "/")
        line_count = content.count("\n") + (1 if content else 0)

        try:
            tree = ast.parse(content, filename=normalized_path)
        except SyntaxError:
            logger.warning("Syntax error in %s", normalized_path)
            return FileAnalysis(
                file_path=normalized_path,
                line_count=line_count,
                has_syntax_error=True,
            )

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

        resolved_deps, external_deps = self._classify_dependencies(
            module_names
        )

        return FileAnalysis(
            file_path=normalized_path,
            imports=imports,
            resolved_deps=resolved_deps,
            external_deps=external_deps,
            classes=classes,
            functions=functions,
            methods=methods,
            line_count=line_count,
            has_syntax_error=False,
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

    def _classify_dependencies(
        self, module_names: list[str]
    ) -> tuple[list[str], list[str]]:
        if not self.project_files:
            return [], self._external_modules(module_names)

        resolved: list[str] = []
        external: list[str] = []
        seen_resolved: set[str] = set()
        seen_external: set[str] = set()

        for module in module_names:
            resolved_path = self._module_to_file_path(module)
            top_level = module.split(".")[0]

            if resolved_path is not None:
                if resolved_path not in seen_resolved:
                    seen_resolved.add(resolved_path)
                    resolved.append(resolved_path)
            elif top_level not in seen_external:
                seen_external.add(top_level)
                external.append(top_level)

        return resolved, external

    def _external_modules(self, module_names: list[str]) -> list[str]:
        external: list[str] = []
        seen: set[str] = set()
        for module in module_names:
            top_level = module.split(".")[0]
            if top_level not in seen:
                seen.add(top_level)
                external.append(top_level)
        return external

    def _module_to_file_path(self, module: str) -> str | None:
        if not self.project_files:
            return None

        parts = module.split(".")
        candidates = [
            "/".join(parts) + ".py",
            "/".join(parts) + "/__init__.py",
        ]
        if len(parts) > 1:
            candidates.append("/".join(parts[:-1]) + ".py")

        for candidate in candidates:
            if candidate in self.project_files:
                return candidate
        return None


def _print_analysis(analysis: FileAnalysis) -> None:
    print(f"file_path: {analysis.file_path}")
    print(f"line_count: {analysis.line_count}")
    print(f"has_syntax_error: {analysis.has_syntax_error}")
    print("imports:")
    for item in analysis.imports:
        print(f"  - {item.display}")
    print("resolved_deps:")
    for item in analysis.resolved_deps:
        print(f"  - {item}")
    print("external_deps:")
    for item in analysis.external_deps:
        print(f"  - {item}")
    print("classes:")
    for cls in analysis.classes:
        if cls.bases:
            bases = ", ".join(cls.bases)
            print(f"  - {cls.name} (bases: {bases})")
        else:
            print(f"  - {cls.name}")
        for method in cls.methods:
            print(f"      - {method}")
    print("functions:")
    for fn in analysis.functions:
        print(f"  - {fn.name}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.parser.ast_parser <path-to-file.py>", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.is_file():
        print(f"File not found: {target}", file=sys.stderr)
        sys.exit(1)

    content = target.read_text(encoding="utf-8", errors="ignore")
    parser = ASTParser()
    analysis = parser.parse_file(target.as_posix(), content)
    _print_analysis(analysis)


if __name__ == "__main__":
    main()

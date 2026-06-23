from __future__ import annotations

import sys
from pathlib import Path

from app.parser.ast_parser import ASTParser
from app.parser.models import FileAnalysis
from app.parser.repository import parse_repository


def print_analysis(analysis: FileAnalysis) -> None:
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
        print(
            "Usage: python -m app.parser.cli <file-or-repo> [relative-file]",
            file=sys.stderr,
        )
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()

    if target.is_dir():
        analyses = parse_repository(target)
        if len(sys.argv) > 2:
            rel_path = sys.argv[2].replace("\\", "/")
            analysis = analyses.get(rel_path)
            if analysis is None:
                print(f"File not found in repo: {rel_path}", file=sys.stderr)
                sys.exit(1)
            print("=" * 60)
            print_analysis(analysis)
            return

        for analysis in analyses.values():
            print("=" * 60)
            print_analysis(analysis)
            print()
        return

    if not target.is_file():
        print(f"Path not found: {target}", file=sys.stderr)
        sys.exit(1)

    content = target.read_text(encoding="utf-8", errors="ignore")
    parser = ASTParser()
    analysis = parser.parse_file(target.as_posix(), content)
    print_analysis(analysis)


if __name__ == "__main__":
    main()

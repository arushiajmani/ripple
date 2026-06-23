from __future__ import annotations


def external_modules(module_names: list[str]) -> list[str]:
    external: list[str] = []
    seen: set[str] = set()
    for module in module_names:
        top_level = module.split(".")[0]
        if top_level not in seen:
            seen.add(top_level)
            external.append(top_level)
    return external


def module_to_file_path(module: str, project_files: set[str]) -> str | None:
    if not project_files:
        return None

    parts = module.split(".")
    candidates = [
        "/".join(parts) + ".py",
        "/".join(parts) + "/__init__.py",
    ]
    if len(parts) > 1:
        candidates.append("/".join(parts[:-1]) + ".py")

    for candidate in candidates:
        if candidate in project_files:
            return candidate

    module_path = "/".join(parts)
    suffix_matches = [
        path
        for path in project_files
        if path.endswith(f"/{module_path}.py")
        or path.endswith(f"/{module_path}/__init__.py")
    ]
    if suffix_matches:
        return min(suffix_matches, key=len)

    return None


def classify_dependencies(
    module_names: list[str],
    project_files: set[str],
) -> tuple[list[str], list[str]]:
    if not project_files:
        return [], external_modules(module_names)

    resolved: list[str] = []
    external: list[str] = []
    seen_resolved: set[str] = set()
    seen_external: set[str] = set()

    for module in module_names:
        resolved_path = module_to_file_path(module, project_files)
        top_level = module.split(".")[0]

        if resolved_path is not None:
            if resolved_path not in seen_resolved:
                seen_resolved.add(resolved_path)
                resolved.append(resolved_path)
        elif top_level not in seen_external:
            seen_external.add(top_level)
            external.append(top_level)

    return resolved, external

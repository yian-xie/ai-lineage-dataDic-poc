"""Static parser for local .NET project-reference declarations."""

from pathlib import Path
import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_kb_accounts(repo_path: str | Path) -> dict:
    """Parse literal local ProjectReference entries without evaluating MSBuild."""
    root = Path(repo_path).resolve()
    projects = sorted(root.rglob("*.csproj"))
    if not projects:
        raise FileNotFoundError(f"No .csproj files found under {root}")

    project_paths = {path.resolve() for path in projects}
    nodes = []
    edges = []
    unresolved = []

    for project_path in projects:
        source_path = project_path.relative_to(root).as_posix()
        project_id = f"dotnet:project:kb-accounts/{source_path}"
        try:
            document = ET.parse(project_path)
        except ET.ParseError as error:
            raise ValueError(f"Invalid project XML in {source_path}: {error}") from error

        nodes.append({
            "id": project_id,
            "type": "DOTNET_PROJECT",
            "properties": {
                "name": project_path.stem,
                "source_path": source_path,
                "confidence": "explicit",
                "confidence_reason": "Declared by a captured .NET project file.",
                "runtime_verified": False,
                "evidence": [{"source_path": source_path}],
            },
        })
        unresolved.append({
            "reason": "dotnet_msbuild_evaluation_not_performed",
            "source_path": source_path,
            "detail": "SDK/imported properties, conditional items, generated files and restore are not evaluated.",
        })

        parents = {child: parent for parent in document.iter() for child in parent}
        for reference in document.iter():
            if _local_name(reference.tag) != "ProjectReference":
                continue
            declared_path = reference.attrib.get("Include")
            parent = parents.get(reference)
            conditioned = bool(reference.attrib.get("Condition"))
            while parent is not None:
                conditioned = conditioned or bool(parent.attrib.get("Condition"))
                parent = parents.get(parent)
            if not declared_path or conditioned or "$(" in declared_path or "*" in declared_path:
                unresolved.append({
                    "reason": "dotnet_reference_not_resolved",
                    "source_path": source_path,
                    "declared_path": declared_path,
                    "detail": "The project reference is conditional, non-literal, or has no Include path.",
                })
                continue

            target_path = (project_path.parent / declared_path.replace("\\", "/")).resolve()
            target_relative = target_path.relative_to(root).as_posix() if target_path.is_relative_to(root) else None
            if target_path not in project_paths or target_relative is None:
                unresolved.append({
                    "reason": "dotnet_reference_not_resolved",
                    "source_path": source_path,
                    "declared_path": declared_path,
                    "detail": "The literal project reference does not resolve to a captured local .csproj file.",
                })
                continue

            target_id = f"dotnet:project:kb-accounts/{target_relative}"
            edges.append({
                "source": project_id,
                "target": target_id,
                "type": "REFERENCES_PROJECT",
                "properties": {
                    "source_path": source_path,
                    "confidence": "explicit",
                    "confidence_reason": "A literal unconditional ProjectReference Include resolves to a captured project in this checkout.",
                    "status": "literal_unconditional_declaration",
                    "operation": "Include",
                    "declared_path": declared_path,
                    "evidence": [{"source_path": source_path, "status": "literal_unconditional_declaration"}],
                },
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "unresolved": unresolved,
        "coverage": {
            "scope": "captured .NET project declarations and resolved local project references",
            "runtime_verified": False,
            "msbuild_evaluation_performed": False,
            "cross_repository_rules_applied": False,
        },
    }
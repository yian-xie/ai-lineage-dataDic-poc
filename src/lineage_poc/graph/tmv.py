"""Compose selected TMV repository graphs without inventing cross-repo links."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _merge_properties(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    paths = list(target.get("source_paths", []))
    for path in (target.get("source_path"), incoming.get("source_path")):
        if path and path not in paths:
            paths.append(path)
    for path in incoming.get("source_paths", []):
        if path and path not in paths:
            paths.append(path)
    for key, value in incoming.items():
        if key in {"source_path", "source_paths"}:
            continue
        if key not in target or target[key] in (None, "", [], {}):
            target[key] = deepcopy(value)
    if paths:
        target["source_path"] = paths[0]
        if len(paths) > 1:
            target["source_paths"] = paths


def compose_tmv_graphs(
    landing: dict,
    protect_downstream: dict,
    kb_accounts: dict | None = None,
) -> dict:
    """Union graph components, recording absent bridges instead of connecting by names."""
    components = {
        "kb-cdp-tenant-landing": landing,
        "kb-cdp-tenant-protect-downstream": protect_downstream,
    }
    if kb_accounts is not None:
        components["kb-accounts"] = kb_accounts

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    counts = {}
    for repository, graph in components.items():
        counts[repository] = {"nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))}
        for incoming in graph.get("nodes", []):
            node_id = incoming["id"]
            existing = nodes.get(node_id)
            if existing is None:
                nodes[node_id] = deepcopy(incoming)
            elif existing.get("type") != incoming.get("type"):
                raise ValueError(f"Conflicting node types for {node_id!r}")
            else:
                _merge_properties(existing.setdefault("properties", {}), incoming.get("properties", {}))
        for incoming in graph.get("edges", []):
            key = (incoming["source"], incoming["type"], incoming["target"])
            existing = edges.get(key)
            if existing is None:
                edges[key] = deepcopy(incoming)
            else:
                _merge_properties(existing.setdefault("properties", {}), incoming.get("properties", {}))

    landing_relations = {
        node["id"] for node in landing.get("nodes", [])
        if node.get("type") == "SNOWFLAKE_RELATION"
    }
    protect_relations = {
        node["id"] for node in protect_downstream.get("nodes", [])
        if node.get("type") == "SNOWFLAKE_RELATION"
    }
    shared_relations = sorted(landing_relations & protect_relations)
    gaps = []
    if not shared_relations:
        gaps.append({
            "id": "landing-protect-physical-relation-bridge",
            "from_repository": "kb-cdp-tenant-landing",
            "to_repository": "kb-cdp-tenant-protect-downstream",
            "status": "unresolved",
            "reason": "No identical canonical SNOWFLAKE_RELATION identity occurs in both saved repository graphs.",
            "cross_repository_edge_created": False,
        })
    if kb_accounts is not None:
        gaps.append({
            "id": "kb-accounts-data-bridge",
            "from_repository": "kb-accounts",
            "to_repository": "dbt-data-graphs",
            "status": "not_applicable_to_data_lineage",
            "reason": "kb-accounts contains DOTNET_PROJECT/REFERENCES_PROJECT software dependencies, not dataset or column declarations.",
            "cross_repository_edge_created": False,
        })

    return {
        "nodes": sorted(nodes.values(), key=lambda node: node["id"]),
        "edges": sorted(edges.values(), key=lambda edge: (edge["source"], edge["type"], edge["target"])),
        "components": counts,
        "shared_physical_relation_ids": shared_relations,
        "gap_register": gaps,
    }


def compose_account_domain_graphs(components: dict) -> dict:
    data = {key: value for key, value in components.items() if key != "kb-accounts"}
    selected = list(data.values())
    graph = selected[0]
    for component in selected[1:]:
        graph = compose_tmv_graphs(graph, component)
    if "kb-accounts" in components:
        graph = compose_tmv_graphs(graph, {"nodes": [], "edges": []}, components["kb-accounts"])
    graph["components"] = {}
    for key, value in components.items():
        repository = key.removesuffix(":data")
        count = graph["components"].setdefault(repository, {"nodes": 0, "edges": 0})
        count["nodes"] += len(value["nodes"])
        count["edges"] += len(value["edges"])
    graph["gap_register"] = []
    names = list(data)
    for position, left in enumerate(names):
        for right in names[position + 1:]:
            relations = [{node["id"] for node in data[name]["nodes"] if node["type"] in {"SNOWFLAKE_RELATION", "POSTGRES_RELATION"}} for name in (left, right)]
            if not relations[0] & relations[1]:
                graph["gap_register"].append({"from_repository": left.removesuffix(":data"), "to_repository": right.removesuffix(":data"),
                    "status": "unresolved", "reason": "No shared canonical relation identity in the selected repository snapshots.", "cross_repository_edge_created": False})
    if "kb-accounts" in components:
        graph["gap_register"].append({"from_repository": "kb-accounts", "to_repository": "data-graphs",
            "status": "not_applicable_to_data_lineage", "reason": "Captured project references are software dependencies, not data bindings.", "cross_repository_edge_created": False})
    return graph
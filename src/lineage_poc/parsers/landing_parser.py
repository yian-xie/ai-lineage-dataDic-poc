"""Static parser for Landing dbt declarations, pipeline configuration, and migrations."""

from pathlib import Path
from typing import Any, Iterable

import yaml

from lineage_poc.graph.models import Edge, GraphPayload, Node
from .common import add_edge
from .landing import parse_landing_tenant
from .schemachange import parse_schemachange_file

_ENTITY_TYPES = {
    "CDP_PRODUCT",
    "DBT_SOURCE",
    "DBT_MODEL",
    "SNOWFLAKE_RELATION",
    "SCHEMACHANGE_MIGRATION",
}
_EDGE_TYPES = {
    "CONTAINS",
    "DEPENDS_ON",
    "RESOLVES_TO",
    "MATERIALIZES_AS",
    "MIGRATES",
}


def _relative_path(path: str | Path, root: Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return value.as_posix()


def _record_node(node: Node, root: Path) -> dict[str, Any]:
    properties = dict(node.properties)
    for key in ("source_path", "source_file"):
        if properties.get(key):
            properties[key] = _relative_path(properties[key], root)
    for key in ("source_paths",):
        if properties.get(key):
            properties[key] = [_relative_path(path, root) for path in properties[key]]
    if properties.get("confidence") == "inferred" and not properties.get("reason"):
        properties["reason"] = (
            "The dbt source declaration does not state the physical relation kind; "
            "the parser applies its documented fallback."
        )
    return {"id": node.id, "type": node.label, "properties": properties}


def _record_edge(edge: Edge, root: Path) -> dict[str, Any]:
    properties = dict(edge.properties)
    for key in ("source_path", "source_file"):
        if properties.get(key):
            properties[key] = _relative_path(properties[key], root)
    for key in ("source_paths",):
        if properties.get(key):
            properties[key] = [_relative_path(path, root) for path in properties[key]]
    if properties.get("confidence") == "inferred" and not properties.get("reason"):
        properties["reason"] = (
            "The dbt source declaration identifies a relation but does not state "
            "its physical object kind; the parser applies the existing dbt fallback."
        )
    return {
        "source": edge.source,
        "target": edge.target,
        "type": edge.type,
        "properties": properties,
    }


def _pipeline_metadata(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        return {}
    config = document.get("config") or {}
    snowflake = config.get("snowflake") or {}
    task = snowflake.get("task") or {}
    metadata: dict[str, Any] = {}
    if document.get("template"):
        metadata["template"] = document["template"]
    if snowflake:
        metadata["snowflake"] = {
            key: snowflake[key]
            for key in ("database", "schema")
            if key in snowflake
        }
        if task:
            metadata["snowflake"]["task"] = {
                key: task[key]
                for key in ("name", "schedule")
                if key in task
            }
    dbt = config.get("dbt") or {}
    if dbt.get("projectName"):
        metadata["dbt"] = {"projectName": dbt["projectName"]}
    return metadata


def _merge_node(nodes: dict[str, dict[str, Any]], incoming: dict[str, Any]) -> None:
    node_id = incoming["id"]
    existing = nodes.get(node_id)
    if existing is None:
        nodes[node_id] = incoming
        return
    if existing["type"] != incoming["type"]:
        raise ValueError(f"Conflicting node types for {node_id!r}")
    properties = existing["properties"]
    incoming_properties = incoming["properties"]
    source_paths = list(properties.get("source_paths", []))
    for path in (properties.get("source_path"), incoming_properties.get("source_path")):
        if path and path not in source_paths:
            source_paths.append(path)
    for path in incoming_properties.get("source_paths", []):
        if path and path not in source_paths:
            source_paths.append(path)
    for key, value in incoming_properties.items():
        if key in {"source_path", "source_paths"}:
            continue
        if key == "pipeline_configs":
            configs = properties.setdefault(key, [])
            for config in value:
                if config not in configs:
                    configs.append(config)
        elif key not in properties or properties[key] in (None, "", [], {}):
            properties[key] = value
    if source_paths:
        properties.setdefault("source_path", source_paths[0])
        if len(source_paths) > 1:
            properties["source_paths"] = source_paths


def _parse_pipeline_configs(
    products_root: Path,
    root: Path,
    nodes: dict[str, dict[str, Any]],
    requested: set[str] | None,
) -> None:
    for product_path in sorted(path for path in products_root.iterdir() if path.is_dir()):
        if requested is not None and product_path.name not in requested:
            continue
        for config_path in sorted(product_path.glob("**/pipeline/pipeline.yaml")):
            product_id = f"cdp:product:landing:{product_path.name}"
            metadata = _pipeline_metadata(config_path)
            if not metadata:
                continue
            product_node = nodes.get(product_id)
            if product_node is None:
                product_node = {
                    "id": product_id,
                    "type": "CDP_PRODUCT",
                    "properties": {
                        "name": product_path.name,
                        "source_path": _relative_path(config_path, root),
                        "confidence": "explicit",
                    },
                }
                nodes[product_id] = product_node
            properties = product_node["properties"]
            config_record = {
                "source_path": _relative_path(config_path, root),
                **metadata,
            }
            configs = properties.setdefault("pipeline_configs", [])
            if config_record not in configs:
                configs.append(config_record)
            source_paths = properties.setdefault("source_paths", [])
            if config_record["source_path"] not in source_paths:
                source_paths.append(config_record["source_path"])


def _parse_migrations(
    products_root: Path,
    root: Path,
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    requested: set[str] | None,
) -> None:
    for product_path in sorted(path for path in products_root.iterdir() if path.is_dir()):
        if requested is not None and product_path.name not in requested:
            continue
        product_id = f"cdp:product:landing:{product_path.name}"
        for migration_path in sorted(product_path.glob("**/schemachange/scripts/*.sql")):
            if product_id not in nodes:
                _merge_node(nodes, {
                    "id": product_id,
                    "type": "CDP_PRODUCT",
                    "properties": {
                        "name": product_path.name,
                        "source_path": _relative_path(migration_path, root),
                        "confidence": "explicit",
                    },
                })
            migration_graph = parse_schemachange_file(migration_path)
            id_map = {}
            for node in migration_graph.nodes:
                node_id = node.id
                if node.label == "SCHEMACHANGE_MIGRATION":
                    name = node.id.removeprefix("schemachange:migration:")
                    node_id = f"schemachange:migration:landing:{product_path.name}:{name}"
                id_map[node.id] = node_id
                _merge_node(nodes, _record_node(Node(node_id, node.label, node.properties), root))
            contains = Edge(product_id, id_map[next(
                node.id for node in migration_graph.nodes
                if node.label == "SCHEMACHANGE_MIGRATION"
            )], "CONTAINS", {
                "source_path": migration_path.as_posix(),
                "confidence": "explicit",
            })
            migration_graph.edges.append(contains)
            for edge in migration_graph.edges:
                source = id_map.get(edge.source, edge.source)
                target = id_map.get(edge.target, edge.target)
                record = _record_edge(Edge(source, target, edge.type, edge.properties), root)
                key = (source, edge.type, target)
                edges.setdefault(key, record)


def parse(
    repo_path: str | Path,
    products: Iterable[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse Landing dbt, pipeline, and schemachange declarations without execution."""
    root = Path(repo_path).resolve()
    products_root = root / "products" if (root / "products").is_dir() else root
    if not products_root.is_dir():
        raise FileNotFoundError(f"Landing products directory not found: {products_root}")

    requested = set(products) if products is not None else None
    graph = parse_landing_tenant(root, products=requested)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for node in graph.nodes:
        _merge_node(nodes, _record_node(node, root))
    for edge in graph.edges:
        record = _record_edge(edge, root)
        edges[(edge.source, edge.type, edge.target)] = record

    _parse_pipeline_configs(products_root, root, nodes, requested)
    _parse_migrations(products_root, root, nodes, edges, requested)

    invalid_nodes = sorted({node["type"] for node in nodes.values()} - _ENTITY_TYPES)
    invalid_edges = sorted({edge["type"] for edge in edges.values()} - _EDGE_TYPES)
    if invalid_nodes or invalid_edges:
        raise ValueError(f"Unsupported schema types: nodes={invalid_nodes}, edges={invalid_edges}")

    node_records = sorted(nodes.values(), key=lambda node: node["id"])
    edge_records = sorted(edges.values(), key=lambda edge: (edge["source"], edge["type"], edge["target"]))
    node_ids = {node["id"] for node in node_records}
    dangling = [edge for edge in edge_records if edge["source"] not in node_ids or edge["target"] not in node_ids]
    if dangling:
        raise ValueError(f"Parser produced {len(dangling)} edges with missing endpoints")
    return node_records, edge_records
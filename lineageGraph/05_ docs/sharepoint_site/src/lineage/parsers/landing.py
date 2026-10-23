"""Parser for the CDP tenant-landing dbt repository."""

from pathlib import Path
from typing import Iterable

from ..models import Edge, GraphPayload, Node
from .dbt import parse_dbt_project


def _merge_properties(target: dict, incoming: dict) -> None:
    for key, value in incoming.items():
        if key == "source_paths":
            paths = target.setdefault("source_paths", [])
            for path in value if isinstance(value, list) else [value]:
                if path and path not in paths:
                    paths.append(path)
        elif key not in target or target[key] in (None, "", [], {}):
            target[key] = value


def parse_landing_tenant(
    path: str | Path,
    products: Iterable[str] | None = None,
) -> GraphPayload:
    """Parse dbt projects under a tenant-landing repository or products directory.

    Model and source-declaration IDs are scoped to their product because dbt names
    may repeat between independent projects. Physical relation IDs remain shared
    and canonical by database, schema, and relation name.
    """
    root = Path(path)
    products_root = root / "products" if (root / "products").is_dir() else root
    requested = set(products) if products is not None else None
    graph = GraphPayload(nodes=[], edges=[])
    nodes: dict[str, Node] = {}
    edges: dict[tuple[str, str, str], Edge] = {}

    for product_path in sorted(products_root.iterdir()):
        project_file = product_path / "dbt" / "dbt_project.yml"
        if not project_file.is_file() or (requested is not None and product_path.name not in requested):
            continue

        product_name = product_path.name
        product_id = f"cdp:product:landing:{product_name}"
        nodes[product_id] = Node(product_id, "CDP_PRODUCT", {
            "name": product_name,
            "source_path": project_file.as_posix(),
            "source_file": project_file.as_posix(),
            "source_paths": [project_file.as_posix()],
            "confidence": "explicit",
        })
        local_graph = parse_dbt_project(product_path / "dbt")
        id_map: dict[str, str] = {}

        for node in local_graph.nodes:
            if node.label == "DBT_MODEL":
                identity = node.id.rsplit(":", 1)[-1]
                id_map[node.id] = f"dbt:model:landing:{product_name}:{identity}"
            elif node.label == "DBT_SOURCE":
                identity = node.id.removeprefix("dbt:source:")
                id_map[node.id] = f"dbt:source:landing:{product_name}:{identity}"
            else:
                id_map[node.id] = node.id

        declared_models = []
        for node in local_graph.nodes:
            new_id = id_map[node.id]
            properties = dict(node.properties)
            if node.label in {"DBT_MODEL", "DBT_SOURCE"}:
                properties["project"] = product_name
            converted = Node(new_id, node.label, properties)
            if new_id in nodes:
                if nodes[new_id].label != converted.label:
                    raise ValueError(f"Conflicting landing node types for {new_id!r}")
                _merge_properties(nodes[new_id].properties, converted.properties)
            else:
                nodes[new_id] = converted
            if (
                node.label == "DBT_MODEL"
                and node.properties.get("confidence") != "declared_reference"
            ):
                declared_models.append(new_id)

        for edge in local_graph.edges:
            source = id_map.get(edge.source, edge.source)
            target = id_map.get(edge.target, edge.target)
            key = (source, target, edge.type)
            properties = dict(edge.properties)
            if key in edges:
                _merge_properties(edges[key].properties, properties)
            else:
                edges[key] = Edge(source, target, edge.type, properties)

        for model_id in declared_models:
            key = (product_id, model_id, "CONTAINS")
            edges[key] = Edge(product_id, model_id, "CONTAINS", {
                "source_path": project_file.as_posix(),
                "confidence": "explicit",
            })

    if requested is not None:
        missing = requested - {
            node.properties["name"]
            for node in nodes.values()
            if node.label == "CDP_PRODUCT"
        }
        if missing:
            raise ValueError(f"Landing dbt projects not found: {', '.join(sorted(missing))}")

    graph.nodes = sorted(nodes.values(), key=lambda node: node.id)
    graph.edges = sorted(edges.values(), key=lambda edge: (edge.source, edge.type, edge.target))
    return graph
#!/usr/bin/env python3
"""Extend the account thin slice through selected CDP Enterprise products."""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from lineage.models import Edge, GraphPayload, Node
from lineage.parsers import parse_airflow_dag, parse_dbt_project, parse_schemachange_file


PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
BASE_GRAPH_PATH = PROJECT_ROOT / "output/account_table_lineage.json"
OUTPUT_PATH = PROJECT_ROOT / "output/account_enterprise_lineage.json"
PRODUCTS = (
    "int-account-v1",
    "enterprise-integrated-account-v1",
    "cur-dimaccount-v1",
    "cur-factaccount-v1",
)


def _relative_path(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _relation_key(properties: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    name = str(properties.get("name", "")).strip(' "`')
    parts = [part.strip(' "`') for part in name.split(".") if part.strip(' "`')]
    table = str(properties.get("table_name") or (parts[-1] if parts else "")).upper()
    schema = str(properties.get("schema") or (parts[-2] if len(parts) > 1 else "")).upper()
    if not table:
        return None
    return schema, table


def _qualified_name(schema: str, table: str) -> str:
    return f"{schema}.{table}" if schema else table


class GraphAccumulator:
    def __init__(self, base_graph: Dict[str, Any]) -> None:
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self.gap_register = base_graph.get("gap_register", [])
        self.extension_notes: list[Dict[str, Any]] = []
        for node in base_graph["nodes"]:
            self.add_node_dict(node)
        for edge in base_graph["edges"]:
            self.add_edge_dict(edge)

    def add_node_dict(self, node: Dict[str, Any]) -> None:
        node_id = node["id"]
        if node_id in self.nodes:
            existing = self.nodes[node_id]
            if existing["type"] != node["type"]:
                raise ValueError(f"Conflicting node types for {node_id}: {existing['type']} / {node['type']}")
            properties = existing["properties"]
            for key, value in node.get("properties", {}).items():
                if key == "source_paths":
                    sources = properties.setdefault("source_paths", [])
                    for source in value if isinstance(value, list) else [value]:
                        if source not in sources:
                            sources.append(source)
                elif key not in properties or properties[key] in (None, "", [], {}):
                    properties[key] = value
            return
        self.nodes[node_id] = {
            "id": node_id,
            "type": node["type"],
            "properties": dict(node.get("properties", {})),
        }

    def add_node(self, node: Node) -> None:
        properties = dict(node.properties)
        source = properties.get("source_path")
        if source:
            source = _relative_path(str(source))
            properties["source_path"] = source
            properties.setdefault("source_file", source)
            properties.setdefault("source_paths", [source])
        self.add_node_dict({"id": node.id, "type": node.label, "properties": properties})

    def add_edge_dict(self, edge: Dict[str, Any]) -> None:
        key = (edge["source"], edge["target"], edge["type"])
        properties = dict(edge.get("properties", {}))
        if key in self.edges:
            existing = self.edges[key]["properties"]
            for prop, value in properties.items():
                if prop == "source_paths":
                    sources = existing.setdefault("source_paths", [])
                    for source in value if isinstance(value, list) else [value]:
                        if source not in sources:
                            sources.append(source)
                elif prop not in existing:
                    existing[prop] = value
            return
        self.edges[key] = {
            "source": edge["source"],
            "target": edge["target"],
            "type": edge["type"],
            "properties": properties,
        }

    def add_edge(self, edge: Edge) -> None:
        properties = dict(edge.properties)
        source = properties.get("source_path")
        if source:
            source = _relative_path(str(source))
            properties["source_path"] = source
            properties.setdefault("source_file", source)
            properties.setdefault("source_paths", [source])
        self.add_edge_dict({"source": edge.source, "target": edge.target, "type": edge.type, "properties": properties})

    def payload(self) -> Dict[str, Any]:
        node_ids = set(self.nodes)
        dangling = [
            edge
            for edge in self.edges.values()
            if edge["source"] not in node_ids or edge["target"] not in node_ids
        ]
        if dangling:
            raise ValueError(f"Enterprise extension has {len(dangling)} dangling edges")
        return {
            "nodes": sorted(self.nodes.values(), key=lambda node: node["id"]),
            "edges": sorted(self.edges.values(), key=lambda edge: (edge["source"], edge["type"], edge["target"])),
            "gap_register": self.gap_register,
            "extension_notes": self.extension_notes,
        }


def _project_graphs() -> Dict[str, GraphPayload]:
    return {
        product: parse_dbt_project(WORKSPACE_ROOT / "kb-cdp-tenant-enterprise" / "products" / product / "dbt")
        for product in PRODUCTS
    }


def _namespace_nodes(
    product: str,
    graph: GraphPayload,
) -> Tuple[Dict[str, str], Dict[str, Node]]:
    id_map: Dict[str, str] = {}
    nodes: Dict[str, Node] = {}
    for node in graph.nodes:
        if node.label == "DBT_MODEL":
            name = str(node.properties.get("name") or node.id.rsplit(":", 1)[-1])
            new_id = f"dbt:model:{product}:{name}"
        elif node.label == "DBT_SOURCE":
            source_name = str(node.properties.get("source_name", "source"))
            table_name = str(node.properties.get("name", node.id.rsplit(":", 1)[-1]))
            new_id = f"dbt:source:{product}:{source_name}.{table_name}"
        else:
            new_id = node.id
        id_map[node.id] = new_id
        properties = dict(node.properties)
        if node.label in {"DBT_MODEL", "DBT_SOURCE"}:
            properties["project"] = product
        nodes[new_id] = Node(id=new_id, label=node.label, properties=properties)
    return id_map, nodes


def _build_extension(base_graph: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if base_graph is None:
        base_graph = json.loads(BASE_GRAPH_PATH.read_text(encoding="utf-8"))
    accumulator = GraphAccumulator(base_graph)
    parsed_graphs = _project_graphs()
    source_nodes: Dict[str, Node] = {}
    model_nodes: Dict[str, Node] = {}
    relation_nodes: Dict[str, Node] = {}
    product_for_model: Dict[str, str] = {}
    source_relation_keys: Dict[str, Tuple[str, str]] = {}
    relation_index: Dict[Tuple[str, str], str] = {}
    model_dependencies: list[Tuple[str, str]] = []
    dependency_edges: list[Edge] = []
    materializations: Dict[str, Set[str]] = {}
    passthrough_edges: list[Edge] = []

    for node_id, node in accumulator.nodes.items():
        if node["type"] != "SNOWFLAKE_RELATION":
            continue
        key = _relation_key(node["properties"])
        if key:
            relation_index.setdefault(key, node_id)

    normalized_graphs: Dict[str, Tuple[Dict[str, str], Dict[str, Node], list[Edge]]] = {}
    for product, graph in parsed_graphs.items():
        id_map, namespaced_nodes = _namespace_nodes(product, graph)
        normalized_edges: list[Edge] = []
        for node_id, node in namespaced_nodes.items():
            if node.label == "DBT_SOURCE":
                source_nodes[node_id] = node
                key = _relation_key({"name": node.properties.get("name"), "schema": node.properties.get("schema")})
                if key:
                    source_relation_keys[node_id] = key
            elif node.label == "DBT_MODEL":
                model_nodes[node_id] = node
                product_for_model[node_id] = product
            elif node.label == "SNOWFLAKE_RELATION":
                relation_nodes.setdefault(node_id, node)
                if node.properties.get("creation_mechanism") == "DBT":
                    key = _relation_key(node.properties)
                    if key:
                        relation_index.setdefault(key, node_id)

        for edge in graph.edges:
            source = id_map.get(edge.source, edge.source)
            target = id_map.get(edge.target, edge.target)
            if edge.type == "DEPENDS_ON" and source in model_nodes:
                model_dependencies.append((source, target))
                dependency_edges.append(Edge(source, target, edge.type, dict(edge.properties)))
            elif edge.type == "MATERIALIZES_AS" and source in model_nodes:
                materializations.setdefault(source, set()).add(target)
                normalized_edges.append(Edge(source, target, edge.type, dict(edge.properties)))
            elif edge.type != "RESOLVES_TO":
                normalized_edges.append(Edge(source, target, edge.type, dict(edge.properties)))
        normalized_graphs[product] = (id_map, namespaced_nodes, normalized_edges)

    base_public_ids = {
        node_id
        for node_id, node in accumulator.nodes.items()
        if node["type"] == "SNOWFLAKE_RELATION" and node["properties"].get("layer") == "public"
    }
    selected_relations = set(base_public_ids)
    source_relations: Dict[str, str] = {}

    for source_id, key in source_relation_keys.items():
        relation_id = relation_index.get(key)
        if relation_id is None:
            source_node = source_nodes[source_id]
            schema, table = key
            relation_id = f"snowflake:relation:{_qualified_name(schema, table)}"
            source_path = source_node.properties.get("source_path", "")
            relation = Node(
                id=relation_id,
                label="SNOWFLAKE_RELATION",
                properties={
                    "name": _qualified_name(schema, table),
                    "canonical_relation_id": relation_id,
                    "kind": "VIEW" if schema == "PUBLIC" else "TABLE",
                    "layer": "public" if schema == "PUBLIC" else "internal" if schema == "INTERNAL" else "landing",
                    "creation_mechanism": None,
                    "source_path": source_path,
                    "confidence": "declared_source",
                },
            )
            relation_nodes.setdefault(relation_id, relation)
            relation_index[key] = relation_id
        source_relations[source_id] = relation_id

    selected_sources: Set[str] = {
        source_id for source_id, relation_id in source_relations.items() if relation_id in base_public_ids
    }
    selected_models: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for source_id, relation_id in source_relations.items():
            if relation_id in selected_relations and source_id not in selected_sources:
                selected_sources.add(source_id)
                changed = True
        for model_id, dependency_id in model_dependencies:
            if dependency_id in selected_sources or dependency_id in selected_models:
                if model_id not in selected_models:
                    selected_models.add(model_id)
                    changed = True
        for model_id in list(selected_models):
            for relation_id in materializations.get(model_id, set()):
                if relation_id not in selected_relations:
                    selected_relations.add(relation_id)
                    changed = True

    # Retain all declared inputs of selected models, including secondary reference data.
    queue = list(selected_models)
    visited: Set[str] = set()
    while queue:
        model_id = queue.pop()
        if model_id in visited:
            continue
        visited.add(model_id)
        for source_model, dependency_id in model_dependencies:
            if source_model != model_id:
                continue
            if dependency_id in model_nodes and dependency_id not in selected_models:
                selected_models.add(dependency_id)
                queue.append(dependency_id)
                selected_relations.update(materializations.get(dependency_id, set()))
            elif dependency_id in source_nodes:
                selected_sources.add(dependency_id)
                relation_id = source_relations.get(dependency_id)
                if relation_id:
                    selected_relations.add(relation_id)

    for product, graph in parsed_graphs.items():
        selected_project_models = {model_id for model_id in selected_models if product_for_model.get(model_id) == product}
        if not selected_project_models:
            continue
        product_path = WORKSPACE_ROOT / "kb-cdp-tenant-enterprise" / "products" / product
        project_file = product_path / "dbt" / "dbt_project.yml"
        product_id = f"cdp:product:{product}"
        accumulator.add_node_dict({
            "id": product_id,
            "type": "CDP_PRODUCT",
            "properties": {
                "name": product,
                "source_path": _relative_path(project_file),
                "source_file": _relative_path(project_file),
                "confidence": "explicit",
            },
        })
        for model_id in selected_project_models:
            accumulator.add_node(model_nodes[model_id])
            accumulator.add_edge(Edge(
                product_id,
                model_id,
                "CONTAINS",
                {"source_path": _relative_path(project_file), "confidence": "explicit"},
            ))

    for source_id in selected_sources:
        source_node = source_nodes[source_id]
        accumulator.add_node(source_node)
        relation_id = source_relations.get(source_id)
        if relation_id:
            if relation_id in relation_nodes:
                accumulator.add_node(relation_nodes[relation_id])
            elif relation_id not in accumulator.nodes:
                raise ValueError(f"No physical relation node available for source {source_id}")
            source_path = source_node.properties.get("source_path", "")
            accumulator.add_edge(Edge(
                source_id,
                relation_id,
                "RESOLVES_TO",
                {"source_path": source_path, "confidence": "explicit"},
            ))

    selected_model_ids = selected_models
    selected_source_ids = selected_sources
    for edge in dependency_edges:
        if edge.source in selected_model_ids and edge.target in (selected_model_ids | selected_source_ids):
            accumulator.add_edge(edge)
    for product, (id_map, namespaced_nodes, normalized_edges) in normalized_graphs.items():
        for edge in normalized_edges:
            if edge.type == "MATERIALIZES_AS":
                if edge.source in selected_model_ids and edge.target in selected_relations:
                    if edge.target in relation_nodes:
                        accumulator.add_node(relation_nodes[edge.target])
                    accumulator.add_edge(edge)

    # Add schemachange evidence only where a selected enterprise relation is named by a migration.
    selected_relation_keys = {
        key: relation_id
        for key, relation_id in relation_index.items()
        if relation_id in selected_relations
    }
    migration_count = 0
    for product in PRODUCTS:
        product_path = WORKSPACE_ROOT / "kb-cdp-tenant-enterprise" / "products" / product
        script_root = product_path / "schemachange" / "scripts"
        if not script_root.is_dir():
            continue
        product_id = f"cdp:product:{product}"
        for migration_path in sorted(script_root.iterdir()):
            if not migration_path.is_file() or migration_path.suffix.lower() != ".sql":
                continue
            migration_graph = parse_schemachange_file(migration_path)
            migration_node = next(node for node in migration_graph.nodes if node.label == "SCHEMACHANGE_MIGRATION")
            relation_nodes_in_migration = {node.id: node for node in migration_graph.nodes if node.label == "SNOWFLAKE_RELATION"}
            for edge in migration_graph.edges:
                target_node = relation_nodes_in_migration.get(edge.target)
                if edge.type != "MIGRATES" or target_node is None:
                    continue
                key = _relation_key(target_node.properties)
                relation_id = selected_relation_keys.get(key) if key else None
                if relation_id is None:
                    continue
                migration_id = f"schemachange:migration:{product}:{migration_path.name}"
                migration_properties = dict(migration_node.properties)
                migration_properties["source_path"] = _relative_path(migration_path)
                migration_properties["source_file"] = _relative_path(migration_path)
                migration = Node(migration_id, "SCHEMACHANGE_MIGRATION", migration_properties)
                accumulator.add_node(migration)
                accumulator.add_edge(Edge(product_id, migration_id, "CONTAINS", {
                    "source_path": _relative_path(product_path / "dbt" / "dbt_project.yml"),
                    "confidence": "explicit",
                }))
                accumulator.add_edge(Edge(migration_id, relation_id, "MIGRATES", dict(edge.properties)))
                migration_count += 1

    airflow_count = 0
    products_without_account_dag: list[str] = []
    for product in PRODUCTS:
        product_models = {model_id for model_id in selected_models if product_for_model.get(model_id) == product}
        if not product_models:
            continue
        product_path = WORKSPACE_ROOT / "kb-cdp-tenant-enterprise" / "products" / product
        dag_root = product_path / "airflow"
        if not dag_root.is_dir():
            products_without_account_dag.append(product)
            continue
        dag_files = sorted(path for path in dag_root.rglob("*run_dbt*.py") if "src" in path.parts and "dags" in path.parts)
        if not dag_files:
            products_without_account_dag.append(product)
        for dag_path in dag_files:
            dag_graph = parse_airflow_dag(dag_path)
            parsed_dag = next((node for node in dag_graph.nodes if node.label == "AIRFLOW_DAG"), None)
            if parsed_dag is None:
                continue
            accumulator.add_node(parsed_dag)
            dag_id = parsed_dag.id
            accumulator.add_edge(Edge(f"cdp:product:{product}", dag_id, "CONTAINS", {
                "source_path": _relative_path(dag_path),
                "confidence": "explicit",
            }))
            for node in dag_graph.nodes:
                if node.label == "AIRFLOW_TASK":
                    accumulator.add_node(node)
            for edge in dag_graph.edges:
                if edge.type == "CONTAINS_TASK":
                    accumulator.add_edge(edge)
            source_text = dag_path.read_text(encoding="utf-8", errors="replace")
            task_name = "run_dbt_bash" if "run_dbt_bash" in source_text else "run_dbt_build" if "run_dbt_build" in source_text else None
            if not task_name:
                continue
            task_id = f"airflow:task:{dag_path.stem}:{task_name}"
            task_node = Node(task_id, "AIRFLOW_TASK", {
                "task_id": task_name,
                "task_kind": "dbt_build",
                "source_path": _relative_path(dag_path),
                "source_file": _relative_path(dag_path),
                "confidence": "explicit",
                "selection_scope": "optional selected model or project build" if "selectedtable" in source_text else "project dbt build",
            })
            accumulator.add_node(task_node)
            accumulator.add_edge(Edge(dag_id, task_id, "CONTAINS_TASK", {
                "source_path": _relative_path(dag_path),
                "confidence": "explicit",
            }))
            for model_id in product_models:
                accumulator.add_edge(Edge(task_id, model_id, "EXECUTES_DBT", {
                    "source_path": _relative_path(dag_path),
                    "confidence": "explicit",
                    "selection_scope": task_node.properties["selection_scope"],
                }))
            airflow_count += 1

    accumulator.extension_notes = [
        {
            "type": "interim_enterprise_extension",
            "products_scanned": list(PRODUCTS),
            "selection_rule": "Enterprise models are included when their dbt source resolves to an account-slice public relation or when they are transitively dependent on an included model. Their other declared model/source dependencies are retained as context.",
            "source_resolution": "DBT_SOURCE declarations are matched to physical relations by normalized schema and table name; database Jinja templates are preserved in source metadata but are not used as the identity key.",
            "enterprise_airflow_dags_added": airflow_count,
            "products_without_scanned_dbt_dag": products_without_account_dag,
            "enterprise_migration_edges_added": migration_count,
            "caveat": "Static repository configuration only; no enterprise DAG runtime state or live Snowflake catalog was queried.",
        }
    ]
    return accumulator.payload()


def main() -> None:
    payload = _build_extension()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    node_counts: Dict[str, int] = {}
    edge_counts: Dict[str, int] = {}
    for node in payload["nodes"]:
        node_counts[node["type"]] = node_counts.get(node["type"], 0) + 1
    for edge in payload["edges"]:
        edge_counts[edge["type"]] = edge_counts.get(edge["type"], 0) + 1
    print(f"Generated {OUTPUT_PATH.relative_to(PROJECT_ROOT)}: {len(payload['nodes'])} nodes, {len(payload['edges'])} edges")
    print("Enterprise nodes by type:", json.dumps(dict(sorted(node_counts.items())), sort_keys=True))
    print("Enterprise edges by type:", json.dumps(dict(sorted(edge_counts.items())), sort_keys=True))


if __name__ == "__main__":
    main()
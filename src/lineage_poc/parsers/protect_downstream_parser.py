"""Static parser for Protect-downstream product metadata and data flows."""

import ast
import re
from pathlib import Path
from typing import Any

from lineage_poc.graph.models import Edge, GraphPayload, Node
from .airflow import parse_airflow_dag
from .common import add_edge, add_node
from .dbt import parse_dbt_project
from .schemachange import parse_schemachange_file

_ENTITY_TYPES = {
    "CDP_PRODUCT",
    "DBT_SOURCE",
    "DBT_MODEL",
    "SNOWFLAKE_RELATION",
    "AIRFLOW_DAG",
    "AIRFLOW_TASK",
    "SCHEMACHANGE_MIGRATION",
    "S3_PATH",
}
_EDGE_TYPES = {
    "CONTAINS",
    "CONTAINS_TASK",
    "PRECEDES",
    "COPIES_FROM",
    "COPIES_TO",
    "LOADS_FROM",
    "LOADS_TO",
    "EXECUTES_DBT",
    "DEPENDS_ON",
    "RESOLVES_TO",
    "MATERIALIZES_AS",
    "MIGRATES",
}


def _relative_path(value: str, root: Path) -> str:
    path = Path(value)
    try:
        return path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _namespace_id(node: Node, product_name: str) -> str:
    if node.label == "CDP_PRODUCT":
        return f"cdp:product:protect:{product_name}"
    if node.label == "DBT_MODEL":
        return f"dbt:model:protect:{product_name}:{node.id.rsplit(':', 1)[-1]}"
    if node.label == "DBT_SOURCE":
        identity = node.id.removeprefix("dbt:source:")
        return f"dbt:source:protect:{product_name}:{identity}"
    if node.label == "AIRFLOW_DAG":
        return f"airflow:dag:protect:{product_name}:{node.id.removeprefix('airflow:dag:')}"
    if node.label == "AIRFLOW_TASK":
        return f"airflow:task:protect:{product_name}:{node.id.removeprefix('airflow:task:')}"
    if node.label == "SCHEMACHANGE_MIGRATION":
        identity = node.id.removeprefix("schemachange:migration:")
        return f"schemachange:migration:protect:{product_name}:{identity}"
    return node.id


def _merge_node(nodes: dict[str, dict[str, Any]], node: Node, node_id: str, root: Path) -> None:
    properties = dict(node.properties)
    if properties.get("source_path"):
        properties["source_path"] = _relative_path(properties["source_path"], root)
    if properties.get("source_paths"):
        properties["source_paths"] = [
            _relative_path(path, root) for path in properties["source_paths"]
        ]
    record = nodes.get(node_id)
    if record is None:
        nodes[node_id] = {"id": node_id, "type": node.label, "properties": properties}
        return
    if record["type"] != node.label:
        raise ValueError(f"Conflicting node types for {node_id!r}")

    existing = record["properties"]
    source_paths = list(existing.get("source_paths", []))
    for path in (existing.get("source_path"), properties.get("source_path")):
        if path and path not in source_paths:
            source_paths.append(path)
    for path in properties.get("source_paths", []):
        if path and path not in source_paths:
            source_paths.append(path)
    for key, value in properties.items():
        if key in {"source_path", "source_paths"}:
            continue
        if key not in existing or existing[key] in (None, "", [], {}):
            existing[key] = value
    if source_paths:
        existing.setdefault("source_path", source_paths[0])
        if len(source_paths) > 1:
            existing["source_paths"] = source_paths


def _merge_edge(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    edge: Edge,
    source: str,
    target: str,
    root: Path,
) -> None:
    properties = dict(edge.properties)
    if properties.get("source_path"):
        properties["source_path"] = _relative_path(properties["source_path"], root)
    key = (source, edge.type, target)
    record = edges.get(key)
    if record is None:
        edges[key] = {
            "source": source,
            "target": target,
            "type": edge.type,
            "properties": properties,
        }
        return
    existing = record["properties"]
    prior_path = existing.get("source_path")
    incoming_path = properties.get("source_path")
    source_paths = list(existing.get("source_paths", []))
    for path in (prior_path, incoming_path):
        if path and path not in source_paths:
            source_paths.append(path)
    for key_name, value in properties.items():
        if key_name not in {"source_path", "source_paths"}:
            existing.setdefault(key_name, value)
    if source_paths:
        existing.setdefault("source_path", source_paths[0])
        if len(source_paths) > 1:
            existing["source_paths"] = source_paths


def _remap_graph(
    graph: GraphPayload,
    product_name: str,
    root: Path,
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    *,
    airflow_graph: bool = False,
) -> None:
    id_map = {node.id: _namespace_id(node, product_name) for node in graph.nodes}
    for node in graph.nodes:
        if airflow_graph and node.label == "DBT_MODEL":
            continue
        _merge_node(nodes, node, id_map[node.id], root)
    for edge in graph.edges:
        if airflow_graph and edge.type == "EXECUTES_DBT":
            continue
        source = id_map.get(edge.source, edge.source)
        target = id_map.get(edge.target, edge.target)
        _merge_edge(edges, edge, source, target, root)


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def _template(value: ast.expr, bindings: dict[str, ast.expr]) -> str:
    if isinstance(value, ast.Name) and value.id in bindings:
        return _template(bindings[value.id], bindings)
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.JoinedStr):
        parts = []
        for item in value.values:
            if isinstance(item, ast.Constant):
                parts.append(str(item.value))
            else:
                parts.append("{" + ast.unparse(item.value) + "}")
        return "".join(parts)
    return ast.unparse(value)


def _task_decorator_id(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        value = _keyword(decorator, "task_id")
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def _task_id_for_expression(
    expression: ast.expr,
    function_ids: dict[str, str],
    variable_ids: dict[str, str],
) -> str | None:
    if isinstance(expression, ast.Name):
        return variable_ids.get(expression.id) or function_ids.get(expression.id)
    if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name):
        return function_ids.get(expression.func.id)
    return None


def _shift_chain(expression: ast.expr) -> list[ast.expr]:
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.RShift):
        return _shift_chain(expression.left) + _shift_chain(expression.right)
    return [expression]


def _add_airflow_evidence(
    dag_path: Path,
    product_name: str,
    root: Path,
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    tree = ast.parse(dag_path.read_text(encoding="utf-8"), filename=str(dag_path))
    function_ids: dict[str, str] = {}
    variable_ids: dict[str, str] = {}

    for item in ast.walk(tree):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            task_id = _task_decorator_id(item)
            if task_id:
                function_ids[item.name] = task_id
                task_node_id = f"airflow:task:protect:{product_name}:{dag_path.stem}:{task_id}"
                for decorator in item.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue
                    kind = ast.unparse(decorator.func).rsplit(".", 1)[-1]
                    if kind in {"bash", "virtualenv", "python"}:
                        nodes[task_node_id]["properties"].setdefault("task_kind", kind)
                        break
        elif isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
            task_id_value = _keyword(item.value, "task_id")
            if isinstance(task_id_value, ast.Constant) and isinstance(task_id_value.value, str):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        variable_ids[target.id] = task_id_value.value

    for item in ast.walk(tree):
        if not isinstance(item, ast.BinOp) or not isinstance(item.op, ast.RShift):
            continue
        task_ids = [
            _task_id_for_expression(term, function_ids, variable_ids)
            for term in _shift_chain(item)
        ]
        task_ids = [task_id for task_id in task_ids if task_id]
        for before, after in zip(task_ids, task_ids[1:]):
            source = f"airflow:task:protect:{product_name}:{dag_path.stem}:{before}"
            target = f"airflow:task:protect:{product_name}:{dag_path.stem}:{after}"
            edge = Edge(source, target, "PRECEDES", {
                "source_path": dag_path.as_posix(),
                "confidence": "explicit",
            })
            _merge_edge(edges, edge, source, target, root)

    dag_id = f"airflow:dag:protect:{product_name}:{dag_path.stem}"
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        task_id = _task_decorator_id(function)
        if not task_id:
            continue
        task_node_id = f"airflow:task:protect:{product_name}:{dag_path.stem}:{task_id}"
        bindings = {
            target.id: assignment.value
            for assignment in ast.walk(function)
            if isinstance(assignment, ast.Assign) and isinstance(assignment.value, ast.expr)
            for target in assignment.targets
            if isinstance(target, ast.Name)
        }
        for call in (item for item in ast.walk(function) if isinstance(item, ast.Call)):
            if not isinstance(call.func, ast.Attribute) or call.func.attr != "put_object":
                continue
            bucket_value = _keyword(call, "Bucket")
            key_value = _keyword(call, "Key")
            if bucket_value is None or key_value is None:
                continue
            bucket = _template(bucket_value, bindings)
            uri_or_prefix = _template(key_value, bindings)
            if "datalake" not in bucket.lower():
                continue
            safe_key = re.sub(r"[^A-Za-z0-9._-]+", "_", uri_or_prefix).strip("_")
            path_id = f"s3:path:DATALAKE:{product_name}:{dag_path.stem}:{safe_key}"
            path_node = Node(path_id, "S3_PATH", {
                "source_path": dag_path.as_posix(),
                "confidence": "explicit",
                "uri_or_prefix": uri_or_prefix,
                "bucket_role": "DATALAKE",
                "bucket_expression": bucket,
            })
            _merge_node(nodes, path_node, path_id, root)
            edge = Edge(task_node_id, path_id, "COPIES_TO", {
                "source_path": dag_path.as_posix(),
                "confidence": "explicit",
            })
            _merge_edge(edges, edge, task_node_id, path_id, root)


def _add_product_node(
    product_path: Path,
    root: Path,
    nodes: dict[str, dict[str, Any]],
) -> str:
    product_name = product_path.name
    evidence_path = product_path / "config.yaml"
    if not evidence_path.is_file():
        evidence_path = product_path
    node = Node(
        f"cdp:product:protect:{product_name}",
        "CDP_PRODUCT",
        {
            "name": product_name,
            "source_path": evidence_path.as_posix(),
            "confidence": "explicit",
        },
    )
    _merge_node(nodes, node, node.id, root)
    return node.id


def parse(repo_path: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse schema-defined Protect entities and edges without executing source files."""
    root = Path(repo_path).resolve()
    products_root = root / "products" if (root / "products").is_dir() else root
    if not products_root.is_dir():
        raise FileNotFoundError(f"Protect-downstream products directory not found: {products_root}")

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for product_path in sorted(path for path in products_root.iterdir() if path.is_dir()):
        product_name = product_path.name
        product_id = _add_product_node(product_path, root, nodes)
        project_file = product_path / "dbt" / "dbt_project.yml"
        if project_file.is_file():
            dbt_graph = parse_dbt_project(project_file.parent)
            _remap_graph(dbt_graph, product_name, root, nodes, edges)
            for node in dbt_graph.nodes:
                if node.label != "DBT_MODEL" or node.properties.get("confidence") == "declared_reference":
                    continue
                model_id = _namespace_id(node, product_name)
                edge = Edge(product_id, model_id, "CONTAINS", {
                    "source_path": project_file.as_posix(),
                    "confidence": "explicit",
                })
                _merge_edge(edges, edge, product_id, model_id, root)

        airflow_root = product_path / "airflow"
        if airflow_root.is_dir():
            dag_paths = sorted(airflow_root.glob("**/src/dags/*.py"))
            for dag_path in dag_paths:
                if dag_path.name == "__init__.py":
                    continue
                airflow_graph = parse_airflow_dag(dag_path)
                _remap_graph(
                    airflow_graph,
                    product_name,
                    root,
                    nodes,
                    edges,
                    airflow_graph=True,
                )
                _add_airflow_evidence(dag_path, product_name, root, nodes, edges)

        for migration_path in sorted(product_path.glob("**/schemachange/scripts/*.sql")):
            migration_graph = parse_schemachange_file(migration_path)
            _remap_graph(migration_graph, product_name, root, nodes, edges)
            migration_node = next(
                node for node in migration_graph.nodes
                if node.label == "SCHEMACHANGE_MIGRATION"
            )
            migration_id = _namespace_id(migration_node, product_name)
            edge = Edge(product_id, migration_id, "CONTAINS", {
                "source_path": migration_path.as_posix(),
                "confidence": "explicit",
            })
            _merge_edge(edges, edge, product_id, migration_id, root)

    for record in edges.values():
        properties = record["properties"]
        if properties.get("confidence") == "inferred" and not properties.get("reason"):
            properties["reason"] = (
                "The source declaration does not establish this relation detail directly; "
                "the parser used its documented fallback classification."
            )

    invalid_nodes = sorted({record["type"] for record in nodes.values()} - _ENTITY_TYPES)
    invalid_edges = sorted({record["type"] for record in edges.values()} - _EDGE_TYPES)
    if invalid_nodes or invalid_edges:
        raise ValueError(f"Unsupported schema types: nodes={invalid_nodes}, edges={invalid_edges}")

    node_records = sorted(nodes.values(), key=lambda record: record["id"])
    edge_records = sorted(edges.values(), key=lambda record: (record["source"], record["type"], record["target"]))
    node_ids = {record["id"] for record in node_records}
    dangling = [record for record in edge_records if record["source"] not in node_ids or record["target"] not in node_ids]
    if dangling:
        raise ValueError(f"Parser produced {len(dangling)} edges with missing endpoints")
    return node_records, edge_records
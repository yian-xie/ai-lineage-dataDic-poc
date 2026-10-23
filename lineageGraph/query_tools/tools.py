"""Named lineage query functions over the generated account graph."""

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = PACKAGE_ROOT / "output" / "account_table_lineage.json"
COLUMN_PATH = PACKAGE_ROOT / "output" / "column_lineage.json"
REVERSED_EDGE_TYPES = {"READS_FROM", "DEPENDS_ON"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _graph() -> Dict[str, Any]:
    graph = _read_json(GRAPH_PATH)
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ValueError(f"Invalid lineage graph payload: {GRAPH_PATH}")
    return graph


def _columns() -> List[Dict[str, Any]]:
    records = _read_json(COLUMN_PATH)
    if not isinstance(records, list):
        raise ValueError(f"Column lineage payload must be a JSON array: {COLUMN_PATH}")
    return records


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _node_map(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in graph["nodes"] if isinstance(node, dict) and isinstance(node.get("id"), str)}


def _semantic_arc(edge: Dict[str, Any]) -> Tuple[str, str]:
    if str(edge.get("type", "")).upper() in REVERSED_EDGE_TYPES:
        return edge["target"], edge["source"]
    return edge["source"], edge["target"]


def _hop(edge: Dict[str, Any], flow_from: str, flow_to: str) -> Dict[str, Any]:
    properties = edge.get("properties") or {}
    return {
        "from": flow_from,
        "to": flow_to,
        "source": edge["source"],
        "target": edge["target"],
        "type": edge.get("type", "UNKNOWN"),
        "traversal": "stored" if (flow_from, flow_to) == (edge["source"], edge["target"]) else "reversed",
        "confidence": properties.get("confidence", "unspecified"),
        "properties": properties,
    }


def _matching_related_columns(extract_node: Dict[str, Any], field_name: str) -> List[Dict[str, Any]]:
    wanted = _normalize(field_name)
    properties = extract_node.get("properties") or {}
    matches = []
    for mapping in properties.get("related_columns", []):
        aliases: Iterable[Any] = [
            mapping.get("hvr_param_column"), mapping.get("business_field"),
            mapping.get("dbt_column"), mapping.get("source_locator"),
            mapping.get("basic_expression"),
        ]
        targets = mapping.get("dbt_targets") or []
        aliases = list(aliases) + [
            value
            for target in targets
            for value in (target.get("column"), target.get("model"), target.get("source_column"))
        ]
        if wanted in {_normalize(alias) for alias in aliases if alias}:
            matches.append(mapping)
    return matches


def _matching_column_records(field_name: str) -> List[Dict[str, Any]]:
    wanted = _normalize(field_name)
    matches = []
    for record in _columns():
        aliases = [record.get("param_column"), record.get("business_field"), record.get("snowflake_column"), record.get("field_id")]
        aliases.extend(target.get("column") for target in record.get("dbt_targets", []))
        if wanted in {_normalize(alias) for alias in aliases if alias}:
            matches.append(record)
    return matches


def _resolve_extract(graph: Dict[str, Any], extract_file: str) -> List[Dict[str, Any]]:
    wanted = _normalize(extract_file)
    return [
        node for node in graph["nodes"]
        if node.get("type") == "EXTRACT_FILE"
        and wanted in {
            _normalize(node.get("id")),
            _normalize((node.get("properties") or {}).get("name")),
            _normalize((node.get("properties") or {}).get("path")),
            _normalize((node.get("properties") or {}).get("source_file")),
        }
    ]


def _paths_to_relations(
    graph: Dict[str, Any],
    start_id: str,
    required_extract_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    nodes = _node_map(graph)
    adjacency: Dict[str, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
    for edge in graph["edges"]:
        flow_from, flow_to = _semantic_arc(edge)
        adjacency[flow_from].append((flow_to, edge))

    queue = deque([(start_id, [start_id], [])])
    visited = {start_id}
    paths = []
    while queue:
        current, node_ids, edges = queue.popleft()
        current_node = nodes[current]
        if current != start_id and current_node.get("type") == "SNOWFLAKE_RELATION":
            paths.append({
                "nodes": [nodes[node_id] for node_id in node_ids],
                "edges": edges,
            })
            continue
        if (current_node.get("properties") or {}).get("is_boundary_node") is True:
            continue
        for neighbor, edge in adjacency[current]:
            if neighbor in visited:
                continue
            next_node = nodes.get(neighbor)
            if next_node is None:
                continue
            if next_node.get("type") == "EXTRACT_FILE" and required_extract_id and neighbor != required_extract_id:
                continue
            visited.add(neighbor)
            flow_from, flow_to = _semantic_arc(edge)
            queue.append((neighbor, node_ids + [neighbor], edges + [_hop(edge, flow_from, flow_to)]))
    return paths


def _result(field_name: str, paths: List[Dict[str, Any]], mappings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    nodes_by_id = {}
    edges_by_key = {}
    for path in paths:
        for node in path["nodes"]:
            nodes_by_id[node["id"]] = node
        for edge in path["edges"]:
            edges_by_key[(edge["source"], edge["type"], edge["target"])] = edge
    edges = list(edges_by_key.values())
    return {
        "field_name": field_name,
        "nodes": list(nodes_by_id.values()),
        "edges": edges,
        "confidence": [edge["confidence"] for edge in edges],
        "paths": paths,
        "field_mappings": mappings or [],
    }


def get_field_lineage(field_name: str) -> Dict[str, Any]:
    """Return graph paths from the matching MV_FILE through to reachable Snowflake relations.

    Column-level DBT targets are returned as field mapping evidence, not fabricated graph
    edges, because the account graph currently has no edges connecting those DBT relations.
    """
    graph = _graph()
    extracts = [node for node in graph["nodes"] if node.get("type") == "EXTRACT_FILE"]
    paths = []
    related_matches = []
    for extract in extracts:
        related_matches.extend((extract, mapping) for mapping in _matching_related_columns(extract, field_name))

    if not related_matches:
        return {**_result(field_name, []), "error": f"No DWACC mapping matched field: {field_name}"}

    node_map = _node_map(graph)
    for extract, mapping in related_matches:
        source_locator = str(mapping.get("source_locator", ""))
        source_name = source_locator.split("@", 1)[0].strip()
        source_nodes = [
            node for node in graph["nodes"]
            if node.get("type") == "MV_FILE"
            and _normalize((node.get("properties") or {}).get("name")) == _normalize(source_name)
        ]
        for source in source_nodes:
            paths.extend(_paths_to_relations(graph, source["id"], extract["id"]))

    mappings = _matching_column_records(field_name)
    result = _result(field_name, paths, mappings)
    result["graph_path_limitations"] = [
        "The graph has no explicit edge from the reachable raw/direct relation to the dbt internal or public target relations."
    ] if mappings and paths else []
    return result


def get_consumers(extract_file: str) -> Dict[str, Any]:
    """Return all reachable SNOWFLAKE_RELATION consumers and their semantic paths."""
    graph = _graph()
    extracts = _resolve_extract(graph, extract_file)
    if not extracts:
        return {**_result(extract_file, []), "consumers": [], "error": f"EXTRACT_FILE not found: {extract_file}"}

    paths = []
    for extract in extracts:
        paths.extend(_paths_to_relations(graph, extract["id"]))
    result = _result(extract_file, paths)
    result["consumers"] = [
        path["nodes"][-1] for path in paths
        if path["nodes"] and path["nodes"][-1].get("type") == "SNOWFLAKE_RELATION"
    ]
    return result


def get_alias_chain(field_name: str) -> Dict[str, Any]:
    """Return source, HVR and DBT field aliases with confidence on each association."""
    graph = _graph()
    extracts = [node for node in graph["nodes"] if node.get("type") == "EXTRACT_FILE"]
    mappings = []
    for extract in extracts:
        mappings.extend(_matching_related_columns(extract, field_name))

    aliases = []
    edges = []
    seen_aliases = set()
    for mapping in mappings:
        confidence = mapping.get("confidence", "unspecified")
        source_alias = mapping.get("basic_expression") or mapping.get("source_locator") or "unspecified"
        hvr_alias = mapping.get("hvr_param_column") or "unspecified"

        def add_alias(name: str, layer: str, model: str = "", table: str = "") -> Dict[str, Any]:
            entry = {
                "name": name,
                "layer": layer,
                "model": model,
                "table": table,
                "confidence": confidence,
                "source_locator": mapping.get("source_locator"),
                "evidence": mapping.get("evidence", ""),
            }
            key = (name, layer, model, table, mapping.get("hvr_param_column"))
            if key not in seen_aliases:
                seen_aliases.add(key)
                aliases.append(entry)
            return entry

        source_entry = add_alias(source_alias, "source")
        hvr_entry = add_alias(hvr_alias, "extract/HVR")
        if _normalize(source_alias) != _normalize(hvr_alias):
            edges.append({
                "from": source_entry["name"], "to": hvr_entry["name"],
                "type": "BASIC_TO_HVR_ALIAS", "confidence": confidence,
                "confidence_scope": "source mapping record", "evidence": mapping.get("evidence", ""),
            })

        internal_aliases: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for target in mapping.get("dbt_targets", []):
            target_name = target.get("column") or "unspecified"
            target_stage = target.get("stage") or "dbt"
            target_entry = add_alias(target_name, target_stage, target.get("model", ""), target.get("table", ""))
            source_model = target.get("source_model")
            source_column = target.get("source_column") or target.get("source_expression") or target.get("projection_expression")
            if source_column and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(source_column).strip()):
                source_column = ""
            source_entry_for_target = internal_aliases.get((source_model, source_column)) if source_model and source_column else None
            previous = source_entry_for_target or hvr_entry
            target_confidence = target.get("confidence", confidence if not source_entry_for_target else "unspecified")
            edges.append({
                "from": previous["name"], "to": target_entry["name"],
                "type": "DBT_COLUMN_PROJECTION", "confidence": target_confidence,
                "confidence_scope": "target projection" if "confidence" in target else "source mapping record" if not source_entry_for_target else "not supplied",
                "source_model": source_model or "",
                "source_column": source_column or "",
                "expression": target.get("source_expression") or target.get("projection_expression") or "",
                "source_path": target.get("source_path", ""),
            })
            if target_stage.casefold() == "internal":
                internal_aliases[(target.get("model", ""), target_name)] = target_entry
    if not mappings:
        return {"field_name": field_name, "nodes": [], "edges": [], "confidence": [], "aliases": [], "error": f"No field aliases matched: {field_name}"}
    return {
        "field_name": field_name,
        "nodes": aliases,
        "edges": edges,
        "confidence": [edge["confidence"] for edge in edges],
        "aliases": aliases,
    }

"""Query generated lineage graphs and column mappings without external dependencies."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = REPOSITORY_ROOT
DEFAULT_GRAPH = REFERENCE_LINEAGE / "account_table_lineage.json"
DEFAULT_COLUMNS = REFERENCE_LINEAGE / "column_lineage.json"
FLOW_REVERSED_TYPES = {"READS_FROM", "DEPENDS_ON"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"Cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error}") from error


def load_graph(path: Path) -> Dict[str, Any]:
    graph = load_json(path)
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ValueError("Graph JSON must contain 'nodes' and 'edges' arrays.")
    node_ids = set()
    for node in graph["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise ValueError("Every graph node must have a string 'id'.")
        if node["id"] in node_ids:
            raise ValueError(f"Duplicate graph node ID: {node['id']}")
        node_ids.add(node["id"])
    for edge in graph["edges"]:
        if not isinstance(edge, dict) or not isinstance(edge.get("source"), str) or not isinstance(edge.get("target"), str):
            raise ValueError("Every graph edge must have string 'source' and 'target' IDs.")
    return graph


def normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def search_graph(graph: Dict[str, Any], query: str, limit: int = 100) -> Dict[str, Any]:
    needle = query.casefold()
    nodes = [node for node in graph["nodes"] if needle in json.dumps(node, ensure_ascii=False).casefold()]
    edges = [edge for edge in graph["edges"] if needle in json.dumps(edge, ensure_ascii=False).casefold()]
    return {
        "query": query,
        "node_matches": nodes[:limit],
        "edge_matches": edges[:limit],
        "node_match_count": len(nodes),
        "edge_match_count": len(edges),
        "truncated": len(nodes) > limit or len(edges) > limit,
    }


def semantic_arc(edge: Dict[str, Any]) -> Tuple[str, str]:
    """Return data-flow source and target, correcting incoming-verb edge types."""
    if str(edge.get("type", "")).upper() in FLOW_REVERSED_TYPES:
        return edge["target"], edge["source"]
    return edge["source"], edge["target"]


def node_details(graph: Dict[str, Any], node_id: str) -> Dict[str, Any]:
    node = next((item for item in graph["nodes"] if item["id"] == node_id), None)
    if node is None:
        return {"node": None, "error": f"Node not found: {node_id}"}
    incident = []
    for edge in graph["edges"]:
        if node_id not in (edge["source"], edge["target"]):
            continue
        flow_source, flow_target = semantic_arc(edge)
        incident.append({
            **edge,
            "semantic_flow": f"{flow_source} -> {flow_target}",
            "stored_direction_matches_flow": (edge["source"], edge["target"]) == (flow_source, flow_target),
        })
    return {"node": node, "incident_edges": incident}


def trace_graph(graph: Dict[str, Any], start_id: str, direction: str, depth: int) -> Dict[str, Any]:
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    known = set(nodes_by_id)
    if start_id not in known:
        return {"start": start_id, "error": f"Node not found: {start_id}", "nodes": [], "hops": []}
    adjacency: Dict[str, List[Tuple[str, Dict[str, Any], str]]] = defaultdict(list)
    for edge in graph["edges"]:
        source, target = semantic_arc(edge)
        if direction in ("downstream", "both"):
            adjacency[source].append((target, edge, "stored" if (source, target) == (edge["source"], edge["target"]) else "reversed"))
        if direction in ("upstream", "both"):
            adjacency[target].append((source, edge, "stored" if (target, source) == (edge["source"], edge["target"]) else "reversed"))
    queue = deque([(start_id, 0)])
    visited = {start_id: 0}
    hops = []
    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        if (nodes_by_id[current].get("properties") or {}).get("is_boundary_node") is True:
            continue
        for neighbor, edge, traversal in adjacency[current]:
            hop = {
                "depth": current_depth + 1,
                "from": current,
                "edge_type": edge.get("type", "UNKNOWN"),
                "to": neighbor,
                "traversal": traversal,
                "confidence": (edge.get("properties") or {}).get("confidence", "unspecified"),
                "edge_properties": edge.get("properties") or {},
            }
            hops.append(hop)
            if neighbor not in visited:
                visited[neighbor] = current_depth + 1
                queue.append((neighbor, current_depth + 1))
    ordered_ids = sorted(visited, key=lambda node_id: (visited[node_id], node_id))
    return {
        "start": start_id,
        "direction": direction,
        "depth_limit": depth,
        "nodes": [nodes_by_id[node_id] for node_id in ordered_ids],
        "hops": hops,
    }


def shortest_path(graph: Dict[str, Any], from_id: str, to_id: str) -> Dict[str, Any]:
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    known = set(nodes_by_id)
    missing = [node_id for node_id in (from_id, to_id) if node_id not in known]
    if missing:
        return {"from": from_id, "to": to_id, "path": None, "error": "Node not found: " + ", ".join(missing)}
    adjacency: Dict[str, List[Tuple[str, Dict[str, Any], str]]] = defaultdict(list)
    for edge in graph["edges"]:
        source, target = semantic_arc(edge)
        traversal = "stored" if (source, target) == (edge["source"], edge["target"]) else "reversed"
        adjacency[source].append((target, edge, traversal))
    queue = deque([from_id])
    previous: Dict[str, Optional[Tuple[str, Dict[str, Any], str]]] = {from_id: None}
    while queue:
        current = queue.popleft()
        if current == to_id:
            break
        if (nodes_by_id[current].get("properties") or {}).get("is_boundary_node") is True:
            continue
        for neighbor, edge, traversal in adjacency[current]:
            if neighbor not in previous:
                previous[neighbor] = (current, edge, traversal)
                queue.append(neighbor)
    if to_id not in previous:
        return {"from": from_id, "to": to_id, "path": None}
    steps = []
    current = to_id
    while current != from_id:
        parent, edge, traversal = previous[current]  # type: ignore[misc]
        steps.append({
            "from": parent,
            "edge_type": edge.get("type", "UNKNOWN"),
            "to": current,
            "traversal": traversal,
            "confidence": (edge.get("properties") or {}).get("confidence", "unspecified"),
            "edge_properties": edge.get("properties") or {},
        })
        current = parent
    steps.reverse()
    return {"from": from_id, "to": to_id, "path": [nodes_by_id[from_id]] + [nodes_by_id[step["to"]] for step in steps], "hops": steps}


def query_columns(path: Path, selector: str, limit: int = 100) -> Dict[str, Any]:
    records = load_json(path)
    if not isinstance(records, list):
        raise ValueError("Column lineage JSON must be an array of mapping records.")
    key = normalized(selector)
    matches = []
    for record in records:
        candidates: Iterable[Any] = [record.get("param_column"), record.get("snowflake_column"), record.get("field_id"), record.get("business_field")]
        if key in {normalized(value) for value in candidates if value}:
            matches.append(record)
    return {"selector": selector, "match_count": len(matches), "matches": matches[:limit], "truncated": len(matches) > limit}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH, help=f"Graph JSON (default: {DEFAULT_GRAPH.relative_to(ROOT)})")
    parser.add_argument("--columns", type=Path, default=DEFAULT_COLUMNS, help=f"Column mapping JSON (default: {DEFAULT_COLUMNS.relative_to(ROOT)})")
    parser.add_argument("--search", metavar="TEXT", help="Search node IDs, types, properties, edge types and evidence.")
    parser.add_argument("--node", metavar="NODE_ID", help="Show a node and all incident edges.")
    parser.add_argument("--trace", metavar="NODE_ID", help="Traverse semantic lineage from a node.")
    parser.add_argument("--path", nargs=2, metavar=("FROM_ID", "TO_ID"), help="Find a shortest downstream semantic path.")
    parser.add_argument("--column", metavar="SELECTOR", help="Look up a column mapping by parameter, target column, business field or field ID.")
    parser.add_argument("--direction", choices=("downstream", "upstream", "both"), default="downstream", help="Direction for --trace (default: downstream).")
    parser.add_argument("--depth", type=int, default=4, help="Maximum number of hops for --trace (default: 4).")
    parser.add_argument("--limit", type=int, default=100, help="Maximum matches per result set for text/column search (default: 100).")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    requested = sum(value is not None for value in (args.search, args.node, args.trace, args.path, args.column))
    if requested != 1:
        parser.error("choose exactly one of --search, --node, --trace, --path, or --column")
    if args.depth < 1:
        parser.error("--depth must be at least 1")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    try:
        if args.column:
            result = query_columns(args.columns, args.column, args.limit)
        else:
            graph = load_graph(args.graph)
            if args.search is not None:
                result = search_graph(graph, args.search, args.limit)
            elif args.node:
                result = node_details(graph, args.node)
            elif args.trace:
                result = trace_graph(graph, args.trace, args.direction, args.depth)
            else:
                result = shortest_path(graph, args.path[0], args.path[1])
    except ValueError as error:
        print(json.dumps({"error": str(error)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

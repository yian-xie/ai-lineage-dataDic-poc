"""Merge two schema-shaped lineage JSON graphs deterministically."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, OUTPUT_ROOT

import argparse
import copy
import json
from pathlib import Path
from typing import Any


ROOT = REPOSITORY_ROOT
DEFAULT_OUTPUT = OUTPUT_ROOT / "lineage" / "merged_lineage.json"
CONFLICT_OUTPUT = OUTPUT_ROOT / "lineage" / "merge_conflicts.json"

CONFIDENCE_RANK = {
    "unspecified": 0,
    "candidate_composite_key": 1,
    "declared_reference": 1,
    "inferred": 2,
    "confirmed_calculated": 3,
    "confirmed": 3,
    "explicit": 4,
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validate_graph(graph: Any, label: str) -> dict[str, Any]:
    if not isinstance(graph, dict):
        raise ValueError(f"{label} must be a JSON object")
    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ValueError(f"{label} must contain 'nodes' and 'edges' arrays")
    for index, node in enumerate(graph["nodes"]):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise ValueError(f"{label}.nodes[{index}] must have a non-empty string id")
        if not isinstance(node.get("properties", {}), dict):
            raise ValueError(f"{label}.nodes[{index}].properties must be an object")
    for index, edge in enumerate(graph["edges"]):
        if not isinstance(edge, dict):
            raise ValueError(f"{label}.edges[{index}] must be an object")
        source = edge.get("source", edge.get("source_key"))
        target = edge.get("target", edge.get("target_key"))
        edge_type = edge.get("type", edge.get("edge_type"))
        if not all(isinstance(value, str) and value for value in (source, target, edge_type)):
            raise ValueError(
                f"{label}.edges[{index}] must define source/source_key, "
                "target/target_key, and type/edge_type as non-empty strings"
            )
        if not isinstance(edge.get("properties", {}), dict):
            raise ValueError(f"{label}.edges[{index}].properties must be an object")
    return graph


def _normalize_edge(edge: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(edge)
    normalized["source"] = edge.get("source", edge.get("source_key"))
    normalized["target"] = edge.get("target", edge.get("target_key"))
    normalized["type"] = edge.get("type", edge.get("edge_type"))
    normalized.pop("source_key", None)
    normalized.pop("target_key", None)
    normalized.pop("edge_type", None)
    normalized.setdefault("properties", {})
    return normalized


def _edge_key(edge: dict[str, Any]) -> tuple[str, str, str]:
    return edge["source"], edge["target"], edge["type"]


def _confidence(edge: dict[str, Any]) -> str:
    properties = edge.get("properties", {})
    value = properties.get("confidence", edge.get("confidence", "unspecified"))
    return str(value).casefold()


def _record_conflict(
    conflicts: list[dict[str, Any]],
    *,
    conflict_type: str,
    key: Any,
    left: dict[str, Any],
    right: dict[str, Any],
    winner: dict[str, Any],
    winner_input: str,
    resolution: str,
) -> None:
    conflicts.append({
        "kind": conflict_type,
        "key": key,
        "winner_input": winner_input,
        "resolution": resolution,
        "winner": copy.deepcopy(winner),
        "left": copy.deepcopy(left),
        "right": copy.deepcopy(right),
    })


def merge_graph_documents(
    left_graph: dict[str, Any],
    right_graph: dict[str, Any],
    left_label: str = "left",
    right_label: str = "right",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Merge nodes by id, edges by endpoint/type identity, and log every conflict."""
    _validate_graph(left_graph, left_label)
    _validate_graph(right_graph, right_label)
    conflicts: list[dict[str, Any]] = []
    nodes: dict[str, dict[str, Any]] = {}
    node_origins: dict[str, str] = {}

    for graph, origin in ((left_graph, left_label), (right_graph, right_label)):
        for source_node in graph["nodes"]:
            candidate = copy.deepcopy(source_node)
            candidate.setdefault("properties", {})
            key = candidate["id"]
            current = nodes.get(key)
            if current is None:
                nodes[key] = candidate
                node_origins[key] = origin
                continue
            if current == candidate:
                continue

            current_count = len(current["properties"])
            candidate_count = len(candidate["properties"])
            if candidate_count > current_count:
                winner, winner_origin = candidate, origin
                resolution = "more_properties"
            else:
                winner, winner_origin = current, node_origins[key]
                resolution = "more_properties" if current_count > candidate_count else "equal_count_first_input_wins"
            _record_conflict(
                conflicts,
                conflict_type="node_conflict",
                key=key,
                left=current,
                right=candidate,
                winner=winner,
                winner_input=winner_origin,
                resolution=resolution,
            )
            nodes[key] = winner
            node_origins[key] = winner_origin

    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    edge_origins: dict[tuple[str, str, str], str] = {}
    for graph, origin in ((left_graph, left_label), (right_graph, right_label)):
        for source_edge in graph["edges"]:
            candidate = _normalize_edge(source_edge)
            key = _edge_key(candidate)
            current = edges.get(key)
            if current is None:
                edges[key] = candidate
                edge_origins[key] = origin
                continue
            if current == candidate:
                continue

            current_confidence = _confidence(current)
            candidate_confidence = _confidence(candidate)
            current_rank = CONFIDENCE_RANK.get(current_confidence, 0)
            candidate_rank = CONFIDENCE_RANK.get(candidate_confidence, 0)
            if candidate_rank > current_rank:
                winner, winner_origin = candidate, origin
                resolution = "higher_confidence"
            else:
                winner, winner_origin = current, edge_origins[key]
                resolution = "higher_confidence" if current_rank > candidate_rank else "equal_or_unranked_confidence_first_input_wins"
            _record_conflict(
                conflicts,
                conflict_type="edge_conflict",
                key={"source_key": key[0], "target_key": key[1], "edge_type": key[2]},
                left=current,
                right=candidate,
                winner=winner,
                winner_input=winner_origin,
                resolution=resolution,
            )
            edges[key] = winner
            edge_origins[key] = winner_origin

    for edge in edges.values():
        if edge["source"] not in nodes or edge["target"] not in nodes:
            raise ValueError(
                f"Merged edge {_edge_key(edge)!r} has a missing endpoint; "
                "include the endpoint node in one of the input graphs"
            )

    merged: dict[str, Any] = {
        "nodes": sorted(nodes.values(), key=lambda node: node["id"]),
        "edges": sorted(edges.values(), key=lambda edge: _edge_key(edge)),
    }
    metadata_keys = (set(left_graph) | set(right_graph)) - {"nodes", "edges"}
    for key in sorted(metadata_keys):
        left_value = left_graph.get(key)
        right_value = right_graph.get(key)
        if key not in left_graph:
            merged[key] = copy.deepcopy(right_value)
        elif key not in right_graph or left_value == right_value:
            merged[key] = copy.deepcopy(left_value)
        elif isinstance(left_value, list) and isinstance(right_value, list):
            combined = []
            seen = set()
            for value in left_value + right_value:
                fingerprint = _stable_json(value)
                if fingerprint not in seen:
                    combined.append(copy.deepcopy(value))
                    seen.add(fingerprint)
            merged[key] = combined
        else:
            merged[key] = copy.deepcopy(left_value)
            conflicts.append({
                "kind": "metadata_conflict",
                "key": key,
                "winner_input": left_label,
                "resolution": "first_input_wins",
                "winner": copy.deepcopy(left_value),
                "left": copy.deepcopy(left_value),
                "right": copy.deepcopy(right_value),
            })

    return merged, conflicts


def merge_files(left_path: Path, right_path: Path, destination: Path, conflicts_path: Path | None = None) -> dict:
    left_path, right_path, destination = Path(left_path), Path(right_path), Path(destination)
    conflicts_path = Path(conflicts_path) if conflicts_path is not None else destination.with_name("merge_conflicts.json")
    if destination.resolve() in {left_path.resolve(), right_path.resolve()} or conflicts_path.resolve() in {left_path.resolve(), right_path.resolve(), destination.resolve()}:
        raise ValueError("Merged graph, conflict log, and input files must have distinct paths.")
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    merged, conflicts = merge_graph_documents(left, right, left_label=left_path.as_posix(), right_label=right_path.as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)
    conflicts_path.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    conflicts_path.write_text(json.dumps({"conflicts": conflicts}, indent=2) + "\n", encoding="utf-8")
    return {"graph": str(destination), "conflicts": str(conflicts_path), "nodes": len(merged["nodes"]), "edges": len(merged["edges"])}


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Merge two lineage graph JSON files.")
    parser.add_argument("left_graph", type=Path, help="First input graph JSON")
    parser.add_argument("right_graph", type=Path, help="Second input graph JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Merged graph output (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--conflicts", type=Path, help="Conflict log (default: beside the merged graph).")
    args = parser.parse_args(argv)
    return merge_files(args.left_graph, args.right_graph, args.output, args.conflicts)


if __name__ == "__main__":
    main()
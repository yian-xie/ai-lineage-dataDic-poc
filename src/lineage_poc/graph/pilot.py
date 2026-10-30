"""Compose the full pilot graph from parser fragments and independent slices."""

from copy import deepcopy
from pathlib import Path

from lineage_poc.parsers.full import GraphAccumulator, parse_core_graph
from .account import build_account_graph
from .enterprise import _build_extension


def compose_graphs(*graphs: dict, source_root: Path | None = None) -> dict:
    accumulator = GraphAccumulator(source_root=source_root)
    for graph in graphs:
        for node in graph["nodes"]:
            existing = accumulator.nodes.get(node["id"])
            if existing is None:
                accumulator.nodes[node["id"]] = deepcopy(node)
            elif existing["type"] != node["type"]:
                raise ValueError(f"Conflicting node types for {node['id']!r}")
            else:
                accumulator._merge_properties(existing["properties"], deepcopy(node.get("properties", {})))
        for edge in graph["edges"]:
            key = (edge["source"], edge["target"], edge["type"])
            if key not in accumulator.edges:
                accumulator.edges[key] = deepcopy(edge)
            else:
                accumulator._merge_properties(accumulator.edges[key]["properties"], deepcopy(edge.get("properties", {})))
    result = accumulator.payload()
    for name in ("input_flags", "gap_register", "extension_notes"):
        values = [graph[name] for graph in graphs if name in graph]
        if values:
            result[name] = deepcopy(values[-1] if name != "input_flags" else values[0])
    return result


def build_pilot_graph(
    source_root: Path | None = None,
    full_graph: dict | None = None,
    param_metadata: dict | None = None,
) -> dict:
    """Legacy composite builder; workflow stages supply recorded fragments instead."""
    full = full_graph if full_graph is not None else parse_core_graph(source_root=source_root)
    account = build_account_graph(full_graph=full, param_metadata=param_metadata)
    enterprise = _build_extension(base_graph=account, source_root=source_root)
    return compose_graphs(full, account, enterprise, source_root=source_root)

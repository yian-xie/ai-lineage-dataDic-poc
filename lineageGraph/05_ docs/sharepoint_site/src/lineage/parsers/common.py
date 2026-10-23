"""Shared metadata and graph helpers for lineage parser adapters."""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..models import Edge, GraphPayload, Node


def source_path(path: str | Path) -> str:
    return Path(path).as_posix()


def add_node(
    graph: GraphPayload,
    node_id: str,
    label: str,
    path: str | Path,
    confidence: str = "explicit",
    **properties: Any,
) -> None:
    node_properties: Dict[str, Any] = {
        "source_path": source_path(path),
        "confidence": confidence,
        **properties,
    }
    for node in graph.nodes:
        if node.id == node_id:
            node.properties.update(node_properties)
            return
    graph.nodes.append(Node(id=node_id, label=label, properties=node_properties))


def add_edge(
    graph: GraphPayload,
    source: str,
    target: str,
    relationship: str,
    path: str | Path,
    confidence: str = "explicit",
    **properties: Any,
) -> None:
    graph.edges.append(
        Edge(
            source=source,
            target=target,
            type=relationship,
            properties={
                "source_path": source_path(path),
                "confidence": confidence,
                **properties,
            },
        )
    )


def merge_graphs(graphs: Iterable[GraphPayload]) -> GraphPayload:
    merged = GraphPayload(nodes=[], edges=[])
    for graph in graphs:
        for node in graph.nodes:
            if not any(existing.id == node.id for existing in merged.nodes):
                merged.nodes.append(node)
        merged.edges.extend(graph.edges)
    return merged


def qualified_relation(name: str, schema: Optional[str] = None, database: Optional[str] = None) -> str:
    parts = [part.strip(' "`') for part in (database, schema, name) if part]
    return ".".join(part.upper() for part in parts)
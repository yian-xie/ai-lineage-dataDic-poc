from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Node:
    id: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphPayload:
    nodes: List[Node]
    edges: List[Edge]

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "nodes": [
                {"id": node.id, "label": node.label, "properties": node.properties}
                for node in self.nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.type,
                    "properties": edge.properties,
                }
                for edge in self.edges
            ],
        }

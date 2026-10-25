import json
import re
from pathlib import Path
from typing import Any, Dict

from lineage_poc.graph.models import GraphPayload


def export_json(graph: GraphPayload, output_path: str | Path) -> None:
    payload = graph.to_dict()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_cypher(graph: GraphPayload, output_path: str | Path) -> None:
    def literal(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        return f"'{escaped}'"

    def property_map(properties: Dict[str, Any]) -> str:
        return "{" + ", ".join(f"{key}: {literal(value)}" for key, value in properties.items()) + "}"

    lines = [
        "CREATE CONSTRAINT lineage_node_id IF NOT EXISTS",
        "FOR (node:LineageNode) REQUIRE node.id IS UNIQUE;",
        "",
    ]
    for node in graph.nodes:
        label = re.sub(r"[^A-Za-z0-9_]", "_", node.label.title().replace("_", " ").replace(" ", ""))
        lines.append(f"MERGE (node:LineageNode:{label} {{id: {literal(node.id)}}})")
        if node.properties:
            lines.append(f"SET node += {property_map(node.properties)}")
        lines.append(";")

    for edge in graph.edges:
        relationship = re.sub(r"[^A-Za-z0-9_]", "_", edge.type.upper())
        lines.append(
            f"MATCH (source:LineageNode {{id: {literal(edge.source)}}}), "
            f"(target:LineageNode {{id: {literal(edge.target)}}})"
        )
        lines.append(f"MERGE (source)-[relationship:{relationship}]->(target)")
        if edge.properties:
            lines.append(f"SET relationship += {property_map(edge.properties)}")
        lines.append(";")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def export_neptune_json(graph: GraphPayload, output_path: str | Path) -> None:
    payload = {
        "nodes": [
            {"~id": node.id, "~label": node.label, **node.properties}
            for node in graph.nodes
        ],
        "edges": [
            {"~from": edge.source, "~to": edge.target, "~label": edge.type, **edge.properties}
            for edge in graph.edges
        ],
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

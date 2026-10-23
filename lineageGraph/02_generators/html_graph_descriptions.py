"""Add display-only descriptions to graph payloads used by HTML viewers."""

from copy import deepcopy
from typing import Any, Dict


NODE_LABELS = {
    "PROGRAM": "BASIC program",
    "MV_FILE": "Ultracs source file",
    "EXTRACT_FILE": "Extract file",
    "HVR_CHANNEL": "HVR channel",
    "HVR_LOCATION": "HVR location",
    "S3_PATH": "S3 path",
    "CDP_PRODUCT": "CDP product",
    "AIRFLOW_DAG": "Airflow DAG",
    "AIRFLOW_TASK": "Airflow task",
    "DBT_SOURCE": "dbt source declaration",
    "DBT_MODEL": "dbt model",
    "SNOWFLAKE_RELATION": "Snowflake relation",
    "SNOWFLAKE_TABLE": "Snowflake table",
    "SCHEMACHANGE_MIGRATION": "schemachange migration",
}

EDGE_LABELS = {
    "READS_FROM": "reads source data from",
    "WRITES_TO": "writes output to",
    "CALLS": "calls",
    "CARRIED_BY": "is carried by",
    "CAPTURES_FROM": "captures from",
    "INTEGRATES_TO": "integrates to",
    "COPIES_TO": "copies data to",
    "COPIES_FROM": "copies data from",
    "LANDS_IN": "lands data in",
    "LOADS_FROM": "loads data from",
    "LOADS_TO": "loads data into",
    "CONTAINS": "contains or owns",
    "CONTAINS_TASK": "contains task",
    "PRECEDES": "runs before",
    "EXECUTES_DBT": "executes dbt model",
    "DEPENDS_ON": "depends on",
    "RESOLVES_TO": "resolves to physical relation",
    "MATERIALIZES_AS": "materializes as",
    "MIGRATES": "creates or alters",
    "HAS_COLUMN": "contains column",
    "CONTAINS_FIELD": "contains field",
    "EXTRACTED_AS": "is extracted as",
    "MAPS_TO": "maps to",
    "FEEDS_MODEL": "feeds model",
    "CONSUMED_BY": "is consumed by",
    "DBT_SOURCE_FOR": "is declared as a dbt source for",
    "CONTAINS_PRODUCT": "contains product",
    "DECLARES_SOURCE": "declares source",
}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _node_name(node: Dict[str, Any]) -> str:
    properties = node.get("properties", {})
    for key in ("name", "table_name", "task_id", "dag_id", "path"):
        value = _text(properties.get(key))
        if value:
            return value
    return str(node.get("id", "Unknown node"))


def _node_description(node: Dict[str, Any]) -> tuple[str, str]:
    properties = node.get("properties", {})
    for key in ("description", "model_description", "documentation", "comment"):
        value = _text(properties.get(key))
        if value:
            return value, "Repository sourced"
    kind = NODE_LABELS.get(str(node.get("type", "")), str(node.get("type", "Graph entity")).replace("_", " ").lower())
    name = _node_name(node)
    details = []
    for key, label in (("layer", "layer"), ("kind", "object kind"), ("materialized", "materialization")):
        value = _text(properties.get(key))
        if value:
            details.append(f"{label}: {value}")
    qualifier = f" ({'; '.join(details)})" if details else ""
    return f"{name} is a {kind} represented in the repository lineage graph{qualifier}.", "Generated"


def _edge_description(edge: Dict[str, Any], nodes: Dict[str, Dict[str, Any]]) -> tuple[str, str]:
    properties = edge.get("properties", {})
    for key in ("description", "evidence"):
        value = _text(properties.get(key))
        if value:
            return value, "Repository evidence"
    source = _node_name(nodes.get(edge.get("source", ""), {"id": edge.get("source", "Unknown source")}))
    target = _node_name(nodes.get(edge.get("target", ""), {"id": edge.get("target", "Unknown target")}))
    relation = str(edge.get("type", "RELATED_TO"))
    verb = EDGE_LABELS.get(relation, relation.replace("_", " ").lower())
    description = f"{source} {verb} {target}."
    if str(properties.get("confidence", "")).lower() == "inferred":
        description += " This relationship is inferred rather than explicitly declared."
    return description, "Generated"


def describe_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Return an HTML-only copy with a description and origin tag on every item."""
    result = deepcopy(graph)
    nodes = {node["id"]: node for node in result.get("nodes", [])}
    for node in result.get("nodes", []):
        properties = node.setdefault("properties", {})
        description, origin = _node_description(node)
        properties["html_description"] = description
        properties["html_description_origin"] = origin
    for edge in result.get("edges", []):
        properties = edge.setdefault("properties", {})
        description, origin = _edge_description(edge, nodes)
        properties["html_description"] = description
        properties["html_description_origin"] = origin
    return result
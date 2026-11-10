"""Build a field-level static lineage graph for the supported DWTDS feed."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..execution import write_json

_DATA_KEY = re.compile(r'\bDATA:(?:"([^"]+)"|([A-Za-z0-9_]+))', re.IGNORECASE)
_POSITION_REASON = (
    "BASIC output fields and HVR .param fields are aligned by one-based position; "
    "the counts match, but BASIC does not declare the .param names."
)


def build_term_deposit_column_graph(records: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    field_ids: set[str] = set()

    def add_node(identifier: str, node_type: str, properties: dict[str, Any]) -> None:
        nodes.append({"id": identifier, "type": node_type, "properties": properties})

    def add_edge(source: str, target: str, edge_type: str, properties: dict[str, Any]) -> None:
        edges.append({"source": source, "target": target, "type": edge_type, "properties": properties})

    for record in records:
        field_id = record["field_id"]
        if field_id in field_ids:
            raise ValueError(f"Duplicate DWTDS field identity: {field_id}")
        field_ids.add(field_id)

        ultracs = record["ultracs"]
        parameter = record["hvr_parameter"]
        source_id = f"{field_id}:ultracs"
        extract_id = f"{field_id}:extract"
        parameter_id = f"{field_id}:hvr"
        basic_path = ultracs["source_path"]
        parameter_path = parameter["source_path"]

        add_node(source_id, "COLUMN", {
            "layer": "source",
            "field_id": field_id,
            "name": record["business_field"],
            "position": record["ultracs_position"],
            "program": record["ultracs_program"],
            "locator": ultracs.get("source_locator"),
            "expression": ultracs.get("basic_expression"),
            "source_line": ultracs.get("basic_source_line"),
            "source_path": basic_path,
            "confidence": "explicit",
        })
        add_node(extract_id, "COLUMN", {
            "layer": "extract",
            "field_id": field_id,
            "name": record["param_column"],
            "position": record["ultracs_position"],
            "extract_file": record["extract_file"],
            "source_path": basic_path,
            "confidence": "explicit",
        })
        add_node(parameter_id, "COLUMN", {
            "layer": "hvr_parameter",
            "field_id": field_id,
            "name": parameter["name"],
            "position": record["ultracs_position"],
            "data_type": parameter.get("type"),
            "source_path": parameter_path,
            "confidence": "explicit",
        })
        add_edge(source_id, extract_id, "EMITS", {
            "confidence": "explicit",
            "expression": ultracs.get("basic_expression"),
            "source_path": basic_path,
        })
        add_edge(extract_id, parameter_id, "POSITIONALLY_ALIGNS_WITH", {
            "confidence": "inferred",
            "reason": _POSITION_REASON,
            "source_path": parameter_path,
            "source_paths": [basic_path, parameter_path],
        })

        targets = record.get("dbt_targets", [])
        if not targets:
            gaps.append({
                "id": f"DWTDS-UNMAPPED-{record['ultracs_position']}",
                "field_id": field_id,
                "position": record["ultracs_position"],
                "parameter": record["param_column"],
                "boundary": "HVR parameter to RAW/dbt column",
                "reason": record.get("notes", "No exact internal dbt target is present in the saved evidence."),
                "source_path": parameter_path,
            })
            continue

        matched_target = False
        for target_index, target in enumerate(targets, start=1):
            expression = target.get("source_expression", "")
            match = _DATA_KEY.search(expression)
            if not match:
                gaps.append({
                    "id": f"DWTDS-SOURCE-KEY-UNRESOLVED-{record['ultracs_position']}-{target_index}",
                    "field_id": field_id,
                    "position": record["ultracs_position"],
                    "boundary": "RAW attribute to dbt column",
                    "reason": "The saved dbt expression does not expose a DATA:<key> source attribute.",
                    "source_path": target["source_path"],
                })
                continue

            raw_key = match.group(1) or match.group(2)
            target_id = f"{field_id}:dbt:{target_index}"
            raw_id = f"{field_id}:raw:{target_index}"
            route = record.get("ingestion_route", {})
            route_paths = record.get("route_evidence", [])
            if raw_key.casefold() == record["param_column"].casefold():
                raw_path = route_paths[0] if route_paths else target["source_path"]
                add_node(raw_id, "COLUMN", {
                    "layer": "landing",
                    "field_id": field_id,
                    "name": raw_key,
                    "relation": route.get("raw_source"),
                    "source_path": raw_path,
                    "confidence": "inferred",
                })
                add_edge(parameter_id, raw_id, "LOADS_AS", {
                    "confidence": "inferred",
                    "reason": (
                        "The HVR parameter name matches the dbt DATA key and repository-static "
                        "ingestion evidence names the RAW source; no runtime load or schema proof is available."
                    ),
                    "source_path": raw_path,
                    "source_paths": [parameter_path, *route_paths, target["source_path"]],
                })
                matched_target = True

            add_node(target_id, "COLUMN", {
                "layer": target.get("stage", "internal"),
                "field_id": field_id,
                "name": target["column"],
                "relation": target["relation"],
                "model": target["model"],
                "data_type": target.get("data_type"),
                "source_path": target["source_path"],
                "source_line": target.get("source_line"),
                "confidence": "explicit",
            })
            if raw_key.casefold() == record["param_column"].casefold():
                add_edge(raw_id, target_id, "PROJECTS_TO", {
                    "confidence": "explicit",
                    "expression": expression,
                    "source_line": target.get("source_line"),
                    "source_path": target["source_path"],
                })
            else:
                gaps.append({
                    "id": f"DWTDS-PARAM-KEY-MISMATCH-{record['ultracs_position']}-{target_index}",
                    "field_id": field_id,
                    "position": record["ultracs_position"],
                    "parameter": record["param_column"],
                    "dbt_source_key": raw_key,
                    "boundary": "HVR parameter to RAW attribute",
                    "reason": "The HVR parameter name and dbt DATA key differ; no crosswalk is asserted.",
                    "source_path": target["source_path"],
                })

        if not matched_target:
            gaps.append({
                "id": f"DWTDS-RAW-BRIDGE-UNRESOLVED-{record['ultracs_position']}",
                "field_id": field_id,
                "position": record["ultracs_position"],
                "boundary": "HVR parameter to RAW attribute",
                "reason": "No exact parameter-name to dbt DATA-key match was established.",
                "source_path": parameter_path,
            })

    node_ids = {node["id"] for node in nodes}
    if len(node_ids) != len(nodes):
        raise ValueError("Term Deposit column graph contains duplicate node identities")
    if any(edge["source"] not in node_ids or edge["target"] not in node_ids for edge in edges):
        raise ValueError("Term Deposit column graph contains a dangling edge")

    return {
        "schema_version": "term-deposit-column-lineage-v1",
        "scope": "DWTDS",
        "evidence_mode": "repository_static",
        "runtime_verified": False,
        "nodes": nodes,
        "edges": edges,
        "gap_register": gaps,
        "summary": {
            "columns": len(records),
            "mapped_columns": sum(bool(record.get("dbt_targets")) for record in records),
            "unmapped_columns": sum(not record.get("dbt_targets") for record in records),
            "nodes": len(nodes),
            "edges": len(edges),
            "gaps": len(gaps),
        },
        "limitations": [
            "BASIC-to-HVR field alignment is inferred from matching one-based positions.",
            "HVR-to-RAW field alignment is inferred from matching parameter and DATA key names plus static route evidence.",
            "No live services, runtime loads, or production schemas were verified.",
            "The separate public model lineage is not connected to this DWTDS field graph.",
        ],
    }


def write_term_deposit_column_graph(records_path: Path, destination: Path) -> dict[str, Any]:
    records = json.loads(records_path.read_text(encoding="utf-8"))
    graph = build_term_deposit_column_graph(records)
    write_json(destination / "term_deposit_column_lineage_graph.json", graph)
    return graph["summary"]
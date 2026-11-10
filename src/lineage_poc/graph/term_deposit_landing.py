"""Join DWTDS evidence to the parsed ultracs-v1 Landing graph."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import yaml

from lineage_poc.execution import accepted_data, execute_step, inventory, write_json
from lineage_poc.parsers import parse_landing_repo
from lineage_poc.paths import OUTPUT_ROOT, PROJECT_ROOT
from lineage_poc.viewers.graph.term_deposit import build_term_deposit_viewer_config
from lineage_poc.viewers.graph.columns import render_html

_SPLIT_PART = re.compile(
    r"SPLIT_PART\s*\(\s*PAYLOAD\s*,\s*['\"]\|['\"]\s*,\s*(\d+)\s*\)",
    re.IGNORECASE,
)
_ALIAS = re.compile(r"\bAS\s+([A-Z_][A-Z0-9_]*)", re.IGNORECASE)
_LANDING_MODELS = {"termdeposits_raw", "termdeposits_delta", "termdeposits_history", "termdeposits"}


def _payload(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {"nodes": nodes, "edges": edges}


def _repo_path(value: str | None, repository: str) -> str | None:
    if not value:
        return value
    path = Path(value)
    if path.is_absolute():
        return f"{repository}/{path.name}" if not path.exists() else value
    normalized = path.as_posix()
    if normalized.startswith("source-repos/"):
        normalized = normalized.removeprefix("source-repos/")
    if normalized.startswith("products/"):
        normalized = f"{repository}/{normalized}"
    return normalized


def _qualify_landing_paths(graph: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(graph)
    for record in [*result.get("nodes", []), *result.get("edges", [])]:
        properties = record.setdefault("properties", {})
        for key in ("source_path", "source_file"):
            if properties.get(key):
                properties[key] = _repo_path(properties[key], "kb-cdp-tenant-landing")
        if isinstance(properties.get("source_paths"), list):
            properties["source_paths"] = [
                _repo_path(path, "kb-cdp-tenant-landing")
                for path in properties["source_paths"]
            ]
        for config in properties.get("pipeline_configs", []):
            if config.get("source_path"):
                config["source_path"] = _repo_path(config["source_path"], "kb-cdp-tenant-landing")
    return result


def _landing_records(records: list[dict[str, Any]], product_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_sql_path = product_root / "dbt/models/internal/termdeposits_raw/termdeposits_raw.sql"
    raw_yaml_path = product_root / "dbt/models/internal/termdeposits_raw/termdeposits_raw.yml"
    sql_lines = raw_sql_path.read_text(encoding="utf-8").splitlines()
    projections: dict[int, dict[str, Any]] = {}
    for line_number, line in enumerate(sql_lines, start=1):
        position_match = _SPLIT_PART.search(line)
        if not position_match:
            continue
        aliases = _ALIAS.findall(line)
        if not aliases:
            raise ValueError(f"Landing projection at line {line_number} has no output alias")
        position = int(position_match.group(1))
        if position in projections:
            raise ValueError(f"Landing RAW SQL has duplicate payload position {position}")
        projections[position] = {
            "column": aliases[-1].upper(),
            "source_expression": line.strip(),
            "source_line": line_number,
        }

    expected_positions = set(range(1, 42))
    if set(projections) != expected_positions:
        raise ValueError(
            "Landing termdeposits_raw must project payload positions 1-41 exactly; "
            f"found {sorted(projections)}"
        )

    document = yaml.safe_load(raw_yaml_path.read_text(encoding="utf-8")) or {}
    raw_model = next(
        (model for model in document.get("models", []) if model.get("name") == "termdeposits_raw"),
        None,
    )
    if raw_model is None:
        raise ValueError("Landing termdeposits_raw YAML contract was not found")
    metadata = {
        str(column.get("name", "")).upper(): column
        for column in raw_model.get("columns", [])
        if column.get("name")
    }

    mapped_records: list[dict[str, Any]] = []
    field_mappings: list[dict[str, Any]] = []
    for original in sorted(records, key=lambda record: record["ultracs_position"]):
        record = copy.deepcopy(original)
        position = record["ultracs_position"]
        projection = projections.get(position)
        record["dbt_targets"] = []
        record["cdp"] = {}
        record["snowflake_table"] = ""
        record["snowflake_column"] = ""
        record["ingestion_route"] = {
            "hvr_channels": ["ult_sf_tdst"],
            "landing_source": "ultracs_landing.termdeposits_ingest",
            "route_confidence": "inferred",
        }
        if projection is None:
            reason = (
                "Landing termdeposits_raw parses DWTDS payload positions 1-41; "
                "position 42 has no corresponding payload projection."
            )
            record["notes"] = reason
            field_mappings.append({
                "field_id": record["field_id"],
                "position": position,
                "ultracs_field": record["param_column"],
                "landing_column": None,
                "status": "unmapped",
                "confidence": "unconfirmed",
                "reason": reason,
            })
            mapped_records.append(record)
            continue

        landing_column = projection["column"]
        column_metadata = metadata.get(landing_column)
        if column_metadata is None:
            raise ValueError(f"Landing RAW YAML is missing projected column {landing_column!r}")
        target = {
            "stage": "internal",
            "model": "termdeposits_raw",
            "model_id": "dbt:model:landing:ultracs-v1:termdeposits_raw",
            "relation": "snowflake:relation:ULTRACS_INTERNAL.TERMDEPOSITS_RAW",
            "column": landing_column,
            "data_type": column_metadata.get("data_type", "Not declared"),
            "description": column_metadata.get("description", ""),
            "classification": (column_metadata.get("meta") or {}).get("CLASSIFICATION", ""),
            "source_expression": projection["source_expression"],
            "source_line": projection["source_line"],
            "source_path": "kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/termdeposits_raw/termdeposits_raw.sql",
            "schema_path": "kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/termdeposits_raw/termdeposits_raw.yml",
        }
        record["dbt_targets"] = [target]
        record["cdp"] = copy.deepcopy(target)
        record["snowflake_table"] = target["relation"]
        record["snowflake_column"] = landing_column
        record["notes"] = (
            "Landing RAW maps this pipe-payload position to the listed column. "
            "BASIC-to-HVR alignment and the HVR-to-Landing physical identity are inferred; "
            "the HVR export omits the target database/schema."
        )
        field_mappings.append({
            "field_id": record["field_id"],
            "position": position,
            "ultracs_field": record["param_column"],
            "basic_expression": record.get("ultracs", {}).get("basic_expression"),
            "hvr_parameter": record["param_column"],
            "landing_payload_position": position,
            "landing_column": landing_column,
            "target_relation": target["relation"],
            "landing_expression": projection["source_expression"],
            "source_path": target["source_path"],
            "confidence": "inferred",
            "reason": record["notes"],
            "status": "mapped",
        })
        mapped_records.append(record)
    return mapped_records, field_mappings


def _select_ultracs_hvr_graph(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    nodes = {node["id"]: node for node in graph["nodes"]}
    programs = [
        node for node in graph["nodes"]
        if node["type"] == "PROGRAM" and node.get("properties", {}).get("name", "").upper() == "KWDW_TDS"
    ]
    extracts = [
        node for node in graph["nodes"]
        if node["type"] == "EXTRACT_FILE" and node.get("properties", {}).get("name", "").upper() == "DWTDS.TXT"
    ]
    if len(programs) != 1 or len(extracts) != 1:
        raise ValueError("Expected one KWDW_TDS program and one DWTDS.TXT extract in the parsed graph")
    program_id, extract_id = programs[0]["id"], extracts[0]["id"]
    selected_ids = {program_id, extract_id}
    selected_edges = []
    for edge in graph["edges"]:
        if edge["source"] == program_id and edge["type"] in {"READS_FROM", "WRITES_TO"}:
            if edge["type"] == "READS_FROM" or edge["target"] == extract_id:
                selected_ids.update((edge["source"], edge["target"]))
                selected_edges.append(edge)
        elif edge["source"] == extract_id and edge["type"] == "CARRIED_BY":
            selected_ids.update((edge["source"], edge["target"]))
            selected_edges.append(edge)

    channels = {
        edge["target"] for edge in selected_edges
        if edge["source"] == extract_id and edge["type"] == "CARRIED_BY"
    }
    route_edge_types = {"CAPTURES_FROM", "INTEGRATES_TO", "COPIES_TO", "LANDS_IN"}
    for edge in graph["edges"]:
        if edge["source"] in channels and edge["type"] in route_edge_types:
            selected_ids.update((edge["source"], edge["target"]))
            selected_edges.append(edge)

    return {
        "nodes": [copy.deepcopy(nodes[node_id]) for node_id in sorted(selected_ids)],
        "edges": sorted(
            (copy.deepcopy(edge) for edge in selected_edges),
            key=lambda edge: (edge["source"], edge["type"], edge["target"]),
        ),
    }


def build_term_deposit_landing_slice(
    ultracs_hvr_graph: dict[str, Any],
    landing_graph: dict[str, Any],
    records: list[dict[str, Any]],
    landing_product_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    mapped_records, field_mappings = _landing_records(records, landing_product_root)
    base = _select_ultracs_hvr_graph(ultracs_hvr_graph)
    landing_graph = _qualify_landing_paths(landing_graph)
    selected_nodes = {node["id"]: node for node in base["nodes"]}
    selected_edges = {
        (edge["source"], edge["type"], edge["target"]): edge
        for edge in base["edges"]
    }

    landing_nodes = {node["id"]: node for node in landing_graph["nodes"]}
    landing_product = next(
        node for node in landing_graph["nodes"]
        if node["type"] == "CDP_PRODUCT" and node.get("properties", {}).get("name") == "ultracs-v1"
    )
    landing_source = next(
        node for node in landing_graph["nodes"]
        if node["type"] == "DBT_SOURCE"
        and node.get("properties", {}).get("project") == "ultracs-v1"
        and node.get("properties", {}).get("source_name") == "ultracs_landing"
        and node.get("properties", {}).get("name") == "termdeposits_ingest"
    )
    landing_models = {
        node["id"] for node in landing_graph["nodes"]
        if node["type"] == "DBT_MODEL"
        and node.get("properties", {}).get("project") == "ultracs-v1"
        and node.get("properties", {}).get("name", "").casefold() in _LANDING_MODELS
    }
    if len(landing_models) != len(_LANDING_MODELS):
        raise ValueError("The ultracs-v1 Landing parser did not return all four term-deposit models")

    source_resolution = [
        edge for edge in landing_graph["edges"]
        if edge["source"] == landing_source["id"] and edge["type"] == "RESOLVES_TO"
    ]
    if len(source_resolution) != 1:
        raise ValueError("Expected one parser-resolved physical relation for Landing termdeposits_ingest")
    landing_source_relation = source_resolution[0]["target"]
    landing_model_relations = {
        edge["target"]
        for edge in landing_graph["edges"]
        if edge["source"] in landing_models and edge["type"] == "MATERIALIZES_AS"
    }
    landing_ids = {landing_product["id"], landing_source["id"], landing_source_relation} | landing_models | landing_model_relations
    for node_id in landing_ids:
        selected_nodes[node_id] = copy.deepcopy(landing_nodes[node_id])
    for edge in landing_graph["edges"]:
        if edge["source"] in landing_ids and edge["target"] in landing_ids:
            selected_edges[(edge["source"], edge["type"], edge["target"])] = copy.deepcopy(edge)

    hvr_landing_edges = [
        edge for edge in selected_edges.values()
        if edge["type"] == "LANDS_IN"
        and edge["target"] in selected_nodes
        and selected_nodes[edge["target"]].get("properties", {}).get("name", "").upper().endswith("TERMDEPOSITS_INGEST")
    ]
    if len(hvr_landing_edges) != 1:
        raise ValueError("Expected one direct HVR LANDs_IN target for termdeposits_ingest")
    hvr_relation_id = hvr_landing_edges[0]["target"]
    hvr_relation_name = str(selected_nodes[hvr_relation_id]["properties"].get("name", "")).split(".")[-1].strip(' `"').upper()
    landing_relation_name = str(selected_nodes[landing_source_relation]["properties"].get("name", "")).split(".")[-1].strip(' `"').upper()
    if hvr_relation_name != landing_relation_name:
        raise ValueError("HVR direct target and Landing source table names do not match")

    candidate_link = {
        "from": hvr_relation_id,
        "to": landing_source_relation,
        "type": "CANDIDATE_PHYSICAL_IDENTITY",
        "confidence": "inferred",
        "reason": (
            "HVR ult_sf_tdst lands a relation named termdeposits_ingest and Landing declares "
            "ultracs_landing.termdeposits_ingest in ULTRACS_RAW. The Landing database is "
            "{{ target.database }} and the HVR export omits database/schema identity, so this is "
            "a candidate cross-repository match, not a confirmed physical relation join."
        ),
        "source_paths": [
            selected_nodes[hvr_relation_id]["properties"].get("source_path"),
            selected_nodes[landing_source_relation]["properties"].get("source_path"),
        ],
    }

    nodes = sorted(selected_nodes.values(), key=lambda node: node["id"])
    edges = sorted(selected_edges.values(), key=lambda edge: (edge["source"], edge["type"], edge["target"]))
    node_ids = {node["id"] for node in nodes}
    if any(edge["source"] not in node_ids or edge["target"] not in node_ids for edge in edges):
        raise ValueError("Term Deposit Landing graph contains dangling parser edges")
    if any("account" in node["id"].casefold() or "enterprise" in node["id"].casefold() for node in nodes):
        raise ValueError("Account or Enterprise nodes must not be included in this Landing-only graph")

    graph = {
        "schema_version": "term-deposit-landing-lineage-v1",
        "scope": "Ultracs DWTDS through HVR to ultracs-v1 Landing",
        "evidence_mode": "repository_static",
        "runtime_verified": False,
        "nodes": nodes,
        "edges": edges,
        "candidate_links": [candidate_link],
        "field_mappings": field_mappings,
        "summary": {
            "ultracs_positions": len(records),
            "landing_columns_mapped": sum(mapping["status"] == "mapped" for mapping in field_mappings),
            "landing_columns_unmapped": sum(mapping["status"] != "mapped" for mapping in field_mappings),
            "nodes": len(nodes),
            "edges": len(edges),
            "candidate_links": 1,
        },
        "limitations": [
            "BASIC output fields and HVR .param names are paired by one-based position.",
            "The HVR and Landing termdeposits_ingest names match, but database/schema identity is unresolved; the bridge remains candidate metadata, not a graph edge.",
            "Landing RAW projections are explicit in SQL; later Landing model dependencies are parser-backed at model level, not expanded into per-column edges.",
            "Position 42 (col40) has no Landing RAW payload projection and remains unmapped.",
            "No Account or Enterprise lineage is included; no runtime services or production catalog were queried.",
        ],
    }
    return graph, mapped_records


def build_term_deposit_landing_view_config(
    graph: dict[str, Any],
    records: list[dict[str, Any]],
    candidate_link: dict[str, Any],
) -> dict[str, Any]:
    config = build_term_deposit_viewer_config(graph, records)
    nodes = {node["id"]: node for node in graph["nodes"]}

    def schema_entry(node_id: str, group: str) -> dict[str, str]:
        node = nodes[node_id]
        properties = node.get("properties", {})
        label = properties.get("name") or properties.get("task_id") or properties.get("uri_or_prefix") or node_id
        return {"id": node_id, "label": str(label), "group": group, "entityType": node["type"]}

    group_definitions = (
        ("source", "Source", "shape-source", {"MV_FILE"}),
        ("extract", "Extract", "shape-extract", {"PROGRAM", "EXTRACT_FILE"}),
        ("staging", "Staging", "shape-staging", {"HVR_CHANNEL", "HVR_LOCATION", "S3_PATH"}),
        ("jobs", "Landing models", "shape-jobs", {"CDP_PRODUCT", "DBT_SOURCE", "DBT_MODEL"}),
        ("target", "Snowflake targets", "shape-target", {"SNOWFLAKE_RELATION"}),
    )
    schema_groups = []
    for key, label, shape, types in group_definitions:
        group_nodes = [
            schema_entry(node["id"], key)
            for node in graph["nodes"]
            if node["type"] in types
        ]
        schema_groups.append({"key": key, "label": label, "shape": shape, "nodes": group_nodes})
    schema_node_ids = {item["id"] for group in schema_groups for item in group["nodes"]}
    reversed_schema_edges = {"READS_FROM", "DEPENDS_ON", "RESOLVES_TO", "CAPTURES_FROM"}
    schema_links = []
    for edge in graph["edges"]:
        if edge["source"] not in schema_node_ids or edge["target"] not in schema_node_ids:
            continue
        source, target = edge["source"], edge["target"]
        if edge["type"] in reversed_schema_edges:
            source, target = target, source
        schema_links.append({"from": source, "to": target})
    landing_nodes = {
        node_id for node_id, node in nodes.items()
        if node.get("properties", {}).get("project") == "ultracs-v1"
        or node_id == "cdp:product:landing:ultracs-v1"
    }
    landing_relation = candidate_link["to"]
    raw_model = next(
        node for node in graph["nodes"]
        if node["type"] == "DBT_MODEL" and node["properties"].get("name") == "termdeposits_raw"
    )
    raw_relation = next(
        edge["target"] for edge in graph["edges"]
        if edge["source"] == raw_model["id"] and edge["type"] == "MATERIALIZES_AS"
    )
    hvr_relation = candidate_link["from"]
    direct_channels = {
        edge["source"] for edge in graph["edges"]
        if edge["type"] == "LANDS_IN" and edge["target"] == hvr_relation
    }
    direct_path_ids = {hvr_relation, *direct_channels}
    for edge in graph["edges"]:
        if edge["source"] in direct_channels and edge["type"] in {"CAPTURES_FROM", "INTEGRATES_TO"}:
            direct_path_ids.add(edge["target"])
    shared_locations = {
        node_id for node_id in direct_path_ids
        if nodes.get(node_id, {}).get("properties", {}).get("name") == "fs_ultracs"
    }
    program_id = next(node["id"] for node in graph["nodes"] if node["type"] == "PROGRAM" and node["properties"].get("name") == "KWDW_TDS")
    extract_id = next(node["id"] for node in graph["nodes"] if node["type"] == "EXTRACT_FILE" and node["properties"].get("name") == "DWTDS.TXT")
    source_ids = {
        edge["target"] for edge in graph["edges"]
        if edge["source"] == program_id and edge["type"] == "READS_FROM"
    }
    config.update({
        "title": "DWTDS to Tenant Landing Column Lineage",
        "subtitle": "Ultracs → DWTDS → HVR → ultracs-v1 Tenant Landing",
        "view_note": "The HVR direct target and Landing source share a base name, but database/schema identity is unresolved. The dashed bridge is a candidate; Account and Enterprise are outside this graph.",
        "targetLabel": "Tenant Landing",
        "positionLabel": "DWTDS position",
        "extract_name": "DWTDS.TXT",
        "extractNodeId": extract_id,
        "columnMappingSourceNodeId": hvr_relation,
        "columnMappingRoute": "direct",
        "candidateLinks": [candidate_link],
        "targetLabel": "Tenant Landing",
        "lineageReference": "term_deposit_landing_lineage.json",
        "reportScopeLabel": "DWTDS to Tenant Landing",
        "schemaFlowGroups": schema_groups,
        "schemaFlowLinks": schema_links,
        "schemaEditKey": "dwdts-tenant-landing-schema-edits-v1",
        "schemaRepositories": [
            {"id": "repo:ultracs", "name": "kb-ultracs-datawarehouse", "x": -360, "path": "kb-ultracs-datawarehouse/KWDW_TDS"},
            {"id": "repo:hvr", "name": "kb-cdp-hvr", "x": 0, "path": "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_tdst.json"},
            {"id": "repo:landing", "name": "kb-cdp-tenant-landing", "x": 360, "path": "kb-cdp-tenant-landing/products/ultracs-v1/dbt"},
        ],
        "schemaGroupTypes": {
            "source": ["MV_FILE"],
            "extract": ["PROGRAM", "EXTRACT_FILE"],
            "staging": ["HVR_CHANNEL", "HVR_LOCATION", "S3_PATH"],
            "jobs": ["CDP_PRODUCT", "DBT_SOURCE", "DBT_MODEL"],
            "target": ["SNOWFLAKE_RELATION"],
        },
        "schemaDirectBranch": {
            "source": {"id": hvr_relation, "label": nodes[hvr_relation]["properties"].get("name", "termdeposits_ingest"), "group": "target", "entityType": "SNOWFLAKE_RELATION"},
            "target": {"id": landing_relation, "label": nodes[landing_relation]["properties"].get("name", "Landing termdeposits_ingest"), "group": "target", "entityType": "SNOWFLAKE_RELATION"},
        },
        "directBranchGap": candidate_link["reason"],
        "mappedPathNodeIds": sorted({program_id, extract_id, *source_ids} | landing_nodes | direct_path_ids),
        "routes": {
            **config["routes"],
            **{node_id: "direct" for node_id in landing_nodes | (direct_path_ids - shared_locations) | {landing_relation, raw_relation}},
        },
    })
    return config


def render_term_deposit_landing_html(
    graph: dict[str, Any],
    records: list[dict[str, Any]],
    candidate_link: dict[str, Any],
) -> str:
    config = build_term_deposit_landing_view_config(graph, records, candidate_link)
    return render_html(
        graph,
        records,
        enterprise_graph={"nodes": [], "edges": []},
        feed="DWTDS",
        feed_configuration=config,
    )


def record_term_deposit_landing_stage() -> dict[str, Any]:
    from lineage_poc.parsers.full import GraphAccumulator, _add_capture_relationships
    from lineage_poc.parsers import parse_basic_file, parse_hvr_config
    from lineage_poc.parsers import parse_landing_repo

    output = Path(OUTPUT_ROOT)
    project = Path(PROJECT_ROOT)
    source_repos = project / "source-repos"
    landing_repo = source_repos / "kb-cdp-tenant-landing"
    landing_product = landing_repo / "products" / "ultracs-v1"
    basic_path = source_repos / "kb-ultracs-datawarehouse" / "KWDW_TDS"
    channel_paths = [
        source_repos / "kb-cdp-hvr" / "hvr-config" / "apps" / "channels" / f"{name}.json"
        for name in ("ult_s3_actd1", "ult_s3_actd2", "ult_sf_tdst")
    ]
    dwdts_inventory = output / "04-column-lineage-term-deposits"
    inputs = [basic_path, *channel_paths, dwdts_inventory, landing_product]

    for path in [basic_path, *channel_paths]:
        if not path.is_file():
            raise FileNotFoundError(f"Required DWTDS parser input is missing: {path}")
    for directory, stage in ((dwdts_inventory, "04-column-lineage-term-deposits"),):
        accepted = accepted_data(directory, stage)
        if any(inventory(Path(item["path"])) != item for item in accepted.get("inputs", [])):
            raise ValueError(f"A recorded prerequisite input changed: {stage}")

    source_records = json.loads((dwdts_inventory / "dwtds_column_lineage.json").read_text(encoding="utf-8"))

    def operation(destination: Path) -> dict[str, Any]:
        accumulator = GraphAccumulator(source_root=source_repos)
        accumulator.add_graph(parse_basic_file(basic_path))
        for channel_path in channel_paths:
            accumulator.add_graph(parse_hvr_config(channel_path))
        hvr_graph = accumulator.payload()
        _add_capture_relationships(hvr_graph)
        landing_nodes, landing_edges = parse_landing_repo(landing_repo, products=("ultracs-v1",))
        landing_graph = {"nodes": landing_nodes, "edges": landing_edges}
        graph, records = build_term_deposit_landing_slice(
            hvr_graph, landing_graph, source_records, landing_product,
        )
        page = render_term_deposit_landing_html(graph, records, graph["candidate_links"][0])
        write_json(destination / "term_deposit_landing_lineage.json", graph)
        (destination / "index.html").write_text(page, encoding="utf-8", newline="\n")
        return {"html": str(destination / "index.html"), **graph["summary"]}

    return execute_step(
        output,
        "term-deposits",
        "13-term-deposit-landing-lineage",
        inputs=inputs,
        parameters={"scope": "DWTDS to ultracs-v1 Landing", "landing_products": ["ultracs-v1"]},
        operation=operation,
    )


if __name__ == "__main__":
    result = record_term_deposit_landing_stage()
    print(json.dumps({"status": result["status"], "stage": result["stage"], "attempt": result["attempt"], "summary": result["summary"]}))
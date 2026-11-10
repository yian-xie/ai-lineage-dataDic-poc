"""Adapt recorded DWTDS snapshots to the shared rich column viewer."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .columns import render_html


def build_term_deposit_viewer_config(graph: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    nodes_by_id = {node["id"]: node for node in nodes}
    program = next((node for node in nodes if node["type"] == "PROGRAM" and node["properties"].get("name") == "KWDW_TDS"), None)
    extract = next((node for node in nodes if node["type"] == "EXTRACT_FILE" and node["properties"].get("name") == "DWTDS.TXT"), None)
    if program is None or extract is None:
        raise ValueError("The saved Term Deposit graph must contain KWDW_TDS and DWTDS.TXT.")

    source_ids = sorted({edge["target"] for edge in edges if edge["source"] == program["id"] and edge["type"] == "READS_FROM"})
    s3_channels = {
        channel
        for record in records
        for channel in record.get("ingestion_route", {}).get("hvr_channels", [])
        if "hvr:channel:" + channel in nodes_by_id
    }
    if not s3_channels:
        s3_channels = {
            node["properties"]["name"]
            for node in nodes
            if node["type"] == "HVR_CHANNEL" and node["properties"].get("name", "").startswith("ult_s3_actd")
        }
    s3_ids = {"hvr:channel:" + channel for channel in s3_channels}
    for edge in edges:
        if edge["source"] in s3_ids and edge["type"] in {"CAPTURES_FROM", "INTEGRATES_TO", "COPIES_TO"}:
            s3_ids.add(edge["target"])

    direct_edges = [edge for edge in edges if edge["type"] == "LANDS_IN"]
    direct_channel_ids = {edge["source"] for edge in direct_edges}
    direct_target_ids = {edge["target"] for edge in direct_edges}
    direct_ids = set(direct_channel_ids | direct_target_ids)
    for edge in edges:
        if edge["source"] in direct_channel_ids and edge["type"] in {"CAPTURES_FROM", "INTEGRATES_TO"}:
            direct_ids.add(edge["target"])
    shared_route_ids = s3_ids & direct_ids

    target_models = {target.get("model") for record in records for target in record.get("dbt_targets", [])}
    target_relations = {target.get("relation") for record in records for target in record.get("dbt_targets", [])}
    mapped_ids = set(source_ids) | {program["id"], extract["id"]} | s3_ids
    mapped_ids.update(node["id"] for node in nodes if node["type"] == "DBT_MODEL" and node["properties"].get("name") in target_models)
    mapped_ids.update(relation for relation in target_relations if relation in nodes_by_id)
    for edge in edges:
        if edge["source"] in mapped_ids and edge["type"] == "DEPENDS_ON":
            mapped_ids.add(edge["target"])
    mapped_sources = {node_id for node_id in mapped_ids if nodes_by_id.get(node_id, {}).get("type") == "DBT_SOURCE"}
    mapped_ids.update(edge["target"] for edge in edges if edge["source"] in mapped_sources and edge["type"] == "RESOLVES_TO")

    routes = {node_id: "shared" for node_id in nodes_by_id}
    routes.update({node_id: "s3" for node_id in s3_ids - shared_route_ids})
    routes.update({node_id: "direct" for node_id in direct_ids - shared_route_ids})
    routes.update({node_id: "s3" for node_id in mapped_ids if node_id not in direct_ids and node_id not in source_ids and node_id not in {program["id"], extract["id"]}})

    def entry(node_id: str) -> dict[str, str]:
        node = nodes_by_id[node_id]
        properties = node.get("properties", {})
        label = properties.get("name") or properties.get("task_id") or properties.get("uri_or_prefix") or node_id
        return {"id": node_id, "label": str(label), "group": "", "entityType": node["type"]}

    read_sources = [entry(node_id) for node_id in source_ids]
    program_entry, extract_entry = entry(program["id"]), entry(extract["id"])
    staging_ids = sorted(
        node["id"] for node in nodes
        if node["type"] in {"HVR_CHANNEL", "HVR_LOCATION", "S3_PATH"}
    )
    jobs_ids = sorted(
        node["id"] for node in nodes
        if node["type"] in {"CDP_PRODUCT", "AIRFLOW_DAG", "AIRFLOW_TASK", "DBT_SOURCE", "DBT_MODEL", "SCHEMACHANGE_MIGRATION"}
    )
    target_ids = sorted(node["id"] for node in nodes if node["type"] == "SNOWFLAKE_RELATION")
    group_specs = [
        {"key": "source", "label": "Source", "shape": "shape-source", "nodes": read_sources},
        {"key": "extract", "label": "Extract", "shape": "shape-extract", "nodes": [program_entry, extract_entry]},
        {"key": "staging", "label": "Staging", "shape": "shape-staging", "nodes": [entry(node_id) for node_id in staging_ids]},
        {"key": "jobs", "label": "Jobs", "shape": "shape-jobs", "nodes": [entry(node_id) for node_id in jobs_ids]},
        {"key": "target", "label": "Target", "shape": "shape-target", "nodes": [entry(node_id) for node_id in target_ids]},
    ]
    for group in group_specs:
        for item in group["nodes"]:
            item["group"] = group["key"]

    visible_ids = {item["id"] for group in group_specs for item in group["nodes"]}
    reverse_types = {"READS_FROM", "DEPENDS_ON", "RESOLVES_TO", "CAPTURES_FROM"}
    links = []
    for edge in edges:
        if edge["source"] not in visible_ids or edge["target"] not in visible_ids:
            continue
        source, target = edge["source"], edge["target"]
        if edge["type"] in reverse_types:
            source, target = edge["target"], edge["source"]
        links.append({"from": source, "to": target})

    direct_target = next((node_id for node_id in direct_target_ids if node_id in nodes_by_id), None)
    direct_branch = None
    if direct_target:
        direct_branch = {
            "source": {**extract_entry, "group": "extract"},
            "target": {**entry(direct_target), "group": "target"},
        }

    return {
        "title": "DWTDS Term Deposit Column Lineage",
        "subtitle": "Ultracs → DWTDS → HVR S3 and direct HVR → Account Snowflake",
        "view_note": "The two HVR routes remain separate. The direct landing relation is not connected to the accounts-v1 RAW/dbt branch by repository evidence.",
        "positionLabel": "DWTDS position",
        "extract_name": "DWTDS.TXT",
        "extractNodeId": extract["id"],
        "entryNodeIds": sorted(set(source_ids) | {program["id"], extract["id"]}),
        "routes": routes,
        "columnMappingRoute": "s3",
        "mappedPathNodeIds": sorted(mapped_ids),
        "lineageReference": "term_deposit_graph.json",
        "reportScopeLabel": "DWTDS graph",
        "schemaEditKey": "dwtds-term-deposit-schema-edits-v1",
        "schemaGroupTypes": {
            "source": ["MV_FILE"],
            "extract": ["PROGRAM", "EXTRACT_FILE"],
            "staging": ["HVR_CHANNEL", "HVR_LOCATION", "S3_PATH"],
            "jobs": ["CDP_PRODUCT", "AIRFLOW_DAG", "AIRFLOW_TASK", "DBT_SOURCE", "DBT_MODEL", "SCHEMACHANGE_MIGRATION"],
            "target": ["SNOWFLAKE_RELATION"],
        },
        "schemaFlowGroups": group_specs,
        "schemaFlowLinks": links,
        "schemaDirectBranch": direct_branch,
        "directBranchGap": "The direct HVR channel lands in TERMDEPOSITS_INGEST. No repository evidence connects that relation to the accounts-v1 RAW/dbt path.",
    }


def render_term_deposit_html(
    graph: dict[str, Any],
    records: list[dict[str, Any]],
    dictionary_document: str,
) -> str:
    normalized_records = []
    for original in records:
        record = copy.deepcopy(original)
        record.setdefault("dbt_targets", [])
        record.setdefault("cdp", {})
        record.setdefault("snowflake_table", record["dbt_targets"][0].get("relation", "") if record["dbt_targets"] else "")
        record.setdefault("snowflake_column", record["dbt_targets"][0].get("column", "") if record["dbt_targets"] else "")
        ultracs = record.setdefault("ultracs", {})
        ultracs.setdefault("transformation", ultracs.get("basic_expression", ""))
        ultracs.setdefault("basic_comment", ultracs.get("description", ""))
        normalized_records.append(record)
    config = build_term_deposit_viewer_config(graph, normalized_records)
    return render_html(
        graph,
        normalized_records,
        enterprise_graph={"nodes": [], "edges": []},
        dictionary_document=dictionary_document,
        feed="DWTDS",
        feed_configuration=config,
    )


def render_saved_term_deposit_html(
    graph_path: Path,
    columns_path: Path,
    adapter_columns_path: Path,
    dictionary_path: Path,
    destination: Path,
) -> dict[str, Any]:
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    records = json.loads(Path(columns_path).read_text(encoding="utf-8"))
    adapted = {record["field_id"]: record for record in json.loads(Path(adapter_columns_path).read_text(encoding="utf-8"))}
    records = [copy.deepcopy(adapted.get(record["field_id"], record)) for record in records]
    records.sort(key=lambda record: record["ultracs_position"])
    dictionary = Path(dictionary_path).read_text(encoding="utf-8")
    html = render_term_deposit_html(graph, records, dictionary)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    index = destination / "index.html"
    index.write_text(html, encoding="utf-8", newline="\n")
    return {"html": str(index), "columns": len(records), "mapped_columns": sum(bool(record["dbt_targets"]) for record in records)}


def record_saved_term_deposit_html_stage() -> dict[str, Any]:
    from lineage_poc.execution import accepted_data, execute_step, inventory
    from lineage_poc.paths import OUTPUT_ROOT

    output = Path(OUTPUT_ROOT)
    columns = output / "04-column-lineage-term-deposits"
    adapter = output / "04b-term-deposit-dictionary-input"
    report = output / "08-html-term-deposits"
    inputs = [columns, adapter, report]
    stages = ("04-column-lineage-term-deposits", "04b-term-deposit-dictionary-input", "08-html-term-deposits")
    for stage, directory in zip(stages, inputs):
        record = accepted_data(directory, stage)
        if any(inventory(Path(item["path"])) != item for item in record.get("inputs", [])):
            raise ValueError(f"A recorded prerequisite input changed: {stage}")
    return execute_step(
        output,
        "term-deposits",
        "12-term-deposit-rich-html",
        inputs=inputs,
        parameters={"scope": "DWTDS", "view": "shared-rich-graph-schema-dictionary"},
        operation=lambda destination: render_saved_term_deposit_html(
            adapter / "term_deposit_graph.json",
            columns / "dwtds_column_lineage.json",
            adapter / "column_lineage.json",
            report / "dictionary.html",
            destination,
        ),
    )


if __name__ == "__main__":
    result = record_saved_term_deposit_html_stage()
    print(json.dumps({"status": result["status"], "stage": result["stage"], "attempt": result["attempt"], "summary": result["summary"]}))
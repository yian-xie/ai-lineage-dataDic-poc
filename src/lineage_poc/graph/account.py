"""Build the ACCOUNT/DWACC thin-slice graph from the full pilot graph."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT, source_root as default_source_root

import json
from copy import deepcopy
from typing import Any, Dict, Iterable, Set


PROJECT_ROOT = REPOSITORY_ROOT
WORKSPACE_ROOT = default_source_root()
FULL_GRAPH_PATH = REFERENCE_LINEAGE / "table_lineage.json"
PARAM_METADATA_PATH = REFERENCE_LINEAGE / "hvr_param_metadata.json"
OUTPUT_PATH = OUTPUT_ROOT / "lineage" / "account_table_lineage.json"

def _related_columns(records: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    related = []
    for record in records:
        ultracs = record.get("ultracs", {})
        cdp = record.get("cdp", {})
        dbt_targets = [
            {
                "stage": target["stage"],
                "model": target["model"],
                "table": target["relation"],
                "column": target["column"],
                "data_type": target.get("data_type", ""),
                "description": target.get("description", ""),
                "source_path": target.get("source_path", ""),
                "source_expression": target.get("source_expression") or target.get("projection_expression", ""),
                "source_model": target.get("source_model", ""),
            }
            for target in record.get("dbt_targets", [])
        ]
        related.append(
            {
                "business_field": record["business_field"],
                "source_locator": ultracs.get("source_locator"),
                "transformation": ultracs.get("transformation"),
                "basic_expression": ultracs.get("basic_expression"),
                "basic_comment": ultracs.get("basic_comment"),
                "hvr_param_column": record["param_column"],
                "hvr_param_position": record["ultracs_position"],
                "dbt_column": record["snowflake_column"],
                "snowflake_table": record["snowflake_table"],
                "dbt_targets": dbt_targets,
                "confidence": record["confidence"],
                "evidence": record["notes"],
                "source_path": record["source_path"],
                "ultracs_source_path": ultracs.get("source_path"),
                "cdp_source_path": cdp.get("source_path"),
                "description": cdp.get("description"),
                "data_type": cdp.get("data_type"),
                "classification": cdp.get("classification"),
            }
        )
    return related


def with_related_columns(graph: Dict[str, Any], records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Compose column presentation onto a graph without rebuilding either input."""
    result = deepcopy(graph)
    related = _related_columns(records)
    for node in result["nodes"]:
        if node["type"] == "EXTRACT_FILE" and node.get("properties", {}).get("name") == "DWACC":
            node.setdefault("properties", {})["related_columns"] = deepcopy(related)
    return result


GAP_REGISTER = [
    {
        "id": "GAP-01",
        "title": "Source traversal direction",
        "status": "confirmed_graph_semantics",
        "details": "A forward traversal from MV_FILE basic:file:ACCOUNT stops immediately because READS_FROM is stored PROGRAM -> MV_FILE. Consumers must reverse this edge to trace data from the source file toward KWDW_ACC.",
        "impact": "A literal outgoing-edge walk does not produce a source-to-consumer lineage path.",
        "evidence": "account_table_lineage.json contains KWDW_ACC --READS_FROM--> ACCOUNT and no outgoing edges from ACCOUNT.",
    },
    {
        "id": "GAP-02",
        "title": "Direct HVR route does not join the accounts-v1 RAW route",
        "status": "unresolved_route_boundary",
        "details": "The direct ult_sf_acc channel lands in LOADACCOUNTS_INGEST. The accounts-v1 Airflow/dbt route loads ACCOUNTS_V1__ACCOUNTS from S3/Datalake. The graph contains no evidenced relationship between these separate branches.",
        "impact": "Do not claim the direct HVR landing table feeds the accounts-v1 RAW table or its public models without configuration or runtime evidence.",
        "evidence": "The direct branch ends at SNOWFLAKE_RELATION LOADACCOUNTS_INGEST; the S3/Airflow branch loads RAW.ACCOUNTS_V1__ACCOUNTS.",
    },
    {
        "id": "GAP-03",
        "title": "dbt physical relation continuity",
        "status": "unresolved_relation_level_lineage",
        "details": "dbt dependencies connect DBT_MODEL nodes and MATERIALIZES_AS connects each model to a physical relation. The graph does not connect an upstream model's physical relation to the downstream model that consumes it.",
        "impact": "A model-level path reaches the public views, but a physical-relation-only traversal cannot continue from internal materializations to those public relations.",
        "evidence": "The public detail and EOD models DEPENDS_ON internal models; their materialized relations are separate nodes with no relation-to-model consumption edge.",
    },
]

CONFIDENCE_RUBRIC = {
    "version": 1,
    "source_skill": ".github/skills/lineage-workflow/references/confidence.md",
    "score_kind": "heuristic_evidence_strength",
    "is_probability": False,
    "levels": [
        {
            "label": "runtime_verified",
            "score": 100,
            "status": "reserved_not_currently_assigned",
            "meaning": "Exact path observed in a successful production-equivalent run and physical objects independently checked against live metadata.",
        },
        {
            "label": "explicit",
            "score": 95,
            "meaning": "Checked-in code, configuration, or metadata directly identifies the relationship or mapping.",
        },
        {
            "label": "confirmed",
            "score": 95,
            "meaning": "Independent repository evidence corroborates the specific mapping or endpoint identity.",
        },
        {
            "label": "confirmed_calculated",
            "score": 90,
            "meaning": "The deterministic calculation and its output mapping are evidenced; the value is derived rather than a direct copy.",
        },
        {
            "label": "declared_source",
            "score": 85,
            "meaning": "Repository metadata declares a source relation and its schema/database context; this is not a live-catalog check.",
        },
        {
            "label": "inferred",
            "score": 60,
            "meaning": "A reproducible indirect association supports a candidate, such as a filename-pattern match.",
        },
        {
            "label": "candidate_composite_key",
            "score": 60,
            "normalized_as": "inferred",
            "meaning": "A proposed composite-key association supported by component evidence but awaiting key-definition confirmation.",
        },
        {
            "label": "unconfirmed",
            "score": 50,
            "meaning": "A specific candidate exists, but source, target, owner, or identity evidence remains missing.",
        },
        {
            "label": "unknown",
            "score": None,
            "meaning": "Evidence does not support a recognized confidence category.",
        },
        {
            "label": "unresolved",
            "score": None,
            "meaning": "A known lineage question remains unresolved; do not assign a numeric score.",
        },
        {
            "label": "missing",
            "score": None,
            "meaning": "The source record has no confidence property; this is not zero percent.",
        },
    ],
    "multi_hop_rule": "Score each hop separately. If one path score is requested, use the lowest numeric hop score; do not average or multiply. Any required unrated hop makes the whole path incomplete or unrated.",
    "limits": [
        "A clean parser/test run validates code behavior, not production execution.",
        "Static repository evidence alone cannot receive the reserved runtime_verified level.",
        "Missing confidence remains not rated and is reported separately.",
    ],
}


def _node_index(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in graph["nodes"]}


def _downstream_models(
    source_id: str,
    nodes: Dict[str, Dict[str, Any]],
    edges: Iterable[Dict[str, Any]],
) -> Set[str]:
    reached = {source_id}
    models: Set[str] = set()
    changed = True
    edge_list = list(edges)
    while changed:
        changed = False
        for edge in edge_list:
            source = edge["source"]
            if (
                edge["type"] == "DEPENDS_ON"
                and edge["target"] in reached
                and nodes.get(source, {}).get("type") == "DBT_MODEL"
                and source not in models
            ):
                models.add(source)
                reached.add(source)
                changed = True
    return models


def _unique_edges(edges: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    unique: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for edge in edges:
        unique[(edge["source"], edge["target"], edge["type"])] = edge
    return sorted(unique.values(), key=lambda edge: (edge["source"], edge["type"], edge["target"]))


def build_account_graph(
    full_graph: Dict[str, Any] | None = None,
    param_metadata: Dict[str, Any] | None = None,
    records: Iterable[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    if full_graph is None:
        full_graph = json.loads(FULL_GRAPH_PATH.read_text(encoding="utf-8"))
    param_flags = []
    if param_metadata is not None:
        param_flags = param_metadata.get("input_flags", [])
    elif PARAM_METADATA_PATH.exists():
        param_metadata = json.loads(PARAM_METADATA_PATH.read_text(encoding="utf-8"))
        param_flags = param_metadata.get("input_flags", [])
    related_columns = _related_columns(records)
    nodes = _node_index(full_graph)
    all_edges = full_graph["edges"]
    selected: Set[str] = set()
    selected_edges: list[Dict[str, Any]] = []

    program_id = next(
        node_id
        for node_id, node in nodes.items()
        if node["type"] == "PROGRAM"
        and node["properties"].get("name", "").upper() == "KWDW_ACC"
    )
    account_source_ids = {
        node_id
        for node_id, node in nodes.items()
        if node["type"] == "MV_FILE"
        and node["properties"].get("name", "").upper() in {"ACCOUNT", "TRAN"}
    }
    extract_id = "extract:DWACC"
    extract_source_path = "kb-ultracs-datawarehouse/KWDW_ACC"
    extract_node = {
        "id": extract_id,
        "type": "EXTRACT_FILE",
        "properties": {
            "name": "DWACC",
            "path": "KBDOSOUTPUT/DWACC{HEAD}",
            "source_path": extract_source_path,
            "source_file": extract_source_path,
            "format": "pipe-delimited",
            "layer": "extract",
            "confidence": "explicit",
            "evidence": "Extract inventory identifies KWDW_ACC writing KBDOSOUTPUT/DWACC{HEAD}; HVR capture pattern matches DWACC files.",
            "related_columns": related_columns,
        },
    }

    selected.add(program_id)
    selected.update(account_source_ids)
    selected.add(extract_id)
    selected_nodes: Dict[str, Dict[str, Any]] = {extract_id: extract_node}

    for edge in all_edges:
        if edge["type"] == "READS_FROM" and edge["source"] == program_id and edge["target"] in account_source_ids:
            selected_edges.append(edge)

    for source_id in account_source_ids:
        if source_id in nodes:
            selected_nodes[source_id] = nodes[source_id]

    selected_nodes[program_id] = nodes[program_id]
    selected_edges.append(
        {
            "source": program_id,
            "target": extract_id,
            "type": "WRITES_TO",
            "properties": {
                "source_path": extract_source_path,
                "source_file": extract_source_path,
                "confidence": "explicit",
                "evidence": "Ultracs extract inventory records KWDW_ACC writing KBDOSOUTPUT/DWACC{HEAD}.",
            },
        }
    )

    hvr_ids = {
        "hvr:channel:ult_sf_acc",
        "hvr:channel:ult_s3_acc1",
        "hvr:channel:ult_s3_acc2",
        "hvr:location:fs_ultracs",
        "hvr:location:fs_hvr_conv",
        "hvr:location:s3_hvrf",
        "hvr:location:sf_lnd_ultra",
        "s3:path:HVR:ultracs:dwacc",
        "snowflake:relation:LOADACCOUNTS_INGEST",
    }
    selected.update(hvr_ids)
    for node_id in hvr_ids:
        if node_id in nodes:
            selected_nodes[node_id] = nodes[node_id]
    hvr_channel_ids = {
        "hvr:channel:ult_sf_acc",
        "hvr:channel:ult_s3_acc1",
        "hvr:channel:ult_s3_acc2",
    }
    for edge in all_edges:
        if edge["source"] in hvr_channel_ids and edge["target"] in hvr_ids:
            selected_edges.append(edge)

    for edge in all_edges:
        if edge["type"] != "CARRIED_BY" or edge["target"] not in hvr_channel_ids:
            continue
        source_node = nodes.get(edge["source"])
        if (source_node or {}).get("properties", {}).get("source_path") != extract_source_path:
            continue
        selected_edges.append({
            **edge,
            "source": extract_id,
            "properties": dict(edge.get("properties", {})),
        })

    product_id = "cdp:product:accounts-v1"
    airflow_dag_id = "airflow:dag:accounts_v1_ingestion_v1"
    copy_task_id = "airflow:task:accounts_v1_ingestion_v1:copy_s3_files_from_hvr_to_datalake_task_for_dwacc"
    load_task_id = "airflow:task:accounts_v1_ingestion_v1:copy_s3_files_to_snowflake_task_for_dwacc"
    dbt_task_id = "airflow:task:accounts_v1_ingestion_v1:run_dbt_bash"
    hvr_path_id = "s3:path:HVR:ultracs:dwacc"
    datalake_path_id = "s3:path:DATALAKE:ultracs:dwacc"
    raw_relation_id = "snowflake:relation:RAW.ACCOUNTS_V1__ACCOUNTS"
    airflow_ids = {
        product_id,
        airflow_dag_id,
        copy_task_id,
        load_task_id,
        dbt_task_id,
        hvr_path_id,
        datalake_path_id,
        raw_relation_id,
    }
    selected.update(airflow_ids)
    for node_id in airflow_ids:
        if node_id in nodes:
            selected_nodes[node_id] = nodes[node_id]
    airflow_edges = {
        "CONTAINS",
        "CONTAINS_TASK",
        "COPIES_FROM",
        "COPIES_TO",
        "PRECEDES",
        "LOADS_FROM",
        "LOADS_TO",
    }
    for edge in all_edges:
        if edge["type"] in airflow_edges and edge["source"] in airflow_ids and edge["target"] in airflow_ids:
            selected_edges.append(edge)

    source_id = "dbt:source:account_raw_source.ACCOUNTS_V1__ACCOUNTS"
    model_ids = _downstream_models(source_id, nodes, all_edges)
    selected.update(model_ids)
    selected.add(source_id)
    for model_id in model_ids:
        model_path = nodes[model_id]["properties"].get("source_path")
        selected_edges.append(
            {
                "source": product_id,
                "target": model_id,
                "type": "CONTAINS",
                "properties": {
                    "source_path": model_path,
                    "source_file": model_path,
                    "confidence": "explicit",
                },
            }
        )

    for edge in all_edges:
        if edge["source"] in model_ids and edge["type"] == "DEPENDS_ON":
            selected.add(edge["target"])
            selected_edges.append(edge)
        elif edge["source"] in model_ids and edge["type"] == "MATERIALIZES_AS":
            selected.add(edge["target"])
            selected_edges.append(edge)
        elif edge["source"] == source_id and edge["type"] == "RESOLVES_TO":
            selected.add(edge["target"])
            selected_edges.append(edge)
        elif edge["source"] == dbt_task_id and edge["type"] == "EXECUTES_DBT" and edge["target"] in model_ids:
            selected_edges.append(edge)

    for node_id in list(selected):
        if node_id in nodes:
            selected_nodes[node_id] = nodes[node_id]

    extract_output = selected_nodes[extract_id]
    extract_properties = dict(extract_output.get("properties", {}))
    extract_properties["related_columns"] = related_columns
    selected_nodes[extract_id] = {**extract_output, "properties": extract_properties}

    selected_relation_ids = {
        node_id
        for node_id in selected
        if nodes.get(node_id, {}).get("type") == "SNOWFLAKE_RELATION"
    }
    for edge in all_edges:
        if edge["type"] == "MIGRATES" and edge["target"] in selected_relation_ids:
            selected_edges.append(edge)
            selected.add(edge["source"])
            selected_nodes[edge["source"]] = nodes[edge["source"]]
            migration_path = nodes[edge["source"]]["properties"].get("source_path")
            selected_edges.append(
                {
                    "source": product_id,
                    "target": edge["source"],
                    "type": "CONTAINS",
                    "properties": {
                        "source_path": migration_path,
                        "source_file": migration_path,
                        "confidence": "explicit",
                    },
                }
            )

    selected_edges = [
        edge
        for edge in _unique_edges(selected_edges)
        if edge["source"] in selected and edge["target"] in selected
    ]
    payload = {
        "nodes": sorted(selected_nodes.values(), key=lambda node: node["id"]),
        "edges": selected_edges,
        "confidence_rubric": CONFIDENCE_RUBRIC,
        "gap_register": GAP_REGISTER,
        "input_flags": sorted(
            {
                (flag["source_path"], flag["line"], flag["flag"]): flag
                for flag in full_graph.get("input_flags", []) + param_flags
            }.values(),
            key=lambda flag: (flag["source_path"], flag["line"], flag["flag"]),
        ),
    }

    node_ids = {node["id"] for node in payload["nodes"]}
    if any(edge["source"] not in node_ids or edge["target"] not in node_ids for edge in payload["edges"]):
        raise ValueError("Account slice contains dangling edges")
    return payload


def main() -> None:
    payload = build_account_graph()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Generated {OUTPUT_PATH.relative_to(PROJECT_ROOT)}: "
        f"{len(payload['nodes'])} nodes, {len(payload['edges'])} edges; "
        f"{sum(len(node['properties'].get('related_columns', [])) for node in payload['nodes'])} related column mappings"
    )


if __name__ == "__main__":
    main()
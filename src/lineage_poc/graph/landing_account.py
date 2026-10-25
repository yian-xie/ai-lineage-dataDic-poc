"""Build an isolated ACCESSNO column trial for landing ultracs-v1."""

from lineage_poc.viewers.graph._templates import read_template
from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT, source_root as default_source_root

import html
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

PROJECT_ROOT = REPOSITORY_ROOT
WORKSPACE_ROOT = default_source_root()

from lineage_poc.parsers import parse_dbt_project, parse_landing_tenant
from lineage_poc.viewers.graph.descriptions import describe_graph


OUTPUT_DIR = OUTPUT_ROOT / "lineage" / "landing_account_no_test"
LANDING_ROOT = WORKSPACE_ROOT / "kb-cdp-tenant-landing"
TABLE_GRAPH_PATH = REFERENCE_LINEAGE / "table_lineage.json"
ACCOUNT_DBT_PATH = WORKSPACE_ROOT / "kb-cdp-tenant-account/products/accounts-v1/dbt"
ENTERPRISE_GRAPH_PATH = REFERENCE_LINEAGE / "account_enterprise_lineage.json"
BASIC_PATH = WORKSPACE_ROOT / "kb-ultracs-datawarehouse/KWDW_FEE"


def relative_path(value: Any, source_root: Path | None = None) -> Any:
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    if not isinstance(value, str):
        return value
    candidate = Path(value)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.resolve().relative_to(workspace_root).as_posix()
    except ValueError:
        return candidate.as_posix()


def normalize_records(records: list[dict[str, Any]], source_root: Path | None = None) -> list[dict[str, Any]]:
    result = deepcopy(records)
    for record in result:
        properties = record.setdefault("properties", {})
        if "source_path" in properties:
            properties["source_path"] = relative_path(properties["source_path"], source_root=source_root)
        if "source_file" in properties:
            properties["source_file"] = relative_path(properties["source_file"], source_root=source_root)
        if isinstance(properties.get("source_paths"), list):
            properties["source_paths"] = [relative_path(path, source_root=source_root) for path in properties["source_paths"]]
    return result


def as_payload(graph: Any) -> dict[str, list[dict[str, Any]]]:
    return {
        "nodes": [
            {"id": node.id, "type": node.label, "properties": dict(node.properties)}
            for node in graph.nodes
        ],
        "edges": [
            {"source": edge.source, "target": edge.target, "type": edge.type, "properties": dict(edge.properties)}
            for edge in graph.edges
        ],
    }


def _node_name(node: dict[str, Any]) -> str:
    properties = node.get("properties", {})
    return str(properties.get("name") or properties.get("table_name") or node.get("id", ""))


def _merge_selected(
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    payload: dict[str, Any],
    selected_ids: set[str],
) -> None:
    for node in payload.get("nodes", []):
        if node["id"] in selected_ids:
            nodes[node["id"]] = node
    for edge in payload.get("edges", []):
        if edge["source"] in selected_ids and edge["target"] in selected_ids:
            key = (edge["source"], edge["type"], edge["target"])
            edges[key] = edge


def build_test_graph(
    source_root: Path | None = None,
    full_graph: dict | None = None,
    enterprise_graph: dict | None = None,
) -> dict[str, Any]:
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    landing_root = workspace_root / "kb-cdp-tenant-landing"
    if not landing_root.is_dir():
        raise FileNotFoundError(f"This optional trial requires kb-cdp-tenant-landing: {landing_root}")
    full = deepcopy(full_graph) if full_graph is not None else json.loads(TABLE_GRAPH_PATH.read_text(encoding="utf-8"))
    full_nodes = {node["id"]: node for node in full["nodes"]}
    program = next(
        node for node in full["nodes"]
        if node["type"] == "PROGRAM" and node.get("properties", {}).get("name", "").upper() == "KWDW_FEE"
    )
    extract = next(
        node for node in full["nodes"]
        if node["type"] == "EXTRACT_FILE"
        and node.get("properties", {}).get("name", "").upper() == "DWFEE605.TXT"
        and "KWDW_FEE" in " ".join(node.get("properties", {}).get("source_paths", []))
    )
    channel = next(
        node for node in full["nodes"]
        if node["type"] == "HVR_CHANNEL" and node.get("properties", {}).get("name") == "ult_sf_fee60"
    )
    hvr_lands_edge = next(
        edge for edge in full["edges"]
        if edge["source"] == channel["id"] and edge["type"] == "LANDS_IN"
        and "FEEEXEMPTION_V1_INGEST" in edge["target"].upper()
    )
    hvr_relation = full_nodes[hvr_lands_edge["target"]]
    source_file = next(
        node for node in full["nodes"]
        if node["type"] == "MV_FILE" and node.get("properties", {}).get("name") == "CLIENT"
    )

    full_payload = {"nodes": full["nodes"], "edges": full["edges"]}
    selected_base_ids = {program["id"], extract["id"], channel["id"], hvr_relation["id"], source_file["id"]}

    landing = as_payload(parse_landing_tenant(landing_root, products=("ultracs-v1",)))
    landing_nodes = {node["id"]: node for node in landing["nodes"]}
    landing_models = {
        node_id for node_id, node in landing_nodes.items()
        if node["type"] == "DBT_MODEL" and node.get("properties", {}).get("project") == "ultracs-v1"
        and node.get("properties", {}).get("name", "").casefold().startswith("feeexemption")
    }
    landing_source = next(
        node for node in landing["nodes"]
        if node["type"] == "DBT_SOURCE"
        and node.get("properties", {}).get("project") == "ultracs-v1"
        and node.get("properties", {}).get("source_name") == "ultracs_landing"
        and node.get("properties", {}).get("name") == "feeexemption_v1_ingest"
    )
    landing_relations = {
        node_id for node_id, node in landing_nodes.items()
        if node["type"] == "SNOWFLAKE_RELATION"
        and "FEEEXEMPTION" in str(node.get("properties", {}).get("name", "")).upper()
    }
    landing_product = next(
        node for node in landing["nodes"]
        if node["type"] == "CDP_PRODUCT" and node.get("properties", {}).get("name") == "ultracs-v1"
    )
    landing_ids = landing_models | landing_relations | {landing_source["id"], landing_product["id"]}

    account = as_payload(parse_dbt_project(workspace_root / "kb-cdp-tenant-account" / "products" / "accounts-v1" / "dbt"))
    account_nodes = {node["id"]: node for node in account["nodes"]}
    account_source = next(
        node for node in account["nodes"]
        if node["type"] == "DBT_SOURCE"
        and node.get("properties", {}).get("source_name") == "ultracs_landing"
        and node.get("properties", {}).get("name") == "feeexemption"
    )
    account_model = account_nodes["dbt:model:feeexemption"]
    account_relations = {
        node_id for node_id, node in account_nodes.items()
        if node["type"] == "SNOWFLAKE_RELATION"
        and "FEEEXEMPTION" in str(node.get("properties", {}).get("name", "")).upper()
    }
    account_ids = {account_source["id"], account_model["id"]} | account_relations

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    _merge_selected(nodes, edges, full_payload, selected_base_ids)
    _merge_selected(nodes, edges, landing, landing_ids)
    _merge_selected(nodes, edges, account, account_ids)

    field_info = {
        "name": "ACCESSNO",
        "business_label": "Account number (fee-exemption view)",
        "source_locator": "CLIENT @ID",
        "basic_output": "DWFEE605.TXT; header column AccessNo",
        "payload_position": 1,
        "landing_type": "NUMBER(38, 0)",
        "classification": "SENSITIVE",
        "landing_raw_sql": "CAST(NULLIF(SPLIT_PART(PAYLOAD, '|', 1), '') AS NUMBER(38, 0)) AS ACCESSNO",
        "landing_public_relation": "ULTRACS_PUBLIC.FEEEXEMPTION",
        "account_public_model": "feeexemption",
        "source_path": "kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_raw/feeexemption_raw.sql",
        "confidence": "explicit",
        "notes": "KWDW_FEE reads CLIENT by ID, writes ID before the delimited record under an AccessNo header, and the landing raw model parses payload part 1 into ACCESSNO. This field is ACCESSNO in the selected feeexemption path; it is not asserted as the DWACC/KiwiAcc mapping.",
    }
    column_nodes = {
        program["id"],
        source_file["id"],
        extract["id"],
        channel["id"],
        hvr_relation["id"],
        landing_source["id"],
        *(node_id for node_id in landing_models | landing_relations if node_id in nodes),
        account_source["id"],
        account_model["id"],
    }
    for node_id in column_nodes:
        properties = nodes[node_id].setdefault("properties", {})
        properties["test_column"] = {"name": "ACCESSNO", "scope": "single-column trial"}

    column_edge_keys = {
        (program["id"], "READS_FROM", source_file["id"]),
        (program["id"], "WRITES_TO", extract["id"]),
        (extract["id"], "CARRIED_BY", channel["id"]),
        (channel["id"], "LANDS_IN", hvr_relation["id"]),
    }
    for edge in edges.values():
        matches_column_path = (
            (edge["type"] == "READS_FROM" and edge["source"] == program["id"] and edge["target"] == source_file["id"])
            or (edge["type"] == "WRITES_TO" and edge["source"] == program["id"] and edge["target"] == extract["id"])
            or (edge["type"] == "CARRIED_BY" and edge["source"] == extract["id"] and edge["target"] == channel["id"])
            or (edge["type"] == "LANDS_IN" and edge["source"] == channel["id"] and edge["target"] == hvr_relation["id"])
        )
        if matches_column_path:
            edge.setdefault("properties", {})["column_evidence"] = {
                "column": "ACCESSNO",
                "evidence": "KWDW_FEE emits the CLIENT record ID as the leading AccessNo field; HVR carries the row payload.",
            }
        elif edge["type"] in {"DEPENDS_ON", "MATERIALIZES_AS"}:
            edge.setdefault("properties", {})["column_evidence"] = {
                "column": "ACCESSNO",
                "evidence": "The selected dbt SQL and YAML retain ACCESSNO through this model stage.",
            }

    hvr_relation_leaf = _node_name(hvr_relation).split(".")[-1].upper()
    landing_raw_relation = next(
        node for node in landing["nodes"]
        if node["id"] in landing_relations
        and _node_name(node).split(".")[-1].upper() == hvr_relation_leaf
    )
    landing_public_relation = next(
        node for node in landing["nodes"]
        if node["id"] in landing_relations
        and _node_name(node).upper().endswith("ULTRACS_PUBLIC.FEEEXEMPTION")
    )
    account_source_relation = next(
        node for node in account["nodes"]
        if node["type"] == "SNOWFLAKE_RELATION"
        and node["id"] in account_relations
        and "ULTRACS_PUBLIC.FEEEXEMPTION" in _node_name(node).upper()
    )

    enterprise = enterprise_graph if enterprise_graph is not None else json.loads(ENTERPRISE_GRAPH_PATH.read_text(encoding="utf-8"))
    enterprise_hits = [
        node["id"] for node in enterprise["nodes"]
        if "FEEEXEMPTION" in json.dumps(node, ensure_ascii=False).upper()
        or "ACCESSNO" in json.dumps(node, ensure_ascii=False).upper()
    ]

    return {
        "nodes": normalize_records(list(nodes.values()), source_root=source_root),
        "edges": normalize_records(list(edges.values()), source_root=source_root),
        "test_column": field_info,
        "candidate_links": [
            {
            "from": hvr_relation["id"],
            "to": landing_raw_relation["id"],
                "confidence": "inferred",
                "reason": "HVR base table name matches the dbt source table name, but HVR database/schema identity is not present in the channel export.",
            },
            {
                "from": landing_public_relation["id"],
                "to": account_source_relation["id"],
                "confidence": "inferred",
                "reason": "Both declare ULTRACS_PUBLIC.FEEEXEMPTION, but the landing target database and account source database are different unresolved templates.",
            },
        ],
        "repository_scope": {
            "kb-ultracs-datawarehouse": "KWDW_FEE reads CLIENT by ID and emits DWFEE605.TXT with an AccessNo header.",
            "kb-cdp-hvr": "ult_sf_fee60 captures DWFEE605.TXT and lands a row payload in FEEEXEMPTION_V1_INGEST.",
            "kb-cdp-tenant-landing": "Only ultracs-v1 was parsed; ACCESSNO is payload field 1 and is retained through raw/delta/history/public dbt models.",
            "kb-cdp-tenant-account": "The feeexemption dbt model declares ultracs_landing.feeexemption as a source and outputs ACCESSNO.",
            "kb-cdp-tenant-enterprise": "The selected Enterprise graph was checked and contains no ACCESSNO/feeexemption continuation.",
        },
        "enterprise_matches": enterprise_hits,
    }


def _html_document(graph: dict[str, Any], explanation: str) -> str:
    enriched = describe_graph({"nodes": graph["nodes"], "edges": graph["edges"]})
    embedded = json.dumps(enriched, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    summary = html.escape(graph["test_column"]["notes"])
    candidates = "".join(
        f"<li>{html.escape(item['from'])} ⇢ {html.escape(item['to'])}: {html.escape(item['reason'])}</li>"
        for item in graph["candidate_links"]
    )
    explanation = html.escape(explanation)
    template = read_template("landing_account_template.html")
    return (template.replace("__SUMMARY__", summary)
            .replace("__CANDIDATES__", candidates)
            .replace("__EXPLANATION__", explanation)
            .replace("__GRAPH_JSON__", embedded))


def build_explanation(graph: dict[str, Any]) -> str:
    candidates=graph["candidate_links"]
    return "\n".join([
        "# ACCESSNO Landing Lineage Test",
        "",
        "## Scope",
        "",
        "This is an isolated one-column trial in `output/landing_account_no_test/`. It parses only `kb-cdp-tenant-landing/products/ultracs-v1`; the other repositories are consulted only for selected source, route, consumer, and gap evidence. The canonical table and column graphs are not modified.",
        "",
        "## Selected Column",
        "",
        "`ACCESSNO` is the account-number example. `KWDW_FEE` reads the `CLIENT` record by `ID`, writes `ID` before the delimited fields to `DWFEE605.TXT`, and the header labels the leading field `AccessNo`. HVR captures that filename. The landing raw model parses payload field 1 as `NUMBER(38, 0)` and its YAML classifies the field as `SENSITIVE`.",
        "",
        "The selected landing path is `feeexemption_raw` -> `feeexemption_delta` -> `feeexemption_history` -> `feeexemption` (`ULTRACS_PUBLIC`). The SQL and YAML retain `ACCESSNO` through those models; history uses it in its unique key. The account tenant separately declares `ultracs_landing.feeexemption` and its `feeexemption` model selects `ACCESSNO`.",
        "",
        "## Five-Repository Placement",
        "",
        "`kb-ultracs-datawarehouse` -> `kb-cdp-hvr` -> `kb-cdp-tenant-landing` -> `kb-cdp-tenant-account` -> selected `kb-cdp-tenant-enterprise` scope.",
        "",
        "The first four repositories have field- or table-level evidence for this example. The selected Enterprise graph contains no `feeexemption` or `ACCESSNO` match, so no Enterprise continuation is drawn.",
        "",
        "## Unjoined Relation Identities",
        "",
        f"1. HVR relation `{candidates[0]['from']}` and landing source relation `{candidates[0]['to']}` share a base table name. The HVR export does not provide the target database/schema identity, so the graph leaves them disconnected.",
        f"2. Landing public relation `{candidates[1]['from']}` and the account dbt source relation `{candidates[1]['to']}` share `ULTRACS_PUBLIC.FEEEXEMPTION`. Their database values are different unevaluated templates (`target.database` versus an environment-variable expression), so the graph leaves them disconnected.",
        "",
        "These are candidate joins, not edges. No inferred connection is inserted to make the picture look continuous.",
        "",
        "## Gap Assessment",
        "",
        "- **HVR pattern parser gap:** addressed for this path. The parser retains `Capture.Pattern`, and the existing table graph has an inferred `CARRIED_BY` match for `DWFEE605.TXT` -> `ult_sf_fee60`.",
        "- **Direct HVR to account RAW bridge:** not addressed. This sample follows HVR direct landing into tenant landing; account-v1's separate `RAW` source path remains a different branch.",
        "- **Physical relation continuity:** partially demonstrated at model level, not resolved generally. The landing dbt `ref()` chain is represented, but the two cross-repository physical identity joins remain unresolved as above.",
        "- **Traversal direction:** unchanged. `READS_FROM` is stored PROGRAM -> MV_FILE; traverse it backward to narrate source -> program.",
        "- **Enterprise column continuation:** none found for this selected field in the current Enterprise extension.",
        "",
        "## Evidence Files",
        "",
        "- `kb-ultracs-datawarehouse/KWDW_FEE`",
        "- `kb-cdp-hvr/hvr-config/apps/channels/ult_sf_fee60.json`",
        "- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/source.yml`",
        "- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_raw/feeexemption_raw.sql` and `.yml`",
        "- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_delta/feeexemption_delta.sql`",
        "- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/feeexemption_history/feeexemption_history.sql` and `.yml`",
        "- `kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/public/feeexemption/feeexemption.sql` and `.yml`",
        "- `kb-cdp-tenant-account/products/accounts-v1/dbt/models/account_raw_source.yml` and `models/public/feeexemption/feeexemption.sql`",
        "",
        "Static repository evidence only; no runtime jobs or Snowflake catalog were queried.",
        "",
    ])


def main(source_root: Path | None = None, destination: Path = OUTPUT_DIR) -> None:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    graph=build_test_graph(source_root=source_root)
    graph=describe_graph(graph)
    graph_path=destination/"account_no_lineage.json"
    explanation_path=destination/"account_no_lineage_explanation.md"
    html_path=destination/"account_no_lineage.html"
    graph_path.write_text(json.dumps(graph,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    explanation=build_explanation(graph)
    explanation_path.write_text(explanation,encoding="utf-8")
    html_path.write_text(_html_document(graph,explanation),encoding="utf-8")
    print(f"Generated {graph_path}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    print(f"Generated {html_path} and {explanation_path}")


if __name__=="__main__":
    main()
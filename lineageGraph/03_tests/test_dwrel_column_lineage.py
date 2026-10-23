import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import generate_dwrel_column_lineage as dwrel

FULL_GRAPH = json.loads(dwrel.FULL_GRAPH_PATH.read_text(encoding="utf-8"))
GRAPH = dwrel.build_graph(FULL_GRAPH)
RECORDS = dwrel.build_records(GRAPH, FULL_GRAPH)
BY_PARAM = {record["param_column"]: record for record in RECORDS}


def test_basic_fields_pair_with_every_param_column_in_order():
    fields, reads, definitions = dwrel._basic_dwrel_fields()
    parameters, flags = dwrel._param_columns()

    assert len(fields) == len(parameters) == 15
    assert flags == []
    assert fields[3]["expression"] == "AREC<30,X>" and fields[3]["source_line"] == 434
    assert [record["param_column"] for record in RECORDS][:6] == [
        "AccountNo", "Product", "CustomerNo", "RelType", "StmtType", "SignatoryonAccount",
    ]
    assert fields[6]["empty_when"] == 'EREC<5>=""'
    assert [item["expression"] for item in fields[6]["continuations"]] == [
        '",":EREC<5,2>', '",":EREC<5,3>', '",":EREC<5,4>',
    ]
    assert reads["AREC"]["file"] == "ACCOUNT" and reads["EREC"]["file"] == "EMAIL.DETAILS"
    assert definitions["CIS"][0]["text"] == "CIS = FIELD(NID,'S',1)"


def test_reltype_maps_to_role_type_in_internal_and_public_relations():
    record = BY_PARAM["RelType"]

    assert record["ultracs_position"] == 4
    assert record["confidence"] == "inferred"
    assert record["ultracs"]["source_locator"] == "AREC<30,X>"
    assert {(target["stage"], target["relation"]) for target in record["dbt_targets"]} == {
        ("internal", "snowflake:relation:INTERNAL.ACCOUNT_RELATIONSHIP_V1__CUSTOMER_ACCOUNT_RELATIONSHIP_V1"),
        ("public", "snowflake:relation:PUBLIC.ACCOUNT_RELATIONSHIP_V1__CUSTOMER_ACCOUNT_RELATIONSHIP"),
        ("internal", "snowflake:relation:INTERNAL.V_ACCOUNT_RELATIONSHIP_V1__ACCRELATIONSHIP_V1"),
        ("public", "snowflake:relation:PUBLIC.VW_ACCOUNT_RELATIONSHIP_V1__ACCRELATIONSHIP_V1"),
    }
    assert {target["column"] for target in record["dbt_targets"]} == {"ACCOUNTINVOLVEMENTROLETYPE"}
    assert record["ingestion_route"]["dbt_input"] == "DATA:RelType"


def test_params_without_a_dbt_projection_stay_unmapped():
    unmapped = {name for name, record in BY_PARAM.items() if not record["dbt_targets"]}

    assert unmapped == {"EmailFormat", "EmailPassword", "EmailFlg", "LetterFlg"}
    assert all(BY_PARAM[name]["snowflake_table"] is None for name in unmapped)
    assert all(BY_PARAM[name]["dbt_mapping_status"] == "no_dbt_projection_found" for name in unmapped)


def test_dbt_key_case_difference_is_preserved_not_corrected():
    record = BY_PARAM["Emailaddress"]

    assert record["ingestion_route"]["dbt_input"] == "DATA:EmailAddress"
    assert {item["dbt_key"] for item in record["dbt_key_case_differences"]} == {"EmailAddress"}
    assert "differs in case" in record["notes"]


def test_direct_branch_is_reported_but_not_joined():
    branch = RECORDS[0]["ingestion_route"]["separate_direct_branch"]
    node_ids = {node["id"] for node in GRAPH["nodes"]}

    assert branch["hvr_channels"] == ["ult_sf_rel"]
    assert branch["landing_relations"] == ["snowflake:relation:LOADRELATIONSHIPS_INGEST"]
    assert branch["associated_with_extract_by_capture_pattern"] is False
    assert branch["joined_to_raw_relation"] is False
    assert "hvr:channel:ult_sf_rel" not in node_ids
    assert "snowflake:relation:LOADRELATIONSHIPS_INGEST" not in node_ids


def test_slice_graph_has_unique_nodes_valid_edges_and_target_relations():
    node_ids = [node["id"] for node in GRAPH["nodes"]]
    edge_keys = [(edge["source"], edge["type"], edge["target"]) for edge in GRAPH["edges"]]

    assert len(node_ids) == len(set(node_ids)) and len(edge_keys) == len(set(edge_keys))
    assert all(edge["source"] in set(node_ids) and edge["target"] in set(node_ids) for edge in GRAPH["edges"])
    assert {node["type"] for node in GRAPH["nodes"]}.isdisjoint({"HVR_PARAM_FILE", "HVR_COLUMN"})
    assert all(
        target["relation"] in set(node_ids)
        for record in RECORDS
        for target in record["dbt_targets"]
    )
    assert {gap["id"] for gap in GRAPH["gap_register"]} >= {"direct-branch-boundary", "direct-branch-not-associated"}

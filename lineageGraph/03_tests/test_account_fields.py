from pathlib import Path

from lineage.account_fields import FIELD_MAPPINGS, build_account_fields_graph
from lineage.exporters import export_cypher


REPO = Path(__file__).resolve().parents[2] / "kb-ultracs-datawarehouse"


def test_requested_fields_have_source_mappings():
    names = {mapping["field"] for mapping in FIELD_MAPPINGS}
    assert names == {
        "Account_Opened_Date",
        "Account_Name",
        "Signatory_Count",
        "Account_Index_ID",
        "Account_ID",
        "Balance",
    }


def test_graph_uses_parsed_jobs_and_marks_index_key_as_candidate():
    graph = build_account_fields_graph(REPO)
    node_ids = {node.id for node in graph.nodes}
    edge_types = {edge.type for edge in graph.edges}

    assert "job:KWDW_ACC" in node_ids
    assert "file:DWACC" in node_ids
    assert "field:Account_Index_ID" in node_ids
    assert "candidate_key:DWACC:CIS+PID" in node_ids
    assert "output:DWACC:Account_Index_ID" not in node_ids
    assert "channel:ult_sf_acc" in node_ids
    assert "table:loadaccounts_ingest" in node_ids
    assert "channel:ult_s3_acc1" in node_ids
    assert "channel:ult_s3_acc2" in node_ids
    assert "dataset:DWACC.parquet" in node_ids
    assert "config:DWACC.param" in node_ids
    assert "config:ult_sf_acc.json" in node_ids
    assert "writes" in edge_types
    account_index = next(node for node in graph.nodes if node.id == "field:Account_Index_ID")
    assert account_index.properties["confidence"] == "candidate_composite_key"
    assert account_index.properties["hvr_param_status"] == "INFERRED"
    assert account_index.properties["direct_snowflake_status"] == "INFERRED"

    open_date = next(node for node in graph.nodes if node.id == "column:DWACC.parquet:OpenDate")
    assert open_date.properties["position"] == 54
    assert open_date.properties["lineage_status"] == "CONFIRMED"
    payload = next(node for node in graph.nodes if node.id == "column:loadaccounts_ingest:payload")
    assert payload.properties["data_type"] == "varchar(max)"
    snowflake_columns = {
        node.properties["name"]
        for node in graph.nodes
        if node.label == "snowflake_column"
    }
    assert snowflake_columns == {"payload", "integration_timestamp"}

    parquet_columns = {
        node.properties["name"]
        for node in graph.nodes
        if node.label == "parquet_column"
    }
    assert parquet_columns == {
        "OpenDate",
        "AccountName",
        "NumOfSignaturesReq",
        "Account",
        "Prod",
        "KiwiAcc",
        "Balance",
    }

    mappings = [edge for edge in graph.edges if edge.type == "positionally_named_as"]
    assert mappings
    assert {edge.properties["lineage_status"] for edge in mappings} == {"CONFIRMED"}
    direct_field_edges = [edge for edge in graph.edges if edge.type == "carried_by_row_pattern"]
    assert direct_field_edges
    assert {edge.properties["lineage_status"] for edge in direct_field_edges} == {"INFERRED"}
    candidate = next(edge for edge in graph.edges if edge.type == "candidate_mapping")
    assert candidate.properties["lineage_status"] == "INFERRED"


def test_cypher_contains_source_transform_output_and_business_field(tmp_path):
    graph = build_account_fields_graph(REPO)
    output_path = tmp_path / "lineage.cypher"
    export_cypher(graph, output_path)
    cypher = output_path.read_text(encoding="utf-8")

    assert "CREATE CONSTRAINT lineage_node_id IF NOT EXISTS" in cypher
    assert "`" not in cypher
    assert "source:LineageNode" in cypher
    assert "candidate_key:DWACC:CIS+PID" in cypher
    assert "config:DWACC.param" in cypher
    assert "lineage_status: 'CONFIRMED'" in cypher
    assert "lineage_status: 'INFERRED'" in cypher
    assert "Account_Opened_Date" in cypher
    assert "Account_Name" in cypher
    assert "Signatory_Count" in cypher
    assert "Account_ID" in cypher
    assert "Balance" in cypher

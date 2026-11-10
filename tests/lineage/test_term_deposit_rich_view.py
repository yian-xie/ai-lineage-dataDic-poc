import json
import re

from lineage_poc.viewers.graph.term_deposit import render_term_deposit_html


def _node(identifier, node_type, name, **properties):
    return {"id": identifier, "type": node_type, "properties": {"name": name, "source_path": "fixture/source", **properties}}


def test_dwdts_rich_view_uses_saved_route_branches_and_embeds_dictionary():
    program = "program:KWDW_TDS"
    extract = "extract:DWTDS.TXT"
    s3_channel = "hvr:channel:ult_s3_actd1"
    direct_channel = "hvr:channel:ult_sf_tdst"
    shared_location = "hvr:location:fs_ultracs"
    raw_source = "dbt:source:ACCOUNTS_V1__TERM_DEPOSITS_RAW"
    raw_relation = "snowflake:relation:RAW.ACCOUNTS_V1__TERM_DEPOSITS_RAW"
    internal_model = "dbt:model:accounts_v1__term_deposits_v1"
    internal_relation = "snowflake:relation:INTERNAL.ACCOUNTS_V1__TERM_DEPOSITS_V1"
    direct_relation = "snowflake:relation:TERMDEPOSITS_INGEST"
    graph = {
        "nodes": [
            _node("basic:file:TRAN", "MV_FILE", "TRAN"),
            _node(program, "PROGRAM", "KWDW_TDS"),
            _node(extract, "EXTRACT_FILE", "DWTDS.TXT"),
            _node(s3_channel, "HVR_CHANNEL", "ult_s3_actd1"),
            _node(shared_location, "HVR_LOCATION", "fs_ultracs"),
            _node("s3:path:HVR:ultracs:dwtds", "S3_PATH", "dwtds"),
            _node(direct_channel, "HVR_CHANNEL", "ult_sf_tdst"),
            _node(raw_source, "DBT_SOURCE", "ACCOUNTS_V1__TERM_DEPOSITS_RAW", relation="RAW.ACCOUNTS_V1__TERM_DEPOSITS_RAW"),
            _node(raw_relation, "SNOWFLAKE_RELATION", "RAW.ACCOUNTS_V1__TERM_DEPOSITS_RAW"),
            _node(internal_model, "DBT_MODEL", "accounts_v1__term_deposits_v1"),
            _node(internal_relation, "SNOWFLAKE_RELATION", "INTERNAL.ACCOUNTS_V1__TERM_DEPOSITS_V1"),
            _node(direct_relation, "SNOWFLAKE_RELATION", "termdeposits_ingest"),
        ],
        "edges": [
            {"source": program, "target": "basic:file:TRAN", "type": "READS_FROM", "properties": {"confidence": "explicit", "source_path": "fixture/source"}},
            {"source": program, "target": extract, "type": "WRITES_TO", "properties": {"confidence": "explicit", "source_path": "fixture/source"}},
            {"source": extract, "target": s3_channel, "type": "CARRIED_BY", "properties": {"confidence": "inferred", "source_path": "fixture/hvr"}},
            {"source": s3_channel, "target": shared_location, "type": "CAPTURES_FROM", "properties": {"confidence": "explicit", "source_path": "fixture/hvr"}},
            {"source": s3_channel, "target": "s3:path:HVR:ultracs:dwtds", "type": "COPIES_TO", "properties": {"confidence": "explicit", "source_path": "fixture/hvr"}},
            {"source": extract, "target": direct_channel, "type": "CARRIED_BY", "properties": {"confidence": "explicit", "source_path": "fixture/hvr"}},
            {"source": direct_channel, "target": shared_location, "type": "CAPTURES_FROM", "properties": {"confidence": "explicit", "source_path": "fixture/hvr"}},
            {"source": direct_channel, "target": direct_relation, "type": "LANDS_IN", "properties": {"confidence": "explicit", "source_path": "fixture/hvr"}},
            {"source": internal_model, "target": raw_source, "type": "DEPENDS_ON", "properties": {"confidence": "explicit", "source_path": "fixture/dbt"}},
            {"source": raw_source, "target": raw_relation, "type": "RESOLVES_TO", "properties": {"confidence": "explicit", "source_path": "fixture/dbt"}},
            {"source": internal_model, "target": internal_relation, "type": "MATERIALIZES_AS", "properties": {"confidence": "explicit", "source_path": "fixture/dbt"}},
        ],
    }
    target = {
        "stage": "internal",
        "model": "accounts_v1__term_deposits_v1",
        "relation": internal_relation,
        "column": "ACCOUNTNUMBER",
        "data_type": "VARCHAR",
        "description": "Account identifier",
        "source_expression": "DATA:Accounts::STRING AS ACCOUNTNUMBER",
        "source_path": "fixture/dbt",
    }
    records = [
        {
            "field_id": "ultracs:ACCOUNT:DWTDS:1",
            "business_field": "Accounts",
            "param_column": "Accounts",
            "ultracs_position": 1,
            "extract_file": "DWTDS.TXT",
            "confidence": "inferred",
            "source_path": "fixture/hvr",
            "notes": "Positional BASIC/HVR association.",
            "ultracs": {"source_path": "fixture/source", "basic_expression": "CIS", "source_locator": "CIS"},
            "cdp": target,
            "dbt_targets": [target],
            "snowflake_table": internal_relation,
            "snowflake_column": "ACCOUNTNUMBER",
            "ingestion_route": {"hvr_channels": ["ult_s3_actd1"]},
        },
        {
            "field_id": "ultracs:ACCOUNT:DWTDS:15",
            "business_field": "Prod",
            "param_column": "Prod",
            "ultracs_position": 15,
            "extract_file": "DWTDS.TXT",
            "confidence": "inferred",
            "source_path": "fixture/hvr",
            "notes": "No exact target.",
            "ultracs": {"source_path": "fixture/source", "basic_expression": "NRATE"},
            "dbt_targets": [],
            "ingestion_route": {"hvr_channels": ["ult_s3_actd1"]},
        },
    ]

    page = render_term_deposit_html(graph, records, "<!doctype html><title>Embedded data dictionary</title>")
    match = re.search(r'<script id="feed-config" type="application/json">(.*?)</script>', page)
    assert match
    config = json.loads(match.group(1))

    assert "Detailed" in page and "Schema overview" in page and "Data Dictionary" in page
    assert "vis.Network" in page and "Embedded data dictionary" in page
    assert "DWTDS Term Deposit Column Lineage" in page
    assert {"from": program, "to": extract} in config["schemaFlowLinks"]
    assert {"from": raw_relation, "to": raw_source} in config["schemaFlowLinks"]
    assert config["schemaDirectBranch"]["target"]["id"] == direct_relation
    assert "No repository evidence connects" in config["directBranchGap"]
    assert direct_relation not in config["mappedPathNodeIds"]
    assert config["routes"][shared_location] == "shared"
    assert config["routes"][s3_channel] == "s3"
    assert config["routes"][direct_channel] == "direct"
    assert "dbt:source:ACCOUNTS_V1__TERM_DEPOSITS_RAW" in config["mappedPathNodeIds"]
    assert "DWTDS position" in page
    assert "term_deposit_graph.json" in page
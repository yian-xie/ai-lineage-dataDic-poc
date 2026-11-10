import json
from pathlib import Path

import pytest

from lineage_poc.columns.dwacc import build_records
from lineage_poc.graph.account_data_slice import build_account_data_slice
from lineage_poc.parsers import parse_landing_repo, parse_protect_downstream
from lineage_poc.paths import REFERENCE_LINEAGE, source_root


WORKSPACE = source_root()
PROTECT_ROOT = WORKSPACE / "kb-cdp-tenant-protect-downstream"
LANDING_ROOT = WORKSPACE / "kb-cdp-tenant-landing"


@pytest.mark.source_repos
def test_account_open_date_slice_includes_account_protect_landing_and_gaps():
    if not PROTECT_ROOT.is_dir() or not LANDING_ROOT.is_dir():
        pytest.skip("The Account slice requires the configured Protect and Landing source checkouts.")

    account_graph = json.loads((REFERENCE_LINEAGE / "account_table_lineage.json").read_text(encoding="utf-8"))
    records = build_records(table_graph=account_graph)
    protect_nodes, protect_edges = parse_protect_downstream(PROTECT_ROOT)
    landing_nodes, landing_edges = parse_landing_repo(LANDING_ROOT, products=("ultracs-v1",))
    result = build_account_data_slice(
        account_graph,
        records,
        {"nodes": protect_nodes, "edges": protect_edges},
        {"nodes": landing_nodes, "edges": landing_edges},
        WORKSPACE,
    )

    node_ids = {node["id"] for node in result["nodes"]}
    edge_keys = {(edge["source"], edge["type"], edge["target"]) for edge in result["edges"]}
    field_id = "ultracs:SAVINGS_ACCOUNT:DWACC:54"
    account_relation = "snowflake:relation:PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL"

    assert result["slice"]["field_id"] == field_id
    assert len(result["field_mappings"]) == 1
    assert result["field_mappings"][0]["business_field"] == "Account_Opened_Date"
    dwacc = next(node for node in result["nodes"] if node["type"] == "EXTRACT_FILE" and node["properties"].get("name") == "DWACC")
    assert [item["business_field"] for item in dwacc["properties"]["related_columns"]] == ["Account_Opened_Date"]
    assert any("sys_pds_stg_account_v1__ultracs_account" in node["id"] for node in result["nodes"])
    assert any("sys_pds_account_v1__account_v2" in node["id"] for node in result["nodes"])
    assert any("loadnewaccounts_raw" in node["id"] for node in result["nodes"])
    assert any(gap["id"] == "ACCOUNT-OPEN-DATE-PROTECT-NULL" for gap in result["gap_register"])
    assert any(gap["id"] == "ACCOUNT-DWACC-LANDING-HANDOFF" for gap in result["gap_register"])
    candidate = next(link for link in result["candidate_links"] if link["from"] == account_relation)
    assert candidate["confidence"] == "inferred"
    assert (candidate["from"], "RESOLVES_TO", candidate["to"]) not in edge_keys
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in result["edges"])
    assert all(node["properties"].get("source_path") for node in result["nodes"])
    assert all(edge["properties"].get("source_path") for edge in result["edges"])
    assert all(
        edge["properties"].get("reason")
        for edge in result["edges"]
        if edge["properties"].get("confidence") == "inferred"
    )
    assert all(
        path.startswith(("kb-cdp-tenant-protect-downstream/", "kb-cdp-tenant-landing/"))
        for node in result["nodes"]
        for path in node["properties"].get("source_paths", [])
        if "sys_pds_stg_account_v1" in node["id"] or "loadnewaccounts" in node["id"].casefold()
    )

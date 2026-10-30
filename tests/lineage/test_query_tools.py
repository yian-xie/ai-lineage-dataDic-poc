from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT
from pathlib import Path

PROJECT_ROOT = REPOSITORY_ROOT

from lineage_poc.graph.query_tools.tools import get_alias_chain, get_consumers, get_field_lineage


def test_get_field_lineage_traces_account_to_reachable_snowflake_relation():
    result = get_field_lineage("Account")

    assert result["paths"]
    path = result["paths"][0]
    assert path["nodes"][0]["type"] == "MV_FILE"
    assert path["nodes"][0]["properties"]["name"] == "ACCOUNT"
    assert any(node["type"] == "EXTRACT_FILE" and node["properties"]["name"] == "DWACC" for node in path["nodes"])
    assert path["nodes"][-1]["type"] == "SNOWFLAKE_RELATION"
    assert all("confidence" in edge for edge in path["edges"])
    assert any(edge["type"] == "READS_FROM" and edge["traversal"] == "reversed" for edge in path["edges"])
    assert result["field_mappings"]


def test_get_consumers_returns_snowflake_relations_from_dwacc():
    result = get_consumers("DWACC")

    assert result["consumers"]
    assert all(node["type"] == "SNOWFLAKE_RELATION" for node in result["consumers"])
    assert any(node["properties"]["name"] == "loadaccounts_ingest" for node in result["consumers"])
    assert result["paths"]
    assert all("confidence" in edge for edge in result["edges"])


def test_get_alias_chain_reports_account_aliases_and_confidence_per_hop():
    result = get_alias_chain("Account")

    alias_names = {alias["name"] for alias in result["aliases"]}
    assert {"CIS", "Account", "ACCESSNUMBER"} <= alias_names
    assert {alias["layer"] for alias in result["aliases"]} >= {"source", "extract/HVR", "internal", "public"}
    assert result["edges"]
    assert all("confidence" in edge for edge in result["edges"])
    assert any(edge["confidence"] == "inferred" for edge in result["edges"])
    assert any(edge["confidence"] == "unspecified" for edge in result["edges"])

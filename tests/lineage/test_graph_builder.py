from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT
from lineage_poc.graph.builder import build_sample_graph
import json
from pathlib import Path

PROJECT_ROOT = REPOSITORY_ROOT

from lineage_poc.graph.query import query_columns, search_graph, shortest_path, trace_graph


def test_graph_has_expected_nodes():
    graph = build_sample_graph()
    node_ids = {node.id for node in graph.nodes}
    assert "ULTRACS" in node_ids
    assert "KWDW_ACC" in node_ids
    assert "raw_ultracs_account_summary" in node_ids
    assert "dim_account" in node_ids
    assert "fact_account_balance" in node_ids


def test_graph_has_expected_edges():
    graph = build_sample_graph()
    edge_types = {edge.type for edge in graph.edges}
    assert "contains_file" in edge_types
    assert "loaded_to" in edge_types
    assert "transformed_to" in edge_types
    assert "curated_as" in edge_types
    assert "aggregated_into" in edge_types


def test_query_graph_search_and_node_detail_report_stored_and_semantic_direction():
    graph = {
        "nodes": [
            {"id": "program", "type": "PROGRAM", "properties": {}},
            {"id": "file", "type": "MV_FILE", "properties": {"name": "ACCOUNT"}},
            {"id": "extract", "type": "EXTRACT_FILE", "properties": {}},
        ],
        "edges": [
            {"source": "program", "target": "file", "type": "READS_FROM", "properties": {"confidence": "explicit"}},
            {"source": "program", "target": "extract", "type": "WRITES_TO", "properties": {}},
        ],
    }

    results = search_graph(graph, "ACCOUNT")
    assert results["node_match_count"] == 1
    assert results["edge_match_count"] == 0
    details = trace_graph(graph, "file", "downstream", 2)
    assert [node["id"] for node in details["nodes"]] == ["file", "program", "extract"]
    assert details["hops"][0]["edge_type"] == "READS_FROM"
    assert details["hops"][0]["traversal"] == "reversed"
    assert details["hops"][0]["confidence"] == "explicit"


def test_query_graph_stops_at_boundary_nodes_and_finds_semantic_paths():
    graph = {
        "nodes": [
            {"id": "source", "properties": {}},
            {"id": "boundary", "properties": {"is_boundary_node": True}},
            {"id": "target", "properties": {}},
        ],
        "edges": [
            {"source": "source", "target": "boundary", "type": "MAPS_TO", "properties": {}},
            {"source": "boundary", "target": "target", "type": "MAPS_TO", "properties": {}},
        ],
    }

    assert trace_graph(graph, "source", "downstream", 4)["nodes"] == [graph["nodes"][0], graph["nodes"][1]]
    assert shortest_path(graph, "source", "target")["path"] is None


def test_query_columns_matches_parameter_target_and_business_field(tmp_path):
    mappings = [{
        "param_column": "AltAccountName",
        "snowflake_column": "ALTERNATEACCOUNTNAME",
        "business_field": "Alternative Account Name",
    }]
    path = tmp_path / "column_lineage.json"
    path.write_text(json.dumps(mappings), encoding="utf-8")

    for selector in ("AltAccountName", "alternate account name", "ALTERNATEACCOUNTNAME"):
        assert query_columns(path, selector)["match_count"] == 1

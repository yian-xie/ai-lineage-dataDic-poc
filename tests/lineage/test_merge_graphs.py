from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT
import json
from pathlib import Path

import pytest

PROJECT_ROOT = REPOSITORY_ROOT

from lineage_poc.graph.merge import merge_graph_documents


def test_merge_adds_unique_nodes_and_keeps_richer_node():
    left = {
        "nodes": [
            {"id": "source", "type": "MV_FILE", "properties": {"name": "ACCOUNT"}},
            {"id": "target", "type": "SNOWFLAKE_RELATION", "properties": {"name": "RAW.ACCOUNTS"}},
        ],
        "edges": [],
    }
    right = {
        "nodes": [
            {"id": "source", "type": "MV_FILE", "properties": {"name": "ACCOUNT", "source_path": "basic/ACCOUNT"}},
            {"id": "extra", "type": "PROGRAM", "properties": {"name": "KWDW_ACC"}},
        ],
        "edges": [],
    }

    merged, conflicts = merge_graph_documents(left, right)

    assert {node["id"] for node in merged["nodes"]} == {"source", "target", "extra"}
    source = next(node for node in merged["nodes"] if node["id"] == "source")
    assert source["properties"]["source_path"] == "basic/ACCOUNT"
    assert len(conflicts) == 1
    assert conflicts[0]["kind"] == "node_conflict"
    assert conflicts[0]["resolution"] == "more_properties"


def test_merge_keeps_higher_confidence_edge_and_logs_conflict():
    nodes = [
        {"id": "source", "type": "PROGRAM", "properties": {}},
        {"id": "target", "type": "EXTRACT_FILE", "properties": {}},
    ]
    left = {
        "nodes": nodes,
        "edges": [{"source": "source", "target": "target", "type": "WRITES_TO", "properties": {"confidence": "inferred"}}],
    }
    right = {
        "nodes": nodes,
        "edges": [{"source_key": "source", "target_key": "target", "edge_type": "WRITES_TO", "properties": {"confidence": "explicit"}}],
    }

    merged, conflicts = merge_graph_documents(left, right)

    assert len(merged["edges"]) == 1
    assert merged["edges"][0]["properties"]["confidence"] == "explicit"
    assert (merged["edges"][0]["source"], merged["edges"][0]["target"], merged["edges"][0]["type"]) == (
        "source", "target", "WRITES_TO"
    )
    assert len(conflicts) == 1
    assert conflicts[0]["kind"] == "edge_conflict"
    assert conflicts[0]["resolution"] == "higher_confidence"


def test_equal_node_richness_is_deterministic_and_logged():
    left = {"nodes": [{"id": "n", "type": "PROGRAM", "properties": {"name": "left"}}], "edges": []}
    right = {"nodes": [{"id": "n", "type": "PROGRAM", "properties": {"name": "right"}}], "edges": []}

    merged, conflicts = merge_graph_documents(left, right)

    assert merged["nodes"][0]["properties"]["name"] == "left"
    assert conflicts[0]["resolution"] == "equal_count_first_input_wins"


def test_merge_rejects_dangling_edge_endpoints():
    left = {"nodes": [{"id": "source", "type": "PROGRAM", "properties": {}}], "edges": []}
    right = {"nodes": [], "edges": [{"source": "source", "target": "missing", "type": "CALLS"}]}

    with pytest.raises(ValueError, match="missing endpoint"):
        merge_graph_documents(left, right)


def test_cli_writes_merged_graph_and_conflict_file(tmp_path, monkeypatch):
    import lineage_poc.graph.merge as merge_graphs

    left_path = tmp_path / "left.json"
    right_path = tmp_path / "right.json"
    output_path = tmp_path / "merged.json"
    left_path.write_text(json.dumps({
        "nodes": [{"id": "n", "type": "PROGRAM", "properties": {"name": "KWDW_ACC"}}],
        "edges": [{"source": "n", "target": "n", "type": "CALLS", "properties": {"confidence": "inferred"}}],
        "input_flags": [],
    }), encoding="utf-8")
    right_path.write_text(json.dumps({
        "nodes": [{"id": "n", "type": "PROGRAM", "properties": {"name": "KWDW_ACC", "source_path": "basic/KWDW_ACC"}}],
        "edges": [{"source": "n", "target": "n", "type": "CALLS", "properties": {"confidence": "explicit"}}],
        "input_flags": [],
    }), encoding="utf-8")
    monkeypatch.setattr(merge_graphs, "CONFLICT_OUTPUT", tmp_path / "merge_conflicts.json")
    monkeypatch.setattr(
        "sys.argv",
        ["merge_graphs.py", str(left_path), str(right_path), "--output", str(output_path)],
    )

    merge_graphs.main()

    merged = json.loads(output_path.read_text(encoding="utf-8"))
    conflicts = json.loads((tmp_path / "merge_conflicts.json").read_text(encoding="utf-8"))["conflicts"]
    assert merged["nodes"][0]["properties"]["source_path"] == "basic/KWDW_ACC"
    assert merged["edges"][0]["properties"]["confidence"] == "explicit"
    assert {conflict["kind"] for conflict in conflicts} == {"node_conflict", "edge_conflict"}
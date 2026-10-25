import json
import shutil

import pytest

from lineage_poc.html_checks import validate_view_inputs
from lineage_poc.paths import REFERENCE_DICTIONARY, REFERENCE_LINEAGE


def test_both_views_use_the_same_mapping_records_and_targets():
    report = validate_view_inputs(REFERENCE_DICTIONARY / "ai-enriched",
                                  REFERENCE_LINEAGE, REFERENCE_LINEAGE)
    assert report["mapping_records"] == 95
    assert report["target_pairs"] == 179


def test_reformatted_inventory_cannot_silently_change_dictionary_snapshot_ids(tmp_path):
    source = REFERENCE_LINEAGE / "column_lineage.json"
    (tmp_path / "column_lineage.json").write_text(
        json.dumps(json.loads(source.read_text(encoding="utf-8"))), encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inventory bytes"):
        validate_view_inputs(REFERENCE_DICTIONARY / "ai-enriched", tmp_path, REFERENCE_LINEAGE)


def test_mixed_graph_and_column_parse_snapshots_are_rejected(tmp_path):
    columns, graphs = tmp_path / "columns", tmp_path / "graphs"
    columns.mkdir()
    graphs.mkdir()
    shutil.copyfile(REFERENCE_LINEAGE / "column_lineage.json", columns / "column_lineage.json")
    (columns / "manifest.json").write_text('{"parse_manifest_sha256": "one"}')
    (graphs / "manifest.json").write_text('{"parse_manifest_sha256": "two"}')
    with pytest.raises(ValueError, match="different parse snapshots"):
        validate_view_inputs(REFERENCE_DICTIONARY / "ai-enriched", columns, graphs)


def test_missing_graph_target_context_is_not_presented_as_matching(tmp_path):
    (tmp_path / "table_lineage.json").write_text('{"nodes": [], "edges": []}')
    with pytest.raises(ValueError, match="every dictionary target"):
        validate_view_inputs(REFERENCE_DICTIONARY / "ai-enriched", REFERENCE_LINEAGE, tmp_path)

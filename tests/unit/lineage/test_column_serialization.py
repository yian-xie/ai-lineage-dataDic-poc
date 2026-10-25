import json
import os

import pytest

from lineage_poc.columns.serialization import write_inventory
from lineage_poc.lineage_workflow import build_columns, build_graphs, parse_sources


@pytest.mark.parametrize("value", [
    [{"param_column": "KiwiAcc", "description": "Māori\r\nsecond line", "empty": ""}],
    {"feeds": {"DWACC": {"description": "Māori\naccount", "dbt_target_projections": 179}}},
])
def test_inventory_bytes_match_legacy_platform_native_serializer(tmp_path, value):
    output = tmp_path / "inventory.json"
    write_inventory(output, value)
    expected = (json.dumps(value, indent=2) + "\n").replace("\n", os.linesep).encode("utf-8")
    assert output.read_bytes() == expected
    assert b"\\u0101" in output.read_bytes()
    assert json.loads(output.read_bytes()) == value


def test_column_stage_keeps_native_inventory_bytes_and_canonical_lf_manifest(source_factory, tmp_path):
    parsed, graphs, columns = (tmp_path / name for name in ("parsed", "graphs", "columns"))
    parse_sources(source_factory(), parsed)
    build_graphs(parsed, graphs, scope="account")
    build_columns(parsed, graphs, columns)
    output = columns / "column_lineage.json"
    records = json.loads(output.read_bytes())
    expected = (json.dumps(records, indent=2) + "\n").replace("\n", os.linesep).encode("utf-8")
    assert output.read_bytes() == expected
    assert b"\\u0101" in output.read_bytes()
    manifest = (columns / "manifest.json").read_bytes()
    assert b"\r\n" not in manifest
    assert manifest.endswith(b"\n")

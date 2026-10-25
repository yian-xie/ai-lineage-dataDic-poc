from pathlib import Path

from lineage_poc.columns.dwacc import _dbt_data_projections, _dwacc_output_fields, _selected_sql_projections
from lineage_poc.parsers import parse_dbt_project, parse_hvr_config, parse_hvr_param
from lineage_poc.parsers.ultracs_basic import parse_ultracs_basic_file, parse_ultracs_record

FIXTURES = Path(__file__).parent / "fixtures"


def test_basic_comments_expressions_and_empty_values_are_preserved(source_factory):
    program = parse_ultracs_basic_file(FIXTURES / "KWDW_SAMPLE")
    assert program.name == "KWDW_SAMPLE"
    assert program.open_files == ["ACCOUNT", "TRAN"]
    fields = _dwacc_output_fields(source_root=source_factory())
    assert fields[0]["expression"] == "REC<4,8>"
    assert fields[0]["source_line"] == 9
    assert "Kiwibank account number — Māori" in program.source
    assert parse_ultracs_record("a||Māori|") == ["a", "", "Māori", ""]


def test_hvr_declaration_order_and_unicode_are_not_alphabetized():
    graph = parse_hvr_param(FIXTURES / "ordered.param")
    columns = [node for node in graph.nodes if node.label == "HVR_COLUMN"]
    assert [column.properties["name"] for column in columns] == ["SecondAlphabetically", "FirstAlphabetically", "MissingColumn1"]
    assert columns[0].properties["description"] == "Māori\nsecond line"
    assert columns[1].properties["description"] == ""
    assert columns[2].properties["description"] is None
    assert {edge.type for edge in graph.edges} == {"DECLARES_COLUMN"}


def test_hvr_channel_keeps_capture_evidence_separate_from_parameter_metadata():
    graph = parse_hvr_config(FIXTURES / "channel.json")
    assert next(node for node in graph.nodes if node.label == "HVR_CHANNEL").properties["capture_pattern"] == "DWACC[0-9][0-9][A-Z].TXT"
    assert any(node.id == "s3:path:HVR:ultracs:dwacc" for node in graph.nodes)
    assert not any(node.label in {"HVR_COLUMN", "HVR_PARAM_FILE"} for node in graph.nodes)


def test_dbt_model_and_relation_identity_and_multiline_schema_are_preserved():
    graph = parse_dbt_project(FIXTURES / "dbt")
    models = {node.id: node for node in graph.nodes}
    assert models["dbt:model:sample_internal"].properties["description"] == "Māori account evidence\nremains multiline.\n"
    assert models["snowflake:relation:INTERNAL.SAMPLE_INTERNAL"].properties["kind"] == "TABLE"
    assert models["snowflake:relation:PUBLIC.SAMPLE_PUBLIC"].properties["kind"] == "VIEW"
    assert any(edge.source == "dbt:model:sample_public" and edge.target == "dbt:model:sample_internal" and edge.type == "DEPENDS_ON" for edge in graph.edges)
    assert any(edge.source == "dbt:source:fixture_raw.ACCOUNTS" and edge.target == "snowflake:relation:RAW.ACCOUNTS" and edge.type == "RESOLVES_TO" for edge in graph.edges)


def test_dbt_column_expressions_keep_exact_keys_and_direct_public_projection():
    projections = _dbt_data_projections(FIXTURES / "dbt" / "models" / "internal" / "sample_internal.sql")
    assert projections == [{"source_column": "KiwiAcc", "target_column": "ACCOUNTNUMBER", "source_expression": "DATA:KiwiAcc::VARCHAR(100) AS ACCOUNTNUMBER", "source_line": 2}]
    public = _selected_sql_projections(FIXTURES / "dbt" / "models" / "public" / "sample_public.sql")
    assert set(public) == {"ACCOUNTNUMBER"}

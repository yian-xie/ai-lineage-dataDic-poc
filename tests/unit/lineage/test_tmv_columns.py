from pathlib import Path

from lineage_poc.columns.tmv import build_column_inventory


def graph_for_account_projection(source_name="raw_accounts", source_table="RAW_ACCOUNTS"):
    source_id = "dbt:source:landing:account-v1:raw.raw_accounts"
    source_relation = "snowflake:relation:RAW.RAW_ACCOUNTS"
    model_id = "dbt:model:landing:account-v1:account_model"
    target_relation = "snowflake:relation:INTERNAL.ACCOUNT_MODEL"
    nodes = [
        {"id": source_id, "type": "DBT_SOURCE", "properties": {
            "project": "account-v1", "source_name": "raw", "name": source_name,
        }},
        {"id": source_relation, "type": "SNOWFLAKE_RELATION", "properties": {"name": f"RAW.{source_table}"}},
        {"id": model_id, "type": "DBT_MODEL", "properties": {
            "project": "account-v1", "name": "account_model",
            "source_path": "products/account-v1/dbt/models/account_model.sql",
        }},
        {"id": target_relation, "type": "SNOWFLAKE_RELATION", "properties": {"name": "INTERNAL.ACCOUNT_MODEL"}},
    ]
    edges = [
        {"source": source_id, "target": source_relation, "type": "RESOLVES_TO", "properties": {}},
        {"source": model_id, "target": source_id, "type": "DEPENDS_ON", "properties": {}},
        {"source": model_id, "target": target_relation, "type": "MATERIALIZES_AS", "properties": {}},
    ]
    return {"nodes": nodes, "edges": edges}


def test_tmv_columns_traces_explicit_sql_projection_to_declared_relation(tmp_path):
    root = tmp_path / "evidence"
    sql_path = root / "kb-cdp-tenant-landing" / "products/account-v1/dbt/models/account_model.sql"
    sql_path.parent.mkdir(parents=True)
    sql_path.write_text(
        "SELECT CAST(RAW.ACCOUNT_NUMBER AS VARCHAR) AS ACCOUNT_NUMBER "
        "FROM {{ source('raw', 'raw_accounts') }} AS RAW\n",
        encoding="utf-8",
    )
    graph = graph_for_account_projection()

    records, gaps = build_column_inventory(
        {"landing": graph, "protect_downstream": {"nodes": [], "edges": []}},
        root,
        "sha256:test-snapshot",
    )

    assert len(records) == 1
    assert records[0]["source_relation_id"] == "snowflake:relation:RAW.RAW_ACCOUNTS"
    assert records[0]["source_column"] == "ACCOUNT_NUMBER"
    assert records[0]["target_relation_id"] == "snowflake:relation:INTERNAL.ACCOUNT_MODEL"
    assert records[0]["target_column"] == "ACCOUNT_NUMBER"
    assert records[0]["confidence"] == "explicit"
    assert gaps == []


def test_tmv_columns_records_unknown_source_macro_as_gap(tmp_path):
    root = tmp_path / "evidence"
    sql_path = root / "kb-cdp-tenant-landing" / "products/account-v1/dbt/models/account_model.sql"
    sql_path.parent.mkdir(parents=True)
    sql_path.write_text(
        "SELECT UNKNOWN.ACCOUNT_NUMBER AS ACCOUNT_NUMBER "
        "FROM {{ source('missing_source', 'missing_table') }} AS UNKNOWN\n",
        encoding="utf-8",
    )

    records, gaps = build_column_inventory(
        {"landing": graph_for_account_projection(), "protect_downstream": {"nodes": [], "edges": []}},
        root,
        "sha256:test-snapshot",
    )

    assert records == []
    assert gaps[0]["reason"].startswith("unresolved_dbt_reference:")
    assert gaps[0]["source_path"].endswith("account_model.sql")


def test_tmv_union_constants_are_not_source_columns_and_branch_expression_is_preserved(tmp_path):
    root = tmp_path / "evidence"
    path = root / "kb-cdp-tenant-landing/products/account-v1/dbt/models/account_model.sql"
    path.parent.mkdir(parents=True)
    path.write_text(
        "SELECT NULL AS ACCOUNT_NUMBER FROM {{ source('raw', 'raw_accounts') }} A "
        "UNION ALL SELECT B.REAL_NUMBER AS ACCOUNT_NUMBER "
        "FROM {{ source('raw', 'raw_accounts') }} B",
        encoding="utf-8",
    )
    records, gaps = build_column_inventory(
        {"landing": graph_for_account_projection(), "protect_downstream": {"nodes": [], "edges": []}},
        root, "sha256:test",
    )
    assert len(records) == 1
    assert records[0]["source_column"] == "REAL_NUMBER"
    assert "REAL_NUMBER" in records[0]["transformation_expression"]
    assert "NULL" not in records[0]["transformation_expression"]
    assert any(gap["reason"] == "constant_or_unresolved_expression_has_no_source_column" for gap in gaps)


def test_sqlglot_untraceable_projection_is_a_gap_not_a_failed_stage(tmp_path, monkeypatch):
    import sqlglot
    import lineage_poc.columns.tmv as module
    path = tmp_path / "kb-cdp-tenant-landing/products/account-v1/dbt/models/account_model.sql"
    path.parent.mkdir(parents=True)
    path.write_text("SELECT A.ACCOUNT_NUMBER FROM {{ source('raw', 'raw_accounts') }} A", encoding="utf-8")
    def unsupported(*args, **kwargs):
        raise sqlglot.errors.SqlglotError("Cannot find projected column in query")
    monkeypatch.setattr(module, "lineage", unsupported)
    records, gaps = build_column_inventory({"landing": graph_for_account_projection()}, tmp_path, "sha256:test")
    assert records == []
    assert gaps[0]["reason"] == "column_lineage_requires_unavailable_schema_or_unsupported_sql"
    assert "Cannot find" in gaps[0]["detail"]
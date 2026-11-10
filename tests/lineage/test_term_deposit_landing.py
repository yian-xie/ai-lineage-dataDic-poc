from lineage_poc.graph.term_deposit_landing import (
    build_term_deposit_landing_slice,
    build_term_deposit_landing_view_config,
    render_term_deposit_landing_html,
)
import json
import re


def _node(identifier, node_type, name, source_path, **properties):
    return {"id": identifier, "type": node_type, "properties": {"name": name, "source_path": source_path, **properties}}


def _field(position, name):
    return {
        "field_id": f"ultracs:ACCOUNT:DWTDS:{position}",
        "business_field": name,
        "param_column": name,
        "ultracs_position": position,
        "extract_file": "DWTDS.TXT",
        "ultracs_program": "kb-ultracs-datawarehouse/KWDW_TDS",
        "source_path": "kb-cdp-hvr/hvr-config/scripts/DWTDS.param",
        "confidence": "inferred",
        "notes": "Positional BASIC-to-HVR association.",
        "ultracs": {
            "source_path": "kb-ultracs-datawarehouse/KWDW_TDS",
            "basic_expression": f"SOURCE_{position}",
            "source_locator": f"SOURCE_{position}",
        },
    }


def _landing_graph():
    product = "cdp:product:landing:ultracs-v1"
    source = "dbt:source:landing:ultracs-v1:ultracs_landing.termdeposits_ingest"
    source_relation = "snowflake:relation:{{ TARGET.DATABASE }}.ULTRACS_RAW.TERMDEPOSITS_INGEST"
    raw_model = "dbt:model:landing:ultracs-v1:termdeposits_raw"
    raw_relation = "snowflake:relation:ULTRACS_INTERNAL.TERMDEPOSITS_RAW"
    delta_model = "dbt:model:landing:ultracs-v1:termdeposits_delta"
    delta_relation = "snowflake:relation:ULTRACS_INTERNAL.TERMDEPOSITS_DELTA"
    history_model = "dbt:model:landing:ultracs-v1:termdeposits_history"
    history_relation = "snowflake:relation:ULTRACS_INTERNAL.TERMDEPOSITS_HISTORY"
    public_model = "dbt:model:landing:ultracs-v1:termdeposits"
    public_relation = "snowflake:relation:ULTRACS_PUBLIC.TERMDEPOSITS"
    nodes = [
        _node(product, "CDP_PRODUCT", "ultracs-v1", "products/ultracs-v1/dbt/dbt_project.yml"),
        _node(source, "DBT_SOURCE", "termdeposits_ingest", "products/ultracs-v1/dbt/models/source.yml", project="ultracs-v1", source_name="ultracs_landing", schema="ULTRACS_RAW", database="{{ target.database }}"),
        _node(source_relation, "SNOWFLAKE_RELATION", "{{ TARGET.DATABASE }}.ULTRACS_RAW.TERMDEPOSITS_INGEST", "products/ultracs-v1/dbt/models/source.yml", layer="landing"),
        _node(raw_model, "DBT_MODEL", "termdeposits_raw", "products/ultracs-v1/dbt/models/internal/termdeposits_raw/termdeposits_raw.sql", project="ultracs-v1", layer="internal", schema="ULTRACS_INTERNAL"),
        _node(raw_relation, "SNOWFLAKE_RELATION", "ULTRACS_INTERNAL.TERMDEPOSITS_RAW", "products/ultracs-v1/dbt/models/internal/termdeposits_raw/termdeposits_raw.sql", layer="internal"),
        _node(delta_model, "DBT_MODEL", "termdeposits_delta", "products/ultracs-v1/dbt/models/internal/termdeposits_delta/termdeposits_delta.sql", project="ultracs-v1", layer="internal", schema="ULTRACS_INTERNAL"),
        _node(delta_relation, "SNOWFLAKE_RELATION", "ULTRACS_INTERNAL.TERMDEPOSITS_DELTA", "products/ultracs-v1/dbt/models/internal/termdeposits_delta/termdeposits_delta.sql", layer="internal"),
        _node(history_model, "DBT_MODEL", "termdeposits_history", "products/ultracs-v1/dbt/models/internal/termdeposits_history/termdeposits_history.sql", project="ultracs-v1", layer="internal", schema="ULTRACS_INTERNAL"),
        _node(history_relation, "SNOWFLAKE_RELATION", "ULTRACS_INTERNAL.TERMDEPOSITS_HISTORY", "products/ultracs-v1/dbt/models/internal/termdeposits_history/termdeposits_history.sql", layer="internal"),
        _node(public_model, "DBT_MODEL", "termdeposits", "products/ultracs-v1/dbt/models/public/termdeposits/termdeposits.sql", project="ultracs-v1", layer="public", schema="ULTRACS_PUBLIC"),
        _node(public_relation, "SNOWFLAKE_RELATION", "ULTRACS_PUBLIC.TERMDEPOSITS", "products/ultracs-v1/dbt/models/public/termdeposits/termdeposits.sql", layer="public"),
    ]
    edges = [
        {"source": product, "target": raw_model, "type": "CONTAINS", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/dbt_project.yml"}},
        {"source": source, "target": source_relation, "type": "RESOLVES_TO", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/source.yml"}},
        {"source": raw_model, "target": source, "type": "DEPENDS_ON", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/internal/termdeposits_raw/termdeposits_raw.sql"}},
        {"source": raw_model, "target": raw_relation, "type": "MATERIALIZES_AS", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/internal/termdeposits_raw/termdeposits_raw.sql"}},
        {"source": delta_model, "target": raw_model, "type": "DEPENDS_ON", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/internal/termdeposits_delta/termdeposits_delta.sql"}},
        {"source": delta_model, "target": delta_relation, "type": "MATERIALIZES_AS", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/internal/termdeposits_delta/termdeposits_delta.sql"}},
        {"source": history_model, "target": delta_model, "type": "DEPENDS_ON", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/internal/termdeposits_history/termdeposits_history.sql"}},
        {"source": history_model, "target": history_relation, "type": "MATERIALIZES_AS", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/internal/termdeposits_history/termdeposits_history.sql"}},
        {"source": public_model, "target": history_model, "type": "DEPENDS_ON", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/public/termdeposits/termdeposits.sql"}},
        {"source": public_model, "target": public_relation, "type": "MATERIALIZES_AS", "properties": {"confidence": "explicit", "source_path": "products/ultracs-v1/dbt/models/public/termdeposits/termdeposits.sql"}},
    ]
    return {"nodes": nodes, "edges": edges}


def _hvr_graph():
    program = "program:KWDW_TDS"
    extract = "extract:DWTDS.TXT"
    channel = "hvr:channel:ult_sf_tdst"
    location = "hvr:location:sf_lnd_ultra"
    relation = "snowflake:relation:TERMDEPOSITS_INGEST"
    nodes = [
        _node("basic:file:TRAN", "MV_FILE", "TRAN", "kb-ultracs-datawarehouse/DATAMASK"),
        _node(program, "PROGRAM", "KWDW_TDS", "kb-ultracs-datawarehouse/KWDW_TDS"),
        _node(extract, "EXTRACT_FILE", "DWTDS.TXT", "kb-ultracs-datawarehouse/KWDW_TDS"),
        _node(channel, "HVR_CHANNEL", "ult_sf_tdst", "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_tdst.json"),
        _node(location, "HVR_LOCATION", "sf_lnd_ultra", "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_tdst.json"),
        _node(relation, "SNOWFLAKE_RELATION", "termdeposits_ingest", "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_tdst.json", layer="landing", creation_mechanism="HVR"),
    ]
    edges = [
        {"source": program, "target": "basic:file:TRAN", "type": "READS_FROM", "properties": {"confidence": "explicit", "source_path": "kb-ultracs-datawarehouse/KWDW_TDS"}},
        {"source": program, "target": extract, "type": "WRITES_TO", "properties": {"confidence": "explicit", "source_path": "kb-ultracs-datawarehouse/KWDW_TDS"}},
        {"source": extract, "target": channel, "type": "CARRIED_BY", "properties": {"confidence": "explicit", "source_path": "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_tdst.json"}},
        {"source": channel, "target": location, "type": "INTEGRATES_TO", "properties": {"confidence": "explicit", "source_path": "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_tdst.json"}},
        {"source": channel, "target": relation, "type": "LANDS_IN", "properties": {"confidence": "explicit", "source_path": "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_tdst.json"}},
    ]
    return {"nodes": nodes, "edges": edges}


def test_term_deposit_landing_graph_uses_parser_scope_and_keeps_relation_candidate(tmp_path):
    raw_dir = tmp_path / "products/ultracs-v1/dbt/models/internal/termdeposits_raw"
    raw_dir.mkdir(parents=True)
    sql_lines = [
        f"    CAST(NULLIF(TRIM(SPLIT_PART(PAYLOAD, '|', {position})), '') AS VARCHAR) AS FIELD{position:02d},"
        for position in range(1, 42)
    ]
    (raw_dir / "termdeposits_raw.sql").write_text("SELECT\n" + "\n".join(sql_lines) + "\nFROM source", encoding="utf-8")
    yaml_columns = "\n".join(
        f"      - name: FIELD{position:02d}\n        data_type: VARCHAR\n        description: Field {position}\n        meta:\n          CLASSIFICATION: SENSITIVE"
        for position in range(1, 42)
    )
    (raw_dir / "termdeposits_raw.yml").write_text(
        "version: 1\nmodels:\n  - name: termdeposits_raw\n    columns:\n" + yaml_columns + "\n",
        encoding="utf-8",
    )
    records = [_field(position, f"Field{position:02d}") for position in range(1, 43)]

    graph, mapped_records = build_term_deposit_landing_slice(
        _hvr_graph(), _landing_graph(), records, tmp_path / "products/ultracs-v1",
    )
    candidate = graph["candidate_links"][0]
    config = build_term_deposit_landing_view_config(graph, mapped_records, candidate)
    page = render_term_deposit_landing_html(graph, mapped_records, candidate)
    ids = {node["id"] for node in graph["nodes"]}
    table_match = re.search(r'<script id="table-data" type="application/json">(.*?)</script>', page)
    feed_match = re.search(r'<script id="feed-config" type="application/json">(.*?)</script>', page)
    assert table_match and feed_match
    embedded_graph = json.loads(table_match.group(1))
    embedded_config = json.loads(feed_match.group(1))

    assert graph["summary"]["ultracs_positions"] == 42
    assert graph["summary"]["landing_columns_mapped"] == 41
    assert graph["summary"]["landing_columns_unmapped"] == 1
    assert candidate["confidence"] == "inferred"
    assert candidate["from"] == "snowflake:relation:TERMDEPOSITS_INGEST"
    assert (candidate["from"], "CANDIDATE_PHYSICAL_IDENTITY", candidate["to"]) not in {
        (edge["source"], edge["type"], edge["target"]) for edge in graph["edges"]
    }
    assert mapped_records[14]["dbt_targets"][0]["column"] == "FIELD15"
    assert mapped_records[41]["dbt_targets"] == []
    assert all("account" not in identifier.casefold() and "enterprise" not in identifier.casefold() for identifier in ids)
    assert config["columnMappingSourceNodeId"] == candidate["from"]
    assert config["targetLabel"] == "Tenant Landing"
    assert all(repository["name"] != "kb-cdp-tenant-enterprise" for repository in config["schemaRepositories"])
    assert "Tenant Landing" in page
    assert candidate["type"] in page
    assert {"from": candidate["from"], "to": candidate["to"]} in [
        {"from": item["from"], "to": item["to"]}
        for item in embedded_config["candidateLinks"]
    ]
    assert not any("accounts_v1" in node["id"].casefold() for node in embedded_graph["nodes"])
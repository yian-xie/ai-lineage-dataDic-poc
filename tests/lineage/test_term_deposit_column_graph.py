from lineage_poc.columns.term_deposit_graph import build_term_deposit_column_graph
from lineage_poc.viewers.graph.term_deposit_columns import render_term_deposit_column_graph


def _record(position, parameter, target=None):
    record = {
        "field_id": f"ultracs:ACCOUNT:DWTDS:{position}",
        "business_field": parameter,
        "ultracs_position": position,
        "ultracs_program": "kb-ultracs-datawarehouse/KWDW_TDS",
        "extract_file": "DWTDS.TXT",
        "param_column": parameter,
        "hvr_parameter": {"name": parameter, "type": "string", "source_path": "kb-cdp-hvr/hvr-config/scripts/DWTDS.param"},
        "ultracs": {
            "source_path": "kb-ultracs-datawarehouse/KWDW_TDS",
            "source_locator": "TDREC<1,1>",
            "basic_expression": "OCONV(TDREC<1,1>,'D4')",
            "basic_source_line": 30,
        },
        "dbt_targets": [target] if target else [],
        "ingestion_route": {"raw_source": "ACCOUNTS_V1__TERM_DEPOSITS_RAW"},
        "route_evidence": ["kb-cdp-tenant-account/products/accounts-v1/airflow/accounts_v1/src/dags/accounts_v1_ingestion_v1.py"],
        "notes": "No exact dbt target is established.",
    }
    return record


def test_term_deposit_column_graph_keeps_mapped_and_unmapped_fields_and_confidence():
    target = {
        "stage": "internal",
        "model": "accounts_v1__term_deposits_v1",
        "relation": "snowflake:relation:INTERNAL.ACCOUNTS_V1__TERM_DEPOSITS_V1",
        "column": "ACCOUNTNUMBER",
        "data_type": "VARCHAR",
        "source_expression": "DATA:Accounts::STRING AS ACCOUNTNUMBER,",
        "source_line": 116,
        "source_path": "kb-cdp-tenant-account/products/accounts-v1/dbt/models/internal/accounts_v1__term_deposits_v1.sql",
    }
    graph = build_term_deposit_column_graph([_record(1, "Accounts", target), _record(2, "col40")])

    assert graph["summary"]["columns"] == 2
    assert graph["summary"]["mapped_columns"] == 1
    assert graph["summary"]["unmapped_columns"] == 1
    assert len(graph["gap_register"]) == 1
    assert all(edge["source"] in {node["id"] for node in graph["nodes"]} for edge in graph["edges"])
    assert all(edge["target"] in {node["id"] for node in graph["nodes"]} for edge in graph["edges"])
    assert all(
        edge["properties"].get("reason")
        for edge in graph["edges"]
        if edge["properties"].get("confidence") == "inferred"
    )
    assert any(edge["type"] == "PROJECTS_TO" and edge["properties"]["confidence"] == "explicit" for edge in graph["edges"])


def test_term_deposit_column_graph_reads_quoted_dbt_data_keys():
    target = {
        "stage": "internal",
        "model": "accounts_v1__term_deposits_v1",
        "relation": "snowflake:relation:INTERNAL.ACCOUNTS_V1__TERM_DEPOSITS_V1",
        "column": "THIRDPARTYCHEQUEDETAILS",
        "data_type": "VARCHAR",
        "source_expression": 'DATA:"3rdPartyChqDetails"::STRING AS THIRDPARTYCHEQUEDETAILS,',
        "source_line": 131,
        "source_path": "kb-cdp-tenant-account/products/accounts-v1/dbt/models/internal/accounts_v1__term_deposits_v1.sql",
    }
    graph = build_term_deposit_column_graph([_record(17, "3rdPartyChqDetails", target)])

    assert graph["summary"]["mapped_columns"] == 1
    assert graph["summary"]["gaps"] == 0
    raw_column = next(node for node in graph["nodes"] if node["properties"]["layer"] == "landing")
    assert raw_column["properties"]["name"] == "3rdPartyChqDetails"


def test_term_deposit_column_graph_renders_a_self_contained_html_view():
    graph = build_term_deposit_column_graph([_record(2, "col40")])

    page = render_term_deposit_column_graph(graph)

    assert "Term Deposit Column Lineage" in page
    assert "__GRAPH_DATA__" not in page
    assert "lineage-data" in page
    assert "data-filter=\"gaps\"" in page
    assert "column lineage graph" in page
from lineage_poc.parsers.tmv_account import slice_landing_account, slice_protect_account


def test_account_slice_retains_dependencies_but_not_unrelated_models():
    def node(identity, kind, name):
        return {"id": identity, "type": kind, "properties": {"name": name, "source_path": "products/ultracs-v1/dbt/models/public/" + name + ".sql"}}
    nodes = [node("account", "DBT_MODEL", "accounts"), node("lookup", "DBT_MODEL", "required_lookup"),
             node("source", "DBT_SOURCE", "raw"), node("relation", "SNOWFLAKE_RELATION", "RAW.INPUT"),
             node("unrelated", "DBT_MODEL", "generalledgerlist")]
    edges = [
        {"source": "account", "target": "lookup", "type": "DEPENDS_ON", "properties": {}},
        {"source": "lookup", "target": "source", "type": "DEPENDS_ON", "properties": {}},
        {"source": "source", "target": "relation", "type": "RESOLVES_TO", "properties": {}},
    ]
    result = slice_landing_account({"nodes": nodes, "edges": edges})
    assert {node["id"] for node in result["nodes"]} == {"account", "lookup", "source", "relation"}
    assert len(result["edges"]) == 3
    assert result["account_scope"]["scope"] == "Account"


def test_protect_account_slice_excludes_unused_source_declarations():
    graph = {"nodes": [
        {"id": "model", "type": "DBT_MODEL", "properties": {"name": "account"}},
        {"id": "used", "type": "DBT_SOURCE", "properties": {}},
        {"id": "unused", "type": "DBT_SOURCE", "properties": {}},
        {"id": "relation", "type": "SNOWFLAKE_RELATION", "properties": {}},
        {"id": "unrelated", "type": "SNOWFLAKE_RELATION", "properties": {}},
    ], "edges": [
        {"source": "model", "target": "used", "type": "DEPENDS_ON", "properties": {}},
        {"source": "used", "target": "relation", "type": "RESOLVES_TO", "properties": {}},
        {"source": "unused", "target": "unrelated", "type": "RESOLVES_TO", "properties": {}},
    ]}
    result = slice_protect_account(graph)
    assert {node["id"] for node in result["nodes"]} == {"model", "used", "relation"}
from lineage_poc.graph.tmv import compose_tmv_graphs


def graph(repository, relation_id):
    product = f"product:{repository}"
    relation = {"id": relation_id, "type": "SNOWFLAKE_RELATION", "properties": {"name": relation_id}}
    node = {"id": product, "type": "CDP_PRODUCT", "properties": {"name": repository}}
    edge = {"source": product, "target": relation_id, "type": "CONTAINS", "properties": {}}
    return {"nodes": [node, relation], "edges": [edge]}


def test_tmv_union_records_missing_repo_bridges_without_synthetic_edges():
    landing = graph("landing", "snowflake:relation:LANDING.ACCOUNT")
    protect = graph("protect", "snowflake:relation:PROTECT.ACCOUNT")
    accounts = {
        "nodes": [{"id": "dotnet:project:one", "type": "DOTNET_PROJECT", "properties": {}}],
        "edges": [],
    }

    combined = compose_tmv_graphs(landing, protect, accounts)

    assert len(combined["nodes"]) == 5
    assert len(combined["edges"]) == 2
    assert combined["shared_physical_relation_ids"] == []
    assert {gap["id"] for gap in combined["gap_register"]} == {
        "landing-protect-physical-relation-bridge",
        "kb-accounts-data-bridge",
    }
    assert all(not gap["cross_repository_edge_created"] for gap in combined["gap_register"])


def test_tmv_union_recognizes_only_identical_physical_relation_ids():
    landing = graph("landing", "snowflake:relation:RAW.ACCOUNT")
    protect = graph("protect", "snowflake:relation:RAW.ACCOUNT")

    combined = compose_tmv_graphs(landing, protect)

    assert combined["shared_physical_relation_ids"] == ["snowflake:relation:RAW.ACCOUNT"]
    assert not combined["gap_register"]
    assert len(combined["nodes"]) == 3
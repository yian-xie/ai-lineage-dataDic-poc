import json
from pathlib import Path

from lineage_poc.cross_repository import build_cdp_account_crosswalk


def test_crosswalk_requires_schema_path_and_exact_raw_extraction(tmp_path):
    schema_dir = tmp_path / "kb-accounts/topic-definitions/schemas"
    schema_dir.mkdir(parents=True)
    (schema_dir / "AccountProfile.g.json").write_text(json.dumps({
        "title": "AccountProfileEvent",
        "definitions": {
            "data": {"properties": {"afterState": {"$ref": "#/definitions/account"}}},
            "account": {"properties": {"accountId": {"type": "string"}}},
        },
        "properties": {"data": {"$ref": "#/definitions/data"}},
    }), encoding="utf-8")
    source_sql = tmp_path / "kb-cdp-tenant-account/products/account-profile-topic-v1/models/profile.sql"
    source_sql.parent.mkdir(parents=True)
    source_sql.write_text("SELECT GET_PATH(src.data, 'data.afterState.accountId') AS ACCOUNTID FROM raw", encoding="utf-8")
    event_mapping = {"field_id": "event-map-1", "repository": "kb-accounts", "source_relation_id": "entity-1",
        "source_relation": "AccountProfile", "source_column": "AccountId", "target_model": "Api.Shared.Clients.Events.Kiwibank.V1.AccountProfile.Account",
        "target_column": "AccountId", "source_path": "src/ProfileBuilder.cs"}
    raw_mapping = {"field_id": "sql-raw-1", "repository": "kb-cdp-tenant-account", "project": "account-profile-topic-v1",
        "source_relation": "RAW.ACCOUNT_PROFILE_TOPIC_V1__RAW", "source_relation_id": "raw-1", "source_column": "DATA",
        "target_relation": "INTERNAL.ACCOUNT_PROFILE", "target_relation_id": "internal-1", "target_column": "ACCOUNTID",
        "transformation_expression": "GET_PATH(src.data, 'data.afterState.accountId') AS ACCOUNTID",
        "source_path": "products/account-profile-topic-v1/models/profile.sql"}
    public_mapping = {"field_id": "sql-pub-1", "repository": "kb-cdp-tenant-account", "project": "account-profile-topic-v1",
        "source_relation": "INTERNAL.ACCOUNT_PROFILE", "source_relation_id": "internal-1", "source_column": "ACCOUNTID",
        "target_relation": "PUBLIC.ACCOUNT_PROFILE", "target_relation_id": "public-1", "target_column": "ACCOUNTID",
        "transformation_expression": "ACCOUNTID", "source_path": "products/account-profile-topic-v1/models/public.sql"}
    schema_field = {"entity_id": "entity-1", "property": "AccountId", "relation_id": "pg-account",
        "relation": "profile.account_profile", "column": "account_id", "entity": "Account.Profile.Shared.Entities.AccountProfile"}
    result = build_cdp_account_crosswalk({"event_mappings": [event_mapping], "schema_inventory": [schema_field]}, [raw_mapping, public_mapping], tmp_path)
    assert len(result["mappings"]) == 1
    assert result["mappings"][0]["event_json_path"] == "data.afterState.accountId"
    assert result["mappings"][0]["downstream_targets"][0]["relation_id"] == "public-1"
    assert result["mappings"][0]["source_database_relation"] == "profile.account_profile"
    assert result["mappings"][0]["transport_status"] == "unverified_secret_backed_kafka_topic"


def test_crosswalk_does_not_link_same_name_when_json_path_differs(tmp_path):
    schema_dir = tmp_path / "kb-accounts/topic-definitions/schemas"
    schema_dir.mkdir(parents=True)
    (schema_dir / "AccountProfile.g.json").write_text(json.dumps({
        "title": "AccountProfileEvent", "definitions": {
            "data": {"properties": {"afterState": {"$ref": "#/definitions/account"}}},
            "account": {"properties": {"accountId": {"type": "string"}}},
        }, "properties": {"data": {"$ref": "#/definitions/data"}},
    }), encoding="utf-8")
    mapping = {"field_id": "event-map", "repository": "kb-accounts", "source_relation_id": "entity",
        "source_relation": "AccountProfile", "source_column": "AccountId", "target_model": "Api.Shared.Clients.Events.Kiwibank.V1.AccountProfile.Account",
        "target_column": "AccountId", "source_path": "ProfileBuilder.cs"}
    sql = {"field_id": "sql", "repository": "kb-cdp-tenant-account", "project": "account-profile-topic-v1",
        "source_relation": "RAW.ACCOUNT_PROFILE_TOPIC_V1__RAW", "source_relation_id": "raw", "source_column": "DATA",
        "target_relation": "INTERNAL.ACCOUNT_PROFILE", "target_relation_id": "internal", "target_column": "ACCOUNTID",
        "transformation_expression": "GET_PATH(src.data, 'data.afterState.customerId') AS ACCOUNTID",
        "source_path": "products/account-profile-topic-v1/models/profile.sql"}
    result = build_cdp_account_crosswalk({"event_mappings": [mapping]}, [sql], tmp_path)
    assert not result["mappings"]
    assert result["unresolved"][0]["reason"] == "event_schema_path_not_extracted_by_selected_raw_sql"


def test_account_opening_id_route_keeps_external_boundaries_unverified(tmp_path):
    schema = {"entity_id": "origination-entity", "property": "AccountId", "relation_id": "origination-table",
        "relation": "origination.account_opening", "column": "account_id", "entity": "Account.Origination.Shared.Entities.AccountOpening"}
    result = build_cdp_account_crosswalk({"event_mappings": [], "schema_inventory": [schema]}, [], tmp_path)
    route = result["candidate_routes"][0]
    assert route["source_column"] == "account_id"
    assert [hop["status"] for hop in route["hops"]] == ["source_declared", "external_service_continuity_unverified", "topic_secret_binding_unverified"]

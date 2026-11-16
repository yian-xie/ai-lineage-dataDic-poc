from lineage_poc.account_scope import select_account_evidence


def test_select_account_evidence_keeps_account_profile_and_balance_only():
    crosswalk = {
        "mappings": [
            {"mapping_id": "profile-map", "raw_sql_mapping_id": "profile-sql",
             "consumer_product": "account-profile-topic-v1", "source_database_relation_id": "profile.account_profile",
             "event_contract": "AccountProfile.Account"},
            {"mapping_id": "balance-map", "raw_sql_mapping_id": "balance-sql",
             "consumer_product": "ads-eod-customeraccount-topic-v1", "source_database_relation_id": "transaction.account_balance",
             "event_contract": "AccountBalance.AccountBalances"},
            {"mapping_id": "transaction-map", "raw_sql_mapping_id": "transaction-sql",
             "consumer_product": "ads-transaction-topic-v1", "source_database_relation_id": "transaction.account_transaction",
             "event_contract": "AccountTransaction.AccountTransaction"},
        ],
        "table_mappings": [
            {"consumer_product": "account-profile-topic-v1", "source_table_id": "profile.account_profile",
             "mapping_ids": ["profile-map"]},
            {"consumer_product": "ads-eod-customeraccount-topic-v1", "source_table_id": "transaction.account_balance",
             "mapping_ids": ["balance-map"]},
            {"consumer_product": "ads-transaction-topic-v1", "source_table_id": "transaction.account_transaction",
             "mapping_ids": ["transaction-map"]},
        ],
        "unresolved": [
            {"consumer_product": "account-profile-topic-v1", "event_contract": "AccountProfile.Account"},
            {"consumer_product": "ads-transaction-topic-v1", "event_contract": "AccountTransaction.AccountTransaction"},
        ],
        "candidate_routes": [
            {"route": "AccountProfile.Account to AccountProfile"},
            {"route": "AccountTransaction to transaction"},
        ],
    }
    records = [
        {"field_id": "profile-sql", "mapping_kind": "sql_projection"},
        {"field_id": "balance-sql", "mapping_kind": "sql_projection"},
        {"field_id": "transaction-sql", "mapping_kind": "sql_projection"},
        {"field_id": "profile-ef", "mapping_kind": "ef_property_binding",
         "target_relation_id": "profile.account_profile"},
        {"field_id": "profile-event", "mapping_kind": "csharp_event_assignment",
         "target_relation": "AccountProfile.Account"},
        {"field_id": "transaction-event", "mapping_kind": "csharp_event_assignment",
         "target_relation": "AccountTransaction.AccountTransaction"},
    ]

    selected, scoped = select_account_evidence(records, crosswalk)

    assert {row["field_id"] for row in selected} == {"profile-sql", "balance-sql", "profile-ef", "profile-event"}
    assert {row["mapping_id"] for row in scoped["mappings"]} == {"profile-map", "balance-map"}
    assert len(scoped["table_mappings"]) == 2
    assert len(scoped["unresolved"]) == 1
    assert len(scoped["candidate_routes"]) == 1
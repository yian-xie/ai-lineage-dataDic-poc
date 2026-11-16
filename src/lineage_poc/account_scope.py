"""Account-only projection of the two-repository CDP Account evidence."""

from __future__ import annotations


ACCOUNT_PRODUCTS = frozenset({"account-profile-topic-v1", "ads-eod-customeraccount-topic-v1"})
ACCOUNT_MAPPING_KINDS = frozenset({"ef_property_binding", "ef_json_document_binding"})


def select_account_evidence(records: list[dict], crosswalk: dict) -> tuple[list[dict], dict]:
    mappings = [item for item in crosswalk.get("mappings", [])
                if item.get("consumer_product") in ACCOUNT_PRODUCTS]
    mapping_ids = {item["mapping_id"] for item in mappings}
    raw_mapping_ids = {item["raw_sql_mapping_id"] for item in mappings}
    source_relations = {item["source_database_relation_id"] for item in mappings}
    event_contracts = {item["event_contract"] for item in mappings}
    selected_records = [record for record in records if (
        record.get("field_id") in raw_mapping_ids
        or record.get("mapping_kind") == "csharp_event_assignment"
        and record.get("target_relation") in event_contracts
        or record.get("mapping_kind") in ACCOUNT_MAPPING_KINDS
        and record.get("target_relation_id") in source_relations
    )]
    selected_raw_ids = {record["field_id"] for record in selected_records
                        if record.get("field_id") in raw_mapping_ids}
    if selected_raw_ids != raw_mapping_ids:
        raise ValueError("Account crosswalk references missing column mappings")

    result = dict(crosswalk)
    result["scope"] = "Account Profile and End-of-Day Account Balance field crosswalk"
    result["mappings"] = mappings
    result["table_mappings"] = [item for item in crosswalk.get("table_mappings", [])
                                if item.get("consumer_product") in ACCOUNT_PRODUCTS
                                and source_relations.intersection({item.get("source_table_id")})
                                and mapping_ids.intersection(item.get("mapping_ids", []))]
    result["unresolved"] = [item for item in crosswalk.get("unresolved", [])
                            if item.get("consumer_product") in ACCOUNT_PRODUCTS
                            or item.get("event_contract") in event_contracts]
    result["candidate_routes"] = [item for item in crosswalk.get("candidate_routes", [])
                                  if any(token in str(item) for token in (
                                      "AccountProfile", "AccountBalanceEndOfDayCustomerAccount"))]
    result["counts"] = {
        "field_mappings": len(result["mappings"]),
        "table_mappings": len(result["table_mappings"]),
        "unresolved": len(result["unresolved"]),
        "candidate_routes": len(result["candidate_routes"]),
        "column_records": len(selected_records),
    }
    return selected_records, result
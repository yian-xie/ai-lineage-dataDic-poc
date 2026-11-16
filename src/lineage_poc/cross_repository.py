"""Evidence-backed field crosswalks between kb-accounts events and CDP Account DBT."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


EVENT_PRODUCTS = {
    "AccountProfile": "account-profile-topic-v1",
    "AccountTransaction": "ads-transaction-topic-v1",
    "AccountBalanceEndOfDayCustomerAccount": "ads-eod-customeraccount-topic-v1",
    "AccountBalanceEndOfDayInternalAccount": "ads-eod-internalaccount-topic-v1",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _ref_name(schema: dict) -> str | None:
    reference = schema.get("$ref")
    return reference.rsplit("/", 1)[-1] if reference else None


def _resolve(schema: dict, definitions: dict) -> tuple[str | None, dict]:
    name = _ref_name(schema)
    return (name, definitions[name]) if name in definitions else (name, schema)


def _object_for_type(root_schema: dict, definitions: dict, type_name: str) -> tuple[list[str], dict] | None:
    data_def = definitions.get(_ref_name(root_schema.get("properties", {}).get("data", {})), {})
    after_schema = data_def.get("properties", {}).get("afterState", {})
    after_name, after_object = _resolve(after_schema, definitions)
    wanted = _norm(type_name)
    if _norm(after_name or "") == wanted:
        return [], after_object

    def walk(schema: dict, path: list[str], seen: frozenset[str]):
        name, resolved = _resolve(schema, definitions)
        if name and _norm(name) == wanted:
            return path, resolved
        if name and name in seen:
            return None
        next_seen = seen | ({name} if name else set())
        if resolved.get("type") == "array":
            item = resolved.get("items", {})
            item_name = _ref_name(item)
            if item_name and _norm(item_name) == wanted:
                return path + ["[]"], definitions.get(item_name, item)
            return walk(item, path + ["[]"], frozenset(next_seen))
        for property_name, property_schema in resolved.get("properties", {}).items():
            if _norm(property_name) == wanted:
                child = property_schema
                suffix = [property_name]
                if child.get("type") == "array":
                    suffix.append("[]")
                    child = child.get("items", {})
                _, child = _resolve(child, definitions)
                return path + suffix, child
            found = walk(property_schema, path + [property_name], frozenset(next_seen))
            if found:
                return found
        return None

    return walk(after_object, [], frozenset({after_name} if after_name else set()))


def event_json_path(schema_directory: Path, contract_type: str, property_name: str) -> tuple[str | None, Path | None, str | None]:
    after_version = contract_type.split(".V1.", 1)[-1]
    parts = after_version.split(".")
    event_root, target_type = parts[0], parts[-1]
    schema_path = schema_directory / (event_root + ".g.json")
    if not schema_path.is_file():
        return None, schema_path, "event_schema_not_captured"
    document = json.loads(schema_path.read_text(encoding="utf-8"))
    definitions = document.get("definitions", document.get("$defs", {}))
    selected = _object_for_type(document, definitions, target_type)
    if not selected:
        return None, schema_path, "event_type_not_found_in_schema"
    prefix, target_schema = selected
    property_schema = next((name for name in target_schema.get("properties", {}) if _norm(name) == _norm(property_name)), None)
    if not property_schema:
        return None, schema_path, "event_property_not_found_in_schema"
    return ".".join(["data", "afterState", *prefix, property_schema]), schema_path, None


def _flatten_paths(sql: str) -> dict[str, str]:
    paths = {}
    pattern = re.compile(r"flatten\s*\([\s\S]*?path\s*=>\s*(['\"])(.*?)\1[\s\S]*?\)\s+as\s+(\w+)", re.I)
    for match in pattern.finditer(sql):
        paths[match.group(3).casefold()] = match.group(2).replace(":", ".").strip(".")
    return paths


def sql_json_paths(expression: str, sql: str) -> set[str]:
    flatten = _flatten_paths(sql)
    paths = set()
    get_path = re.compile(r"GET_PATH\s*\(\s*([\w.]+)\s*,\s*(['\"])(.*?)\2", re.I | re.S)
    for match in get_path.finditer(expression):
        source, relative = match.group(1).casefold(), match.group(3).replace(":", ".").strip(".")
        alias = source.removesuffix(".value").split(".")[-1]
        prefix = flatten.get(alias)
        if prefix and not relative.casefold().startswith("data."):
            paths.add(prefix + "[]." + relative)
        else:
            paths.add(relative)
    colon = re.compile(r"\b(\w+)\.value\s*:\s*([\w]+)", re.I)
    for match in colon.finditer(expression):
        alias, relative = match.group(1).casefold(), match.group(2)
        prefix = flatten.get(alias)
        if prefix:
            paths.add(prefix + "[]." + relative)
    return {_norm(path) for path in paths}


def build_cdp_account_crosswalk(kb_data: dict[str, Any], sql_records: list[dict], evidence_root: Path) -> dict:
    """Match EF-backed event fields to CDP Account RAW/model paths by schema and JSON path."""
    schema_dir = Path(evidence_root) / "kb-accounts/topic-definitions/schemas"
    event_mappings = kb_data.get("event_mappings", [])
    schema_fields = {(row["entity_id"], row["property"]): row for row in kb_data.get("schema_inventory", [])}
    gaps = []
    sql_by_product: dict[str, list[dict]] = defaultdict(list)
    for row in sql_records:
        sql_by_product[row["project"]].append(row)
    raw_candidates = {}
    for product, records in sql_by_product.items():
        product_rows = [row for row in records if "__RAW" in row["source_relation"].upper()]
        for row in product_rows:
            source_file = Path(evidence_root) / row["repository"] / row["source_path"]
            sql_text = source_file.read_text(encoding="utf-8", errors="replace") if source_file.is_file() else ""
            raw_candidates.setdefault(product, []).append((row, sql_text))

    mappings = []
    for event_mapping in event_mappings:
        event_type = event_mapping["target_model"]
        event_root = event_type.split(".V1.", 1)[-1].split(".", 1)[0]
        product = EVENT_PRODUCTS.get(event_root)
        if not product or product not in sql_by_product:
            gaps.append({"mapping_id": event_mapping["field_id"], "reason": "no_account_tenant_consumer_product_for_event_contract",
                         "event_contract": event_type, "source_path": event_mapping["source_path"]})
            continue
        json_path, schema_path, schema_gap = event_json_path(schema_dir, event_type, event_mapping["target_column"])
        if schema_gap:
            gaps.append({"mapping_id": event_mapping["field_id"], "reason": schema_gap, "schema_path": str(schema_path),
                         "event_contract": event_type, "event_property": event_mapping["target_column"]})
            continue
        expected = _norm(json_path)
        matches = []
        for raw_mapping, sql_text in raw_candidates.get(product, []):
            if expected in sql_json_paths(raw_mapping["transformation_expression"], sql_text):
                matches.append(raw_mapping)
        if not matches:
            gaps.append({"mapping_id": event_mapping["field_id"], "reason": "event_schema_path_not_extracted_by_selected_raw_sql",
                         "event_contract": event_type, "event_property": event_mapping["target_column"],
                         "event_json_path": json_path, "consumer_product": product})
            continue
        for raw_mapping in matches:
            source_schema = schema_fields.get((event_mapping["source_relation_id"], event_mapping["source_column"]), {})
            downstream = defaultdict(list)
            for row in sql_by_product[product]:
                downstream[(row["source_relation_id"], row["source_column"])].append(row)
            queue = [(raw_mapping["target_relation_id"], raw_mapping["target_column"], [])]
            seen = set()
            terminal = []
            while queue:
                relation_id, column, chain = queue.pop(0)
                key = (relation_id, column)
                if key in seen:
                    continue
                seen.add(key)
                next_rows = downstream.get(key, [])
                if not next_rows:
                    terminal.append({"relation_id": relation_id, "column": column, "path": chain})
                else:
                    for row in next_rows:
                        queue.append((row["target_relation_id"], row["target_column"], chain + [row["field_id"]]))
            mappings.append({"mapping_id": "cross-repo:" + event_mapping["field_id"] + ":" + raw_mapping["field_id"],
                "source_repository": "kb-accounts", "source_entity_id": event_mapping["source_relation_id"],
                "source_entity": event_mapping["source_relation"], "source_property": event_mapping["source_column"],
                "source_database_relation_id": source_schema.get("relation_id"),
                "source_database_relation": source_schema.get("relation"),
                "source_database_column": source_schema.get("column"),
                "source_database_column_id": (source_schema.get("relation_id"), source_schema.get("column")) if source_schema else None,
                "event_contract": event_type, "event_property": event_mapping["target_column"],
                "event_json_path": json_path, "consumer_repository": "kb-cdp-tenant-account", "consumer_product": product,
                "raw_relation_id": raw_mapping["target_relation_id"], "raw_relation": raw_mapping["target_relation"],
                "raw_column": raw_mapping["target_column"], "raw_sql_mapping_id": raw_mapping["field_id"],
                "raw_sql_expression": raw_mapping["transformation_expression"], "raw_sql_source_path": raw_mapping["source_path"],
                "downstream_targets": terminal, "evidence_paths": [event_mapping["source_path"], str(schema_path), raw_mapping["source_path"]],
                "field_link_status": "event_schema_and_json_path_match", "transport_status": "unverified_secret_backed_kafka_topic",
                "confidence": "explicit_static_declarations_not_runtime_verified"})
    table_index = {}
    for row in mappings:
        key = (row["source_database_relation_id"], row["raw_relation_id"])
        item = table_index.setdefault(key, {"source_repository": row["source_repository"], "source_table_id": row["source_database_relation_id"],
            "source_table": row["source_database_relation"], "consumer_repository": row["consumer_repository"],
            "consumer_product": row["consumer_product"], "raw_relation_id": row["raw_relation_id"], "raw_relation": row["raw_relation"],
            "mapping_ids": []})
        item["mapping_ids"].append(row["mapping_id"])
    origination = next((row for row in kb_data.get("schema_inventory", [])
        if row["entity"].endswith(".AccountOpening") and row["property"] == "AccountId"), None)
    opening_route = None
    if origination:
        opening_route = {"source_table": origination["relation"], "source_column": origination["column"],
            "source_entity": origination["entity"], "source_property": origination["property"],
            "hops": [
                {"kind": "api_request", "target": "TMV Account API accountId", "status": "source_declared",
                 "evidence": ["kb-accounts/src/origination/Account.Origination.Job/Services/TmvAccountAction.cs",
                              "kb-accounts/src/origination/Account.Origination.Job/TMVClient/Factories/OnlineCallAccountRequestFactory.cs"],
                 "detail": "Origination passes AccountOpening.AccountId into account get/create/open request IDs."},
                {"kind": "async_service_event", "target": "TMV AccountEvent.Account.Id -> AccountProfile.AccountId", "status": "external_service_continuity_unverified",
                 "evidence": ["kb-accounts/catalog/processors-workers.yaml",
                              "kb-accounts/src/profile/Account.Profile.Processor/Subscribers/TmvAccountEventSubscriber.cs",
                              "kb-accounts/src/profile/Account.Profile.Processor/Services/AccountProfileChangeSetCreator.cs"],
                 "detail": "The processor consumes TMV Account events and copies AccountEvent.Account.Id to the Profile change set; service-level identity continuity is not runtime verified."},
                {"kind": "profile_topic_consumer", "target": "account-profile-topic-v1 / RAW.ACCOUNT_PROFILE_TOPIC_V1__RAW", "status": "topic_secret_binding_unverified",
                 "evidence": ["kb-accounts/catalog/kafka-events.yaml",
                              "kb-accounts/src/profile/Account.Profile.Processor/Publishers/AccountProfileEventBuilder.cs",
                              "kb-cdp-tenant-account/products/account-profile-topic-v1/airflow/account_profile_topic_v1/src/dags/account_profile_topic_ingestion_v1.py",
                              "kb-cdp-tenant-account/products/account-profile-topic-v1/README.md"],
                 "detail": "The producer event contract and consumer product correspond by schema/product evidence, but the consumer topic is supplied by Secret Manager and its runtime value is absent from the source snapshot."}
            ], "status": "candidate_path_with_explicit_external_boundaries"}
    return {"scope": "kb-accounts to kb-cdp-tenant-account field crosswalk", "runtime_verified": False,
        "mappings": mappings, "table_mappings": list(table_index.values()), "candidate_routes": [opening_route] if opening_route else [], "unresolved": gaps,
        "counts": {"event_assignment_rows": len(event_mappings), "cross_repository_field_mappings": len(mappings),
            "table_mappings": len(table_index), "unresolved_event_mappings": len(gaps)},
        "limitations": ["Kafka topic names/consumer secret values are not in the repository snapshot; producer-consumer continuity is not runtime verified.",
            "Only event schema JSON paths exactly matched to SQL extraction expressions are linked.",
            "AccountOpening-to-TMV AccountEvent identity continuity crosses an external API/event service and remains unverified."]}

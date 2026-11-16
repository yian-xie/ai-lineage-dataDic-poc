"""Explicit TMV relation/column dictionary projection; no Ultracs/HVR aliases."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path

import yaml

from .io import CSV_FILES, digest_file, read_tables, require, staging_directory, commit_outputs, write_table
from lineage_poc.execution import read_json, write_json
from lineage_poc.parsers.snapshot import load_snapshot, TMV_REPOSITORIES, ACCOUNT_DOMAIN_REPOSITORIES, CDP_ACCOUNT_REPOSITORIES
from lineage_poc.dictionary.legacy_projection import uid


CONTRACT = "tmv-dictionary-v1"
COMMON = ["contract_version", "graph_id", "snapshot_id"]
ASSETS = COMMON + ["asset_id", "repository", "asset_name", "relation_id", "description", "metadata_json"]
FIELDS = COMMON + ["field_id", "asset_id", "repository", "relation_id", "field_name", "data_type",
                   "is_mapped_target", "description", "description_source_type", "description_provenance_json",
                   "metadata_json", "evidence_json", "description_generation_status",
                   "description_confidence_score_10", "description_confidence_json"]
MAPPINGS = COMMON + ["dictionary_entry_id", "repository", "project", "source_field_id", "target_field_id",
                     "source_relation", "source_column", "target_relation", "target_column",
                     "source_description", "target_description", "transformation_expression", "confidence",
                     "source_path", "original_record_pointer"]


def identity(repository, relation, column=None):
    return uid("tmv-field" if column is not None else "tmv-asset", [repository, relation, column])


def _column_metadata(evidence, repositories=TMV_REPOSITORIES):
    metadata = defaultdict(list)
    for repository in repositories:
        if repository == "kb-accounts":
            continue
        for path in sorted((evidence / repository / "products").glob("*/dbt/models/**/*.y*ml")):
            content = "\n".join(line.rstrip("\t") for line in path.read_text(encoding="utf-8").splitlines())
            document = yaml.safe_load(content) or {}
            if not isinstance(document, dict):
                continue
            product = path.relative_to(evidence / repository).parts[1]
            for model in document.get("models", []) or []:
                for column in model.get("columns", []) or []:
                    if model.get("name") and column.get("name"):
                        key = (repository, product, str(model["name"]).casefold(), str(column["name"]).upper())
                        metadata[key].append({
                            "source_path": path.relative_to(evidence).as_posix(),
                            "description": column.get("description") or "",
                            "data_type": column.get("data_type") or "",
                            "declaration": column,
                        })
    return metadata


def eligible(row):
    metadata = json.loads(row["metadata_json"])
    return (row.get("contract_version") == CONTRACT and row.get("is_mapped_target") == "true"
            and not row["description"].strip() and not metadata.get("description_conflict"))


def generate(input_path: Path, parsed: Path, graphs: Path, destination: Path):
    records = read_json(input_path)
    require(isinstance(records, list) and records, "TMV requires a nonempty column mapping array")
    parse_manifest = read_json(parsed / "manifest.json")
    profile = "cdp-account" if parse_manifest.get("parser") == "cdp-account" else "account-domain" if parse_manifest.get("parser") == "account-domain" else "tmv"
    repositories = CDP_ACCOUNT_REPOSITORIES if profile == "cdp-account" else ACCOUNT_DOMAIN_REPOSITORIES if profile == "account-domain" else TMV_REPOSITORIES
    require(all(row.get("repository") in repositories and (row.get("repository") != "kb-accounts" or profile in {"account-domain", "cdp-account"} and row.get("mapping_kind") in {"ef_property_binding", "ef_json_document_binding", "csharp_event_assignment"}) and row.get("graph_id") == "tmv_column_lineage" for row in records), "Input repository or mapping contract differs from the selected profile")
    require(parse_manifest.get("parser") in {"tmv", "tmv-account", "account-domain", "cdp-account"} and set(parse_manifest["repositories"]) == set(repositories), "Snapshot repository allowlist differs from the selected profile")
    require(read_json(graphs / "manifest.json")["parse_manifest_sha256"] == digest_file(parsed / "manifest.json"), "Graph/parse snapshots differ")
    nodes = {node["id"]: node for node in read_json(graphs / "table_lineage.json")["nodes"]}
    snapshot = "sha256:" + digest_file(input_path)
    scope = {"contract_version": CONTRACT, "graph_id": "tmv_dictionary", "snapshot_id": snapshot}
    assets, fields, source_rows, field_evidence = {}, {}, [], defaultdict(list)
    target_metadata = defaultdict(list)
    with load_snapshot(parsed, workspace=destination) as (_, evidence):
        metadata = _column_metadata(evidence, repositories)
        for index, record in enumerate(records):
            repository = record["repository"]
            for role in ("source", "target"):
                relation = record[role + "_relation_id"]
                column = record[role + "_column"]
                supported_types = {"SNOWFLAKE_RELATION", "POSTGRES_RELATION", "DOTNET_ENTITY", "DOTNET_EVENT"} if profile in {"account-domain", "cdp-account"} else {"SNOWFLAKE_RELATION"}
                require(relation in nodes and nodes[relation]["type"] in supported_types, "Invalid mapping relation")
                field_id = identity(repository, relation, column)
                asset_id = identity(repository, relation)
                assets.setdefault(asset_id, {**scope, "asset_id": asset_id, "repository": repository,
                    "asset_name": nodes[relation]["properties"].get("name", relation), "relation_id": relation,
                    "description": nodes[relation]["properties"].get("description", ""),
                    "metadata_json": json.dumps(nodes[relation].get("properties", {}), ensure_ascii=True)})
                fields.setdefault(field_id, {**scope, "field_id": field_id, "asset_id": asset_id,
                    "repository": repository, "relation_id": relation, "field_name": column, "data_type": "",
                    "is_mapped_target": "false", "description": "", "description_source_type": "not_supplied",
                    "description_provenance_json": "null", "metadata_json": "{}", "evidence_json": "[]",
                    "description_generation_status": "", "description_confidence_score_10": "", "description_confidence_json": "null"})
                field_evidence[field_id].append({"mapping_id": record["field_id"], "role": role,
                    "source_path": repository + "/" + record["source_path"], "column": column,
                    "expression": record["transformation_expression"], "original_record_pointer": "/" + str(index)})
                if repository == "kb-accounts":
                    original = record.get("property_metadata", {})
                    if role == "target" and record.get("mapping_kind") == "csharp_event_assignment":
                        original = {}
                    target_metadata[field_id].append({"source_path": repository + "/" + original.get("source_path", record["source_path"]),
                        "description": original.get("description", ""),
                        "data_type": (record.get("data_type") if role == "target" else original.get("source_data_type")) or "",
                        "declaration": {"mapping_kind": record["mapping_kind"], "role": role,
                            "binding_expression": record["transformation_expression"], "original_documentation": original.get("original_documentation", "")}})
                if role == "target":
                    fields[field_id]["is_mapped_target"] = "true"
                    target_metadata[field_id].extend(metadata.get((repository, record["project"], record["target_model"].casefold(), column.upper()), []))
            source_rows.append({**scope, "dictionary_entry_id": record["field_id"], "repository": repository,
                "project": record["project"], "source_field_id": identity(repository, record["source_relation_id"], record["source_column"]),
                "target_field_id": identity(repository, record["target_relation_id"], record["target_column"]),
                "source_relation": record["source_relation"], "source_column": record["source_column"],
                "target_relation": record["target_relation"], "target_column": record["target_column"],
                "source_description": "", "target_description": "", "transformation_expression": record["transformation_expression"],
                "confidence": record["confidence"], "source_path": repository + "/" + record["source_path"],
                "original_record_pointer": "/" + str(index)})
            if profile in {"account-domain", "cdp-account"}:
                source_rows[-1]["mapping_kind"] = record.get("mapping_kind", "sql_projection")
    for field_id, field in fields.items():
        declarations = list({json.dumps(item, sort_keys=True): item for item in target_metadata[field_id]}.values())
        descriptions = {str(item["description"]) for item in declarations if str(item["description"]).strip()}
        types = {str(item["data_type"]) for item in declarations if item["data_type"]}
        field["data_type"] = next(iter(types)) if len(types) == 1 else ""
        field["metadata_json"] = json.dumps({"column_declarations": declarations, "description_conflict": len(descriptions) > 1}, ensure_ascii=True)
        if len(descriptions) == 1:
            field["description"] = next(iter(descriptions))
            field["description_source_type"] = "existing_metadata"
            field["description_provenance_json"] = json.dumps({"source_type": "existing_metadata", "evidence": declarations}, ensure_ascii=True)
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "field_evidence.json", dict(field_evidence))
    evidence_hash = digest_file(destination / "field_evidence.json")
    for field_id, field in fields.items():
        field["evidence_json"] = json.dumps({"file": "field_evidence.json", "sha256": evidence_hash, "json_pointer": "/" + field_id})
    for row in source_rows:
        row["source_description"] = fields[row["source_field_id"]]["description"]
        row["target_description"] = fields[row["target_field_id"]]["description"]
    destination.mkdir(parents=True, exist_ok=True)
    mapping_headers = MAPPINGS + (["mapping_kind"] if profile in {"account-domain", "cdp-account"} else [])
    for filename, headers, rows in ((CSV_FILES[0], ASSETS, list(assets.values())), (CSV_FILES[1], FIELDS, list(fields.values())), (CSV_FILES[2], mapping_headers, source_rows)):
        write_table(destination / filename, headers, rows)
    shutil.copyfile(input_path, destination / "original_records.json")
    write_json(destination / "manifest.json", {**scope, "input_sha256": digest_file(input_path), "repositories": list(repositories),
        "original_records_sha256": digest_file(destination / "original_records.json"), "dictionary_contract": CONTRACT})
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    manifest["field_evidence_sha256"] = evidence_hash
    if profile in {"account-domain", "cdp-account"}:
        manifest["run_profile"] = profile
    if parse_manifest.get("account_scope"):
        manifest["account_scope"] = parse_manifest["account_scope"]
    write_json(destination / "manifest.json", manifest)
    return validate(destination)


def validate(directory: Path, baseline: Path | None = None):
    manifest = read_json(directory / "manifest.json")
    require(manifest.get("dictionary_contract") == CONTRACT, "Not a TMV dictionary bundle")
    profile = manifest.get("run_profile", "tmv")
    require(profile in {"tmv", "account-domain", "cdp-account"}, "Unknown dictionary run profile")
    repositories = CDP_ACCOUNT_REPOSITORIES if profile == "cdp-account" else ACCOUNT_DOMAIN_REPOSITORIES if profile == "account-domain" else TMV_REPOSITORIES
    require(set(manifest["repositories"]) == set(repositories), "Dictionary repository scope changed")
    if profile in {"account-domain", "cdp-account"}:
        require(manifest.get("account_scope", {}).get("profile") == profile, "Missing Account-domain scope policy")
    tables = read_tables(directory)
    require(digest_file(directory / "original_records.json") == manifest["original_records_sha256"] == manifest["input_sha256"], "Original mapping archive changed")
    original = read_json(directory / "original_records.json")
    require(digest_file(directory / "field_evidence.json") == manifest["field_evidence_sha256"], "Field evidence archive changed")
    evidence = read_json(directory / "field_evidence.json")
    assets = {row["asset_id"]: row for row in tables[CSV_FILES[0]].rows}
    fields = {row["field_id"]: row for row in tables[CSV_FILES[1]].rows}
    for filename, table in tables.items():
        id_key = {CSV_FILES[0]: "asset_id", CSV_FILES[1]: "field_id", CSV_FILES[2]: "dictionary_entry_id"}[filename]
        require(len({row[id_key] for row in table.rows}) == len(table.rows), "Duplicate scoped IDs")
        for row in table.rows:
            require(all(row[key] == manifest[key] for key in COMMON), "Dictionary scope identity mismatch")
            require(row["repository"] in repositories and (row["repository"] != "kb-accounts" or profile in {"account-domain", "cdp-account"}), "Unsupported data-field repository")
    require(len(original) == len(tables[CSV_FILES[2]].rows), "Mapping count changed")
    for field in fields.values():
        require(field["asset_id"] in assets, "Field asset endpoint missing")
        reference = json.loads(field["evidence_json"])
        require(reference == {"file": "field_evidence.json", "sha256": manifest["field_evidence_sha256"], "json_pointer": "/" + field["field_id"]}, "Field evidence reference changed")
        require(field["field_id"] in evidence, "Field evidence missing")
    for index, row in enumerate(tables[CSV_FILES[2]].rows):
        require(row["source_field_id"] in fields and row["target_field_id"] in fields, "Mapping field endpoint missing")
        require(row["source_description"] == fields[row["source_field_id"]]["description"] and row["target_description"] == fields[row["target_field_id"]]["description"], "Description mirror mismatch")
        record = original[index]
        if profile in {"account-domain", "cdp-account"}:
            require(row.get("mapping_kind") == record.get("mapping_kind", "sql_projection"), "Mapping kind changed")
            if row["repository"] == "kb-accounts":
                require(record.get("mapping_kind") in {"ef_property_binding", "ef_json_document_binding", "csharp_event_assignment"}
                        and record["source_relation_id"].startswith("dotnet:entity:kb-accounts:")
                    and record["target_relation_id"].startswith("dotnet:event:kb-accounts:" if record.get("mapping_kind") == "csharp_event_assignment" else "postgres:relation:kb-accounts:"), "Invalid EF/event mapping identities")
        require(row["dictionary_entry_id"] == record["field_id"] and row["original_record_pointer"] == "/" + str(index), "Original mapping order changed")
        for key in ("source_relation", "source_column", "target_relation", "target_column", "transformation_expression", "confidence", "project", "repository"):
            require(row[key] == record[key], "Original mapping value changed: " + key)
        require(row["source_field_id"] == identity(record["repository"], record["source_relation_id"], record["source_column"]), "Wrong source identity")
        require(row["target_field_id"] == identity(record["repository"], record["target_relation_id"], record["target_column"]), "Wrong target identity")
    if baseline:
        old_tables = read_tables(baseline)
        require((directory / CSV_FILES[0]).read_bytes() == (baseline / CSV_FILES[0]).read_bytes(), "Asset registry changed")
        require((directory / "original_records.json").read_bytes() == (baseline / "original_records.json").read_bytes(), "Original records changed")
        require((directory / "manifest.json").read_bytes() == (baseline / "manifest.json").read_bytes(), "Source snapshot changed")
        require((directory / "field_evidence.json").read_bytes() == (baseline / "field_evidence.json").read_bytes(), "Field evidence changed")
        for filename in CSV_FILES[1:]:
            old = old_tables[filename]
            new = tables[filename]
            require(old.headers == new.headers and len(old.rows) == len(new.rows), "Enrichment changed structure")
            for before, after in zip(old.rows, new.rows):
                permitted = ({"description", "description_source_type", "description_provenance_json", "description_generation_status", "description_confidence_score_10", "description_confidence_json"}
                             if filename == CSV_FILES[1] else {"source_description", "target_description"})
                for key in old.headers:
                    if key not in permitted:
                        require(before[key] == after[key], "Protected cell changed: " + key)
                if filename == CSV_FILES[1] and before["description"].strip():
                    require(before == after, "Existing description metadata changed")
                if filename == CSV_FILES[1] and before["description"] != after["description"]:
                    require(eligible(before) and after["description_source_type"] == "ai_generated", "Ineligible description changed")
                    from lineage_poc.validation.descriptions import validate_sentences, validate_assessment
                    validate_sentences(after["description"])
                    assessment = json.loads(after["description_confidence_json"])
                    validate_assessment(assessment, tables=old_tables)
                    require(after["description_confidence_score_10"] == str(assessment["score_10"]), "Description score mirror mismatch")
                    provenance = json.loads(after["description_provenance_json"])
                    require(provenance["input_hashes"] == {name: table.sha256 for name, table in old_tables.items()}, "Stale description evidence hashes")
                    require(provenance["decision"]["description"] == after["description"] and provenance["decision"]["assessment"] == assessment, "Description provenance mismatch")
                    require(provenance["previous"] == before, "Previous field state not preserved exactly")
                    linked = {row["dictionary_entry_id"] for row in old_tables[CSV_FILES[2]].rows if before["field_id"] in (row["source_field_id"], row["target_field_id"])}
                    for reference in assessment["evidence_refs"].values():
                        require(reference["graph_id"] == before["graph_id"] and reference["snapshot_id"] == before["snapshot_id"], "Description evidence scope changed")
                        permitted_ids = ({before["field_id"]} if reference["file"] == CSV_FILES[1] else linked if reference["file"] == CSV_FILES[2] else {before["asset_id"]})
                        require(reference["row_id"] in permitted_ids, "Description evidence is unrelated to the field")
                    require(provenance["is_approved_business_definition"] is False, "AI draft is not business approval")
    return {"status": "passed", "dictionary_contract": CONTRACT,
        "assets": len(assets), "fields": len(fields), "mappings": len(original),
        "eligible_missing_descriptions": sum(eligible(row) for row in fields.values()),
        "existing_descriptions": sum(row["description_source_type"] == "existing_metadata" and bool(row["description"].strip()) for row in fields.values()),
        "ai_draft_descriptions": sum(row["description_source_type"] == "ai_generated" and bool(row["description"].strip()) for row in fields.values()),
        "nonempty_descriptions": sum(bool(row["description"].strip()) for row in fields.values()),
        "missing_out_of_scope_descriptions": sum(not row["description"].strip() and not eligible(row) for row in fields.values()),
        "maximum_cell_characters": {name: table.maximum_cell_characters for name, table in tables.items()},
        "scope": "TMV repository-static dictionary; not the legacy Ultracs V3 contract or live verification"}
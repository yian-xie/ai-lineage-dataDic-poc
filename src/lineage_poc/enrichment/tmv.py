"""Hash-bound assistant description decisions for the explicit TMV dictionary."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from lineage_poc.dictionary.io import CSV_FILES, read_tables, require, write_table, digest_file
from lineage_poc.dictionary.tmv import eligible, validate, CONTRACT
from lineage_poc.execution import read_json, write_json, utc_now
from lineage_poc.validation.descriptions import validate_sentences, validate_assessment, utc_time


def assemble_review(context_path: Path, review_path: Path, destination: Path):
    """Expand explicitly authored review groups into scoped records; author no prose."""
    context, review = read_json(context_path), read_json(review_path)
    groups = {}
    for field in context["eligible_fields"]:
        example = field["mapping_examples"][0]
        key = (field["field_name"], example["source_column"], example["transformation_expression"])
        groups.setdefault(key, []).append(field)
    require(set(review["descriptions"]) == {str(index) for index in range(len(groups))}, "Incomplete assistant review")
    generated_at = utc_now()
    generator = "GitHub Copilot (active VS Code assistant)"
    results = []
    for index, fields in enumerate(groups.values()):
        description = review["descriptions"][str(index)]
        validate_sentences(description)
        points = [1, 1, 1 if index in review["partial_transformation_groups"] else 2, 0, 2]
        criteria = ["identity_grounding", "meaning_support", "transformation_support", "corroboration", "uncertainty_handling"]
        refs = [["E1", "E2", "E3"], ["E4", "E5"], ["E4", "E5"], [], ["E2", "E6"]]
        reasons = [review["criterion_judgments"].get(criterion, description) for criterion in criteria]
        for field in fields:
            assessment = {
                "assessment_scope": "description_evidence", "assessment_origin": "ai_self_assessment",
                "rubric_id": "description-evidence-v1", "verification_mode": "supplied_csv_only",
                "score_10": sum(points),
                "components": [{"criterion": criterion, "points": point, "reason": reason, "evidence_refs": evidence}
                               for criterion, point, reason, evidence in zip(criteria, points, reasons, refs)],
                "evidence_refs": field["evidence_refs"],
                "calculation": " + ".join(str(point) for point in points) + f" = {sum(points)} / 10",
                "rationale": description, "limitations": review["limitations"],
                "assessed_by": generator, "model": None, "assessed_at": generated_at,
                "human_review_status": "not_reviewed", "is_probability": False,
            }
            results.append({"graph_id": field["graph_id"], "snapshot_id": field["snapshot_id"],
                "field_id": field["field_id"], "status": "draft", "description": description, "assessment": assessment})
    payload = {"schema_version": "tmv-description-drafts-v1", "rubric_id": "description-evidence-v1",
        "input_hashes": context["input_hashes"], "run_id": "tmv-current", "generator": generator,
        "model": None, "generated_at": generated_at, "results": results,
        "assistant_review_sha256": digest_file(review_path), "context_sha256": digest_file(context_path)}
    write_json(destination, payload)
    return {"decisions": len(results), "review_groups": len(groups)}


def revalidate_saved_review(context_path: Path, saved_drafts: Path, destination: Path):
    """Rebind only assistant decisions whose exact field evidence values match."""
    context, prior = read_json(context_path), read_json(saved_drafts)
    existing = {row["field_id"]: row for row in prior["results"]}
    generated_at = utc_now()
    results = []
    for field in context["eligible_fields"]:
        require(field["field_id"] in existing, "A new eligible field requires active assistant authorship")
        old = existing[field["field_id"]]
        require(old["status"] == "draft", "Saved decision is not a supported draft")
        old_values = {key: reference["value"] for key, reference in old["assessment"]["evidence_refs"].items()}
        new_values = {key: reference["value"] for key, reference in field["evidence_refs"].items()}
        require(old_values == new_values, "Changed field evidence requires a new assistant decision")
        result = json.loads(json.dumps(old))
        result.update(graph_id=field["graph_id"], snapshot_id=field["snapshot_id"])
        result["assessment"]["evidence_refs"] = field["evidence_refs"]
        result["assessment"]["assessed_at"] = generated_at
        results.append(result)
    payload = {
        "schema_version": "tmv-description-drafts-v1", "rubric_id": "description-evidence-v1",
        "input_hashes": context["input_hashes"], "run_id": context.get("run_profile", "tmv-account") + "-current",
        "generator": prior["generator"], "model": prior.get("model"), "generated_at": generated_at,
        "results": results, "context_sha256": digest_file(context_path),
        "reused_from": {"drafts_sha256": digest_file(saved_drafts), "generated_at": prior["generated_at"],
                        "generator": prior["generator"], "method": "Exact field identity and all evidence values revalidated by the active assistant; prose retained, not newly generated."},
    }
    write_json(destination, payload)
    return {"decisions": len(results), "authoring_mode": "revalidated_existing_assistant_drafts"}


def assemble_schema_review(context_path: Path, saved_drafts: Path, review_path: Path, destination: Path):
    """Record literal assistant-authored schema prose and exact-match prior decisions."""
    context, prior, review = read_json(context_path), read_json(saved_drafts), read_json(review_path)
    old = {row["field_id"]: row for row in prior["results"]}
    groups, results, reused_ids = {}, [], []
    generated_at = utc_now()
    generator = "GitHub Copilot (active VS Code assistant)"
    for field in context["eligible_fields"]:
        previous = old.get(field["field_id"])
        if previous and previous["status"] == "draft" and (
            {key: item["value"] for key, item in previous["assessment"]["evidence_refs"].items()} ==
            {key: item["value"] for key, item in field["evidence_refs"].items()}
        ):
            result = json.loads(json.dumps(previous))
            result.update(graph_id=field["graph_id"], snapshot_id=field["snapshot_id"])
            result["assessment"].update(evidence_refs=field["evidence_refs"], assessed_at=generated_at, assessed_by=generator, model=None)
            results.append(result)
            reused_ids.append(field["field_id"])
        else:
            example = field["mapping_examples"][0]
            key = (field["field_name"], example["source_column"], example["transformation_expression"])
            groups.setdefault(key, []).append(field)
    require(set(review["descriptions"]) == {str(index) for index in range(len(groups))}, "Assistant schema review must cover all new exact binding groups")
    for index, fields in enumerate(groups.values()):
        description = review["descriptions"][str(index)]
        validate_sentences(description)
        for field in fields:
            components = []
            for criterion in ("identity_grounding", "meaning_support", "transformation_support", "corroboration", "uncertainty_handling"):
                authored = review.get("group_criteria", {}).get(str(index), {}).get(criterion, review["criteria"][criterion])
                components.append({"criterion": criterion, "points": authored["points"],
                    "reason": description if authored["reason"] is None else authored["reason"], "evidence_refs": authored["evidence_refs"]})
            points = [component["points"] for component in components]
            assessment = {"assessment_scope": "description_evidence", "assessment_origin": "ai_self_assessment",
                "rubric_id": "description-evidence-v1", "verification_mode": "supplied_csv_only", "score_10": sum(points),
                "components": components, "evidence_refs": field["evidence_refs"],
                "calculation": " + ".join(str(value) for value in points) + " = " + str(sum(points)) + " / 10",
                "rationale": description, "limitations": review["limitations"], "assessed_by": generator,
                "model": None, "assessed_at": generated_at, "human_review_status": "not_reviewed", "is_probability": False}
            results.append({"graph_id": field["graph_id"], "snapshot_id": field["snapshot_id"], "field_id": field["field_id"],
                "status": "draft", "description": description, "assessment": assessment})
    payload = {"schema_version": "tmv-description-drafts-v1", "rubric_id": "description-evidence-v1",
        "input_hashes": context["input_hashes"], "run_id": context.get("run_profile", "tmv") + "-current", "generator": generator,
        "model": None, "generated_at": generated_at, "context_sha256": digest_file(context_path), "results": results,
        "assistant_review_sha256": digest_file(review_path), "newly_authored_results": len(results) - len(reused_ids),
        "reused_from": {"drafts_sha256": digest_file(saved_drafts), "generated_at": prior["generated_at"],
            "generator": prior["generator"], "field_ids": reused_ids, "method": "Exact scoped identities and all cited evidence values revalidated; these prior descriptions are retained, not newly authored."}}
    write_json(destination, payload)
    return {"newly_authored": payload["newly_authored_results"], "revalidated": len(reused_ids), "review_groups": len(groups)}


def prepare(input_dir: Path, destination: Path):
    validate(input_dir)
    tables = read_tables(input_dir)
    mappings = tables[CSV_FILES[2]].rows
    by_target = {}
    for row in mappings:
        by_target.setdefault(row["target_field_id"], []).append(row)
    fields = []
    for row in tables[CSV_FILES[1]].rows:
        if not eligible(row):
            continue
        examples = by_target[row["field_id"]][:3]
        references = {}
        for column in ("field_name", "relation_id", "repository"):
            references["E" + str(len(references) + 1)] = {
                "file": CSV_FILES[1], "input_sha256": tables[CSV_FILES[1]].sha256,
                "graph_id": row["graph_id"], "snapshot_id": row["snapshot_id"],
                "row_id_column": "field_id", "row_id": row["field_id"],
                "column": column, "json_pointer": None, "value": row[column],
            }
        for column in ("transformation_expression", "source_column", "source_path"):
            mapping = examples[0]
            references["E" + str(len(references) + 1)] = {
                "file": CSV_FILES[2], "input_sha256": tables[CSV_FILES[2]].sha256,
                "graph_id": row["graph_id"], "snapshot_id": row["snapshot_id"],
                "row_id_column": "dictionary_entry_id", "row_id": mapping["dictionary_entry_id"],
                "column": column, "json_pointer": None, "value": mapping[column],
            }
        fields.append({"graph_id": row["graph_id"], "snapshot_id": row["snapshot_id"],
            "field_id": row["field_id"], "field_name": row["field_name"],
            "relation_id": row["relation_id"], "repository": row["repository"],
            "mapping_examples": examples, "evidence_refs": references})
    context = {"schema_version": "tmv-description-context-v1", "dictionary_contract": CONTRACT,
        "input_hashes": {name: table.sha256 for name, table in tables.items()},
        "eligible_fields": fields, "scope": "Only blank mapped TMV target-field descriptions; preserve existing descriptions"}
    manifest = read_json(input_dir / "manifest.json")
    if manifest.get("run_profile") in {"account-domain", "cdp-account"}:
        context["run_profile"] = manifest["run_profile"]
    write_json(destination / "context.json", context)
    return {"status": "awaiting_assistant_drafts", "eligible_fields": len(fields), "input_hashes": context["input_hashes"]}


def decisions(input_dir: Path, payload: dict):
    validate(input_dir)
    tables = read_tables(input_dir)
    require(payload.get("schema_version") == "tmv-description-drafts-v1", "Wrong TMV draft contract")
    require(payload.get("input_hashes") == {name: table.sha256 for name, table in tables.items()}, "Stale TMV draft hashes")
    utc_time(payload.get("generated_at"), "generated_at")
    require(bool(payload.get("generator")) and bool(payload.get("run_id")), "Missing actual assistant attribution")
    fields = {row["field_id"]: row for row in tables[CSV_FILES[1]].rows}
    expected = {key for key, row in fields.items() if eligible(row)}
    results = payload.get("results", [])
    require(len({row["field_id"] for row in results}) == len(results), "Duplicate draft IDs")
    require({row["field_id"] for row in results} == expected, "TMV drafts must cover exactly every eligible field")
    mapping_index = {row["dictionary_entry_id"]: row for row in tables[CSV_FILES[2]].rows}
    for result in results:
        field = fields[result["field_id"]]
        require(all(result[key] == field[key] for key in ("graph_id", "snapshot_id")), "Draft snapshot mismatch")
        if result["status"] == "draft":
            validate_sentences(result["description"])
            assessment = result["assessment"]
            validate_assessment(assessment, tables=tables)
            require(assessment["assessed_by"] == payload["generator"] and assessment["assessed_at"] == payload["generated_at"] and assessment.get("model") == payload.get("model"), "Assessment attribution mismatch")
            for reference in assessment["evidence_refs"].values():
                require(reference["graph_id"] == field["graph_id"] and reference["snapshot_id"] == field["snapshot_id"], "Evidence scope mismatch")
                if reference["file"] == CSV_FILES[1]:
                    require(reference["row_id"] == field["field_id"], "Unrelated field evidence")
                elif reference["file"] == CSV_FILES[2]:
                    mapping = mapping_index[reference["row_id"]]
                    require(field["field_id"] in (mapping["source_field_id"], mapping["target_field_id"]), "Unrelated mapping evidence")
                else:
                    require(reference["row_id"] == field["asset_id"], "Unrelated asset evidence")
        else:
            require(result["status"] == "needs_evidence" and result.get("description") is None and result.get("assessment") is None and result.get("reason") and result.get("open_questions"), "Unsupported TMV description decision")
    return tables, {result["field_id"]: result for result in results}


def record(input_dir: Path, drafts: Path, destination: Path):
    payload = read_json(drafts)
    _, results = decisions(input_dir, payload)
    context_path = destination.parent / "06a-enrichment-context" / "context.json"
    require(context_path.is_file() and payload["context_sha256"] == digest_file(context_path), "Drafts do not match the recorded TMV context")
    shutil.copyfile(drafts, destination / "drafts.json")
    return {"status": "passed", "drafts_recorded": len(results), "drafts_sha256": digest_file(drafts),
        "authoring_mode": "mixed_active_assistant_and_revalidated" if payload.get("newly_authored_results") and payload.get("reused_from") else "revalidated_existing_assistant_drafts" if payload.get("reused_from") else "active_assistant_authored", "external_AI_invoked": False}


def apply(input_dir: Path, drafts: Path, destination: Path):
    payload = read_json(drafts)
    tables, results = decisions(input_dir, payload)
    destination.mkdir(parents=True, exist_ok=True)
    for name in (CSV_FILES[0], "manifest.json", "original_records.json", "field_evidence.json"):
        shutil.copyfile(input_dir / name, destination / name)
    fields = {row["field_id"]: row for row in tables[CSV_FILES[1]].rows}
    for field_id, decision in results.items():
        row = fields[field_id]
        previous = dict(row)
        reused = payload.get("reused_from")
        if reused and "field_ids" in reused and field_id not in reused["field_ids"]:
            reused = None
        row["description_generation_status"] = decision["status"]
        if decision["status"] == "draft":
            row["description"] = decision["description"]
            row["description_source_type"] = "ai_generated"
            row["description_confidence_json"] = json.dumps(decision["assessment"], ensure_ascii=True)
            row["description_confidence_score_10"] = str(decision["assessment"]["score_10"])
        row["description_provenance_json"] = json.dumps({"source_type": row["description_source_type"],
            "status": decision["status"], "generator": payload["generator"], "model": payload.get("model"),
            "generated_at": payload["generated_at"], "run_id": payload["run_id"], "input_hashes": payload["input_hashes"],
            "decision": decision, "previous": previous, "reused_from": reused,
            "is_approved_business_definition": False}, ensure_ascii=True)
    for row in tables[CSV_FILES[2]].rows:
        row["source_description"] = fields[row["source_field_id"]]["description"]
        row["target_description"] = fields[row["target_field_id"]]["description"]
    for name in CSV_FILES[1:]:
        write_table(destination / name, tables[name].headers, tables[name].rows)
    result = validate(destination, input_dir)
    result.update(drafts_applied=sum(row["status"] == "draft" for row in results.values()),
                  needs_evidence=sum(row["status"] == "needs_evidence" for row in results.values()))
    return result
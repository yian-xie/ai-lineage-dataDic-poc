"""Build the read-only legacy/new Account-savings field reconciliation HTML."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_LINEAGE = ROOT / "output/04-column-lineage/column_lineage.json"
NEW_ROOT = ROOT / "CDP_Account_output/Account"
NEW_CROSSWALK = NEW_ROOT / "04-column-lineage/cross_repository_field_lineage.json"
NEW_FIELDS = NEW_ROOT / "06c-ai-enrichment/field_catalog.csv"
DESTINATION = Path(__file__).resolve().parent / "account-savings-field-mapping.html"

SPECS = {
    ("Account_Index_ID", "Prod"): {
        "source_property": "ProductFacility.BankingProductCode",
        "event_property": "BankingProductCode",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "Both target fields are product-code candidates, but the old Account_Index_ID component is inferred from Prod/PID and the new field is a product-facility code. Confirm the value domain.",
    },
    ("Account_ID", "KiwiAcc"): {
        "source_property": "AccountId",
        "event_property": "AccountId",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "The old target is KIWIBANKACCOUNTNUMBER; the new target is AccountId. The labels suggest a relationship but do not prove the identifier values are interchangeable.",
    },
    ("Account_Name", "AccountName"): {
        "source_property": "Name",
        "event_property": "AccountName",
        "meaning": "Equivalent",
        "derivation": "Different",
        "reason": "Both dictionary descriptions identify the account name. Legacy DWACC/HVR/BASIC and new entity/event/JSON extraction are different derivation paths.",
    },
    ("Status", "Status"): {
        "source_property": "Status",
        "event_property": "AccountStatus",
        "meaning": "Equivalent",
        "derivation": "Different",
        "reason": "Both describe account state. The new event builder applies AccountStatusHelper; the old mapping uses DWACC/HVR and a DBT target.",
    },
    ("Alternative_Account_Name", "AltAccountName"): {
        "source_property": "AlternateName",
        "event_property": "AlternateAccountName",
        "meaning": "Equivalent",
        "derivation": "Different",
        "reason": "Both dictionary descriptions identify an alternate account name. The source and transformation paths differ.",
    },
    ("DateFrozen", "DateFrozen"): {
        "source_property": "AccountFreezeDetails.Effective",
        "event_property": "AccountFrozenDateTime",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "The old field is DateFrozen; the new field is the freeze effective timestamp. Confirm that the legacy date and effective-time semantics match.",
    },
    ("DateClosed", "DateClosed"): {
        "source_property": "Closed",
        "event_property": "AccountClosedDateTime",
        "meaning": "Equivalent",
        "derivation": "Different",
        "reason": "Both represent account closure time/date. Legacy date conversion and new timestamp event/SQL extraction differ.",
    },
    ("CloseReason", "CloseReason"): {
        "source_property": "AccountClosureReason",
        "event_property": "AccountClosureReason",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "The legacy target is CLOSEREASONCODE while the new field is AccountClosureReason; confirm whether code values and reason values have the same domain.",
    },
    ("LoanIntRate", "LoanIntRate"): {
        "source_property": "ProductFacility.InterestRate",
        "event_property": "Rate",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "A legacy loan interest rate may correspond to the new product-facility interest rate, but product scope and rate semantics are not established as equal.",
    },
    ("LoanRateEffectiveDate", "LoanRateEffectiveDate"): {
        "source_property": "ProductFacility.InterestRateValidFrom",
        "event_property": "ValidFrom",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "Both are rate-effective dates, but the legacy loan rate and new product-facility arrangement may have different scope and timing rules.",
    },
    ("Account_Opened_Date", "OpenDate"): {
        "source_property": "Opened",
        "event_property": "AccountOpenedDateTime",
        "meaning": "Equivalent",
        "derivation": "Different",
        "reason": "Both describe when the account opened. Legacy date formatting and new timestamp event/SQL extraction differ.",
    },
    ("DomTaxCode", "DomTaxCode"): {
        "source_property": "DomesticTaxRate.DomesticTaxType",
        "event_property": "DomesticTaxType",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "DOMTAXCODE may identify a tax category, while the new field is DomesticTaxType. Confirm the value domain and whether the legacy code includes more than type.",
    },
    ("Signatory_Count", "NumOfSignaturesReq"): {
        "source_property": "MinimumNumberOfAuthoriser",
        "event_property": "MinimumNumberOfAuthoriser",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "A required signature count may align with minimum authorisers, but the business rule and treatment of joint authorities need confirmation.",
    },
    ("SPFreezeCode", "SPFreezeCode"): {
        "source_property": "AccountFreezeDetails.FreezeType",
        "event_property": "AccountFreezeType",
        "meaning": "To be confirmed",
        "derivation": "Different",
        "reason": "Both appear to identify a freeze category, but code versus type value semantics are not proven equivalent.",
    },
    ("SPFreezeDesc", "SPFreezeDesc"): {
        "source_property": "AccountFreezeDetails.FreezeDescription",
        "event_property": "AccountFreezeDescription",
        "meaning": "Equivalent",
        "derivation": "Different",
        "reason": "Both describe the account freeze. The legacy record extraction and new event/JSON projection are different paths.",
    },
    ("Balance", "Balance"): {
        "source_property": "Amount",
        "event_property": "AccountBalanceValue",
        "meaning": "Equivalent",
        "derivation": "Different",
        "reason": "Both describe an account balance amount. The old EOD BAL path and new AccountBalance event/JSON path differ; runtime/value-level parity is not tested.",
    },
}


def text(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def old_meaning(record: dict) -> str:
    cdp = str(record.get("cdp", {}).get("description") or "").strip()
    ultracs = str(record.get("ultracs", {}).get("description") or "").strip()
    if cdp and " sourced from " not in cdp:
        return cdp
    if ultracs:
        return ultracs
    return cdp or "No business description is recorded; retain the field name and source expression as technical evidence."


def source_property_label(record: dict) -> str:
    entity = str(record.get("source_entity") or "")
    marker = "Entities."
    if marker in entity:
        entity = entity.split(marker, 1)[1]
    return entity + "." + str(record.get("source_property") or "")


def main() -> None:
    old_records = json.loads(OLD_LINEAGE.read_text(encoding="utf-8"))
    crosswalk = json.loads(NEW_CROSSWALK.read_text(encoding="utf-8"))
    new_mappings = crosswalk["mappings"]
    with NEW_FIELDS.open(encoding="utf-8-sig", newline="") as handle:
        field_rows = list(csv.DictReader(handle))
    catalog = defaultdict(list)
    for row in field_rows:
        catalog[(row["relation_id"], row["field_name"].upper())].append(row)

    legacy_rows = []
    paired_new_targets = set()
    seen_legacy_ids = set()
    for record in old_records:
        field_id = record["field_id"]
        if field_id in seen_legacy_ids:
            raise ValueError("Duplicate legacy field ID: " + field_id)
        seen_legacy_ids.add(field_id)
        key = (record.get("business_field", ""), record.get("param_column", ""))
        spec = SPECS.get(key)
        program = str(record.get("ultracs_program", record.get("ultracs", {}).get("program", "")))
        if program.startswith("kb-ultracs-datawarehouse/"):
            program = program.split("/", 1)[1]
        legacy_public_targets = sorted({target.get("relation", "") + "." + target.get("column", "")
                                        for target in record.get("dbt_targets", [])
                                        if target.get("stage") == "public" and target.get("relation")})
        mapped = []
        if spec:
            mapped = [item for item in new_mappings
                      if item.get("source_property") == spec["source_property"]
                      and item.get("event_property") == spec["event_property"]]
            if not mapped:
                raise ValueError("Curated candidate has no new evidence: " + repr(key))
            paired_new_targets.update((item["raw_relation_id"], item["raw_column"].upper()) for item in mapped)
        legacy_rows.append({
            "legacy_id": field_id,
            "business_field": record.get("business_field", ""),
            "hvr_column": record.get("param_column", ""),
            "basic_expression": record.get("ultracs", {}).get("basic_expression", ""),
            "source_locator": record.get("ultracs", {}).get("source_locator", ""),
            "source_path": record.get("source_path", ""),
            "program": program,
            "extract_file": record.get("extract_file", ""),
            "meaning": old_meaning(record),
            "old_target": "; ".join(legacy_public_targets) or "No public output target identified",
            "legacy_public_targets": legacy_public_targets,
            "old_description": record.get("cdp", {}).get("description", ""),
            "confidence": record.get("confidence", ""),
            "coverage": "Mapped candidate" if spec else "Pending",
            "new_fields": [{
                "source": source_property_label(item),
                "source_repository": item.get("source_repository", "kb-accounts"),
                "source_table": item.get("source_database_relation", ""),
                "source_column": item.get("source_database_column", ""),
                "event": str(item.get("event_contract", "")).split(".")[-1] + "." + str(item.get("event_property", "")),
                "json_path": item.get("event_json_path", ""),
                "target": "; ".join(target.get("relation_id", "") + "." + target.get("column", "")
                                     for target in item.get("downstream_targets", [])) or "No final public CDP output identified",
                "consumer_repository": item.get("consumer_repository", "kb-cdp-tenant-account"),
                "consumer_product": item.get("consumer_product", ""),
                "expression": item.get("raw_sql_expression", ""),
                "downstream_targets": item.get("downstream_targets", []),
                "meaning": (catalog.get((item["raw_relation_id"], item["raw_column"].upper()), [{}])[0].get("description", "")),
                "sql_source_path": item.get("raw_sql_source_path", ""),
                "transport_status": item.get("transport_status", ""),
            } for item in mapped],
            "business_assessment": spec["meaning"] if spec else "",
            "derivation_assessment": spec["derivation"] if spec else "",
            "assessment_reason": spec["reason"] if spec else "The new workflow is still in development; no corresponding field has been established or its absence confirmed.",
        })

    if len(seen_legacy_ids) != len(old_records):
        raise ValueError("Legacy reconciliation must count each field ID exactly once")

    raw_fields = {}
    for item in new_mappings:
        key = (item["raw_relation_id"], item["raw_column"].upper())
        if key in raw_fields:
            continue
        raw_fields[key] = {
            "field": item["raw_column"],
            "source": "{} / {}.{}".format(item.get("source_repository", "kb-accounts"), item.get("source_database_relation", ""), item.get("source_database_column", "")),
            "target": "{} / {} / {}".format(item.get("consumer_repository", "kb-cdp-tenant-account"), item.get("consumer_product", ""),
                                                "; ".join(target.get("relation_id", "") + "." + target.get("column", "")
                                                           for target in item.get("downstream_targets", []))
                                                or "No final public CDP output identified"),
            "event": str(item.get("event_contract", "")).split(".")[-1] + "." + str(item.get("event_property", "")),
            "json_path": item.get("event_json_path", ""),
            "meaning": (catalog.get(key, [{}])[0].get("description", "")
                        or "Defined as a selected Account-topic raw field; see event property and JSON path."),
            "expression": item.get("raw_sql_expression", ""),
            "legacy_counterpart": "Identified candidate" if key in paired_new_targets else "None identified; pending new-workflow review",
            "state": "Mapped candidate" if key in paired_new_targets else "Pending",
        }
    new_unmapped = [row for key, row in raw_fields.items() if key not in paired_new_targets]

    unresolved_events = {}
    for item in crosswalk.get("unresolved", []):
        key = (item.get("event_contract", ""), item.get("event_property", ""), item.get("reason", ""))
        details = unresolved_events.setdefault(key, {"occurrences": 0, "sample": item})
        details["occurrences"] += 1
    mapped_event_keys = {(item.get("event_contract", ""), item.get("event_property", "")) for item in new_mappings}
    for (contract, prop, reason), details in unresolved_events.items():
        if (contract, prop) in mapped_event_keys:
            continue
        unresolved = details["sample"]
        new_unmapped.append({
            "field": contract.split(".")[-1] + "." + prop,
            "source": "kb-accounts / {}".format(unresolved.get("source_entity") or unresolved.get("schema_path") or "event contract"),
            "target": "kb-cdp-tenant-account / {} / unresolved raw table".format(unresolved.get("consumer_product") or "tenant event consumer"),
            "event": contract.split(".")[-1] + "." + prop,
            "json_path": "Not resolved to a raw SQL path",
            "meaning": "Declared event property/object; downstream tenant field is not established by the current SQL inventory.",
            "expression": reason + " (" + str(details["occurrences"]) + " source assignments)",
            "legacy_counterpart": "None identified; pending new-workflow review",
            "state": "Pending",
        })

    legacy_table_counts = Counter()
    for row in old_records:
        public_relations = {target.get("relation", "") for target in row.get("dbt_targets", [])
                            if target.get("stage") == "public" and target.get("relation")}
        for relation in public_relations:
            legacy_table_counts[relation] += 1
    new_table_counts = Counter(target.get("relation_id", "") for item in new_mappings
                               for target in item.get("downstream_targets", []) if target.get("relation_id"))
    legacy_tables = "".join("<li><code>{}</code>: {} lineage fields</li>".format(text(name), count)
                            for name, count in sorted(legacy_table_counts.items()))
    new_tables = "".join("<li><code>{}</code>: {} mapped field paths</li>".format(text(name), count)
                         for name, count in sorted(new_table_counts.items()))

    legacy_mapped = sum(row["coverage"] == "Mapped candidate" for row in legacy_rows)
    legacy_pending = sum(row["coverage"] == "Pending" for row in legacy_rows)
    no_match = 0
    if legacy_mapped + legacy_pending + no_match != len(old_records):
        raise ValueError("Legacy count equation failed")
    old_target_names = {str(row.get("cdp", {}).get("column", "")).casefold() for row in old_records}
    new_target_names = {str(item.get("raw_column", "")).casefold() for item in new_mappings}
    exact_target_name_matches = len(old_target_names.intersection(new_target_names))
    meaning_counts = Counter(row["business_assessment"] for row in legacy_rows if row["business_assessment"])
    old_target_table_count = len(legacy_table_counts)
    new_table_pair_count = len(new_table_counts)

    mapped_html = []
    unmapped_html = []
    for row in legacy_rows:
        if row["coverage"] == "Pending":
            unmapped_html.append("""<tr data-state="Pending" data-workflow="ultracs" data-search="{search}"><td>Legacy Ultracs / HVR</td>
<td><strong>{business}</strong><br><code>{legacy_id}</code><br>HVR: <code>{hvr}</code></td>
<td>{meaning}</td><td>kb-ultracs-datawarehouse / {program}<br>kb-cdp-hvr / DWACC.param / {hvr}<br>BASIC: <code>{basic}</code></td>
<td>{target}</td><td><span class="state pending-state">Pending</span></td><td>{reason}</td></tr>""".format(
                search=text(" ".join(str(v) for v in row.values())), business=text(row["business_field"]),
                legacy_id=text(row["legacy_id"]), hvr=text(row["hvr_column"]), meaning=text(row["meaning"]),
                program=text(row["program"]), basic=text(row["basic_expression"]), target=text(row["old_target"]),
                reason=text(row["assessment_reason"])))
            continue
        candidate = row["new_fields"][0]
        legacy_source = "<strong>kb-ultracs-datawarehouse</strong><br>Program: <code>{}</code><br>Locator: <code>{}</code><br>HVR: <code>kb-cdp-hvr / {}.param / {}</code>".format(
            text(row["program"]), text(row["source_locator"]), text(row["extract_file"]), text(row["hvr_column"]))
        legacy_output = "<strong>kb-cdp-tenant-account</strong><br><code>{}</code>".format(text(row["old_target"]))
        new_source = "<strong>{}</strong><br>Table.field: <code>{}.{}</code><br>Entity property: <code>{}</code><br>Event field: <code>{}</code>".format(
            text(candidate["source_repository"]), text(candidate["source_table"]), text(candidate["source_column"]),
            text(candidate["source"]), text(candidate["event"]))
        new_output = "<strong>{}</strong><br>Product: <code>{}</code><br><code>{}</code>".format(
            text(candidate["consumer_repository"]), text(candidate["consumer_product"]), text(candidate["target"]))
        business_assessment = """<span class="grade {}">{}</span><p><strong>Legacy:</strong> {}</p><p><strong>New:</strong> {}</p>""".format(
            "equivalent" if row["business_assessment"] == "Equivalent" else "confirm",
            text(row["business_assessment"]), text(row["meaning"]), text(candidate["meaning"]))
        derivation_assessment = """<span class="grade different">Different</span><details><summary>Derivation evidence</summary>
<p><strong>Legacy BASIC:</strong> <code>{}</code></p><p><strong>New JSON path:</strong> <code>{}</code></p>
<p><strong>New SQL:</strong> <code>{}</code></p><p>{}</p></details>""".format(
            text(row["basic_expression"]), text(candidate["json_path"]), text(candidate["expression"]),
            text(row["assessment_reason"]))
        mapped_html.append("""<tr data-search="{search}">
<td><strong>{business}</strong><br><code>{legacy_id}</code></td><td>{legacy_source}</td><td>{legacy_output}</td>
<td>{new_source}</td><td>{new_output}</td><td>{business_assessment}</td><td>{derivation_assessment}</td></tr>""".format(
            search=text(" ".join(str(v) for v in row.values())),
            legacy_id=text(row["legacy_id"]), business=text(row["business_field"]),
            legacy_source=legacy_source, legacy_output=legacy_output, new_source=new_source, new_output=new_output,
            business_assessment=business_assessment, derivation_assessment=derivation_assessment))

    new_html = []
    for row in new_unmapped:
        new_html.append("""<tr data-state="{state}" data-workflow="kb-accounts" data-search="{search}"><td>New kb-accounts</td><td><code>{field}</code></td>
    <td>{meaning}</td><td><code>{source}</code></td><td><code>{target}</code></td>
    <td><code>{event}</code><br><span class="muted">JSON: {json_path}<br>{expression}</span></td><td>{counterpart}<br>{state}</td></tr>""".format(
            state=text(row["state"]), search=text(" ".join(str(v) for v in row.values())),
            field=text(row["field"]), source=text(row["source"]), target=text(row["target"]),
            meaning=text(row["meaning"]), event=text(row["event"]),
            json_path=text(row["json_path"]), expression=text(row["expression"]),
            counterpart=text(row["legacy_counterpart"])))
    unmapped_html.extend(new_html)

    example_row = next((row for row in legacy_rows
                        if row["business_field"] == "Account_Name" and row["hvr_column"] == "AccountName"), None)
    if not example_row or not example_row["new_fields"]:
        raise ValueError("The Account Name overlap example is missing from the field evidence")
    example_candidate = next((item for item in example_row["new_fields"]
                              if item["source"] == "AccountProfile.Name"), example_row["new_fields"][0])
    legacy_example_target = "; ".join(example_row["legacy_public_targets"]) or "No public target identified"
    example_html = """<section class="example" aria-label="Example mapped field">
<h2>Example overlap: Account Name</h2><p>Both workflows map an account-name field to a public CDP output. The meaning is classified Equivalent; the recorded derivation paths are Different.</p>
<div class="example-grid"><div class="example-step"><strong>Legacy source</strong><span>kb-ultracs-datawarehouse / {program}</span><span>HVR: kb-cdp-hvr / {extract}.param / {hvr}</span><span>BASIC: <code>{basic}</code></span></div>
<div class="example-step"><strong>Legacy CDP output</strong><span>{legacy_target}</span></div>
<div class="example-step"><strong>New source</strong><span>{new_repository} / {source_table}.{source_column}</span><span>kb-accounts field: {source_property}</span><span>Event: {event}</span><span>JSON: <code>{json_path}</code></span></div>
<div class="example-step"><strong>New CDP output</strong><span>{consumer_repository} / {product} / {new_target}</span></div></div>
<p class="example-grade"><span class="grade equivalent">Business meaning: Equivalent</span><span class="grade different">Derivation: Different</span></p>
</section>""".format(
        program=text(example_row["program"]), extract=text(example_row["extract_file"]), hvr=text(example_row["hvr_column"]),
        basic=text(example_row["basic_expression"]), legacy_target=text(legacy_example_target),
        new_repository=text(example_candidate["source_repository"]), source_table=text(example_candidate["source_table"]),
        source_column=text(example_candidate["source_column"]), source_property=text(example_candidate["source"]),
        event=text(example_candidate["event"]), json_path=text(example_candidate["json_path"]),
        consumer_repository=text(example_candidate["consumer_repository"]), product=text(example_candidate["consumer_product"]),
        new_target=text(example_candidate["target"]))

    html_document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Account Savings Field Reconciliation</title>
<style>
:root{color-scheme:light;--ink:#172b32;--muted:#586d73;--line:#cbd8d9;--paper:#edf3f2;--white:#fff;--teal:#086c67;--amber:#9a5c00;--red:#8f332c}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 "Segoe UI",Arial,sans-serif}
header{background:#123b40;color:#fff;padding:24px clamp(16px,4vw,48px)}header h1{margin:0;font-size:26px}header p{max-width:1000px;color:#d4e4e3;margin:8px 0 0}
main{max-width:1600px;margin:0 auto;padding:20px clamp(12px,3vw,36px) 48px}.scope{padding:14px 16px;background:#fff;border-left:4px solid var(--teal);margin-bottom:16px}
.workflow-overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:18px 0}.workflow-card{background:#fff;border:1px solid var(--line);padding:16px 18px}.workflow-card h2{font-size:17px;margin:0 0 6px}.workflow-card p{margin:3px 0;color:var(--muted)}.workflow-card strong{color:#123b40}
.comparison-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:12px 0}.comparison-summary article{background:#fff;border:1px solid var(--line);border-top:4px solid var(--teal);padding:15px 17px}.comparison-summary article:last-child{border-top-color:#bd7a2a}.comparison-summary h2{margin:0 0 7px;font-size:17px}.comparison-summary p{margin:0}.comparison-summary strong{color:#123b40}
.example{background:#fff;border:1px solid var(--line);padding:16px;margin:16px 0}.example h2{font-size:17px;margin:0 0 5px}.example>p{margin:5px 0 12px}.example-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}.example-step{display:flex;flex-direction:column;gap:4px;background:#f3f7f6;border:1px solid #dce7e5;padding:10px;font-size:12px;overflow-wrap:anywhere}.example-step strong{color:#14514f}.example-grade{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0 0!important}
.count-check{background:#dcebe8;border:1px solid #b8d2ce;padding:10px 14px;margin:12px 0;font-weight:600}
section{margin-top:24px}h2{font-size:19px;margin:0 0 10px}.tables{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.table-list{background:#fff;border:1px solid var(--line);padding:14px}.table-list ul{margin:8px 0 0;padding-left:18px}.table-list li{margin:4px 0;overflow-wrap:anywhere}
.tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}.tools input,.tools select{min-height:36px;border:1px solid #9cadb0;background:#fff;padding:6px 9px;font:inherit}.tools input{min-width:min(360px,100%);flex:1}.count{color:var(--muted);font-size:12px}
.wrap{overflow:auto;max-height:72vh;border:1px solid var(--line);background:#fff}table{border-collapse:collapse;width:100%;min-width:1120px}th,td{border-bottom:1px solid #dce5e5;padding:9px 10px;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#dfeae8;color:#19363b;font-size:12px;z-index:1}td{max-width:350px;overflow-wrap:anywhere;font-size:12px}code{font:11px Consolas,"Courier New",monospace;overflow-wrap:anywhere}.muted{color:var(--muted)}
.state,.grade{display:inline-block;padding:3px 8px;border-radius:3px;font-size:11px;font-weight:700;white-space:nowrap}.mapped-state,.equivalent{background:#d9eeea;color:#075b50}.pending-state,.confirm{background:#fff0d6;color:#805000}.different{background:#e8eaf0;color:#43516b}.candidate{padding:7px 0;border-bottom:1px solid #e6eded}.candidate:last-child{border-bottom:0}.candidate strong,.candidate span{display:block}.candidate span{font-size:11px;color:var(--muted)}.candidate details{margin-top:4px}.candidate pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f6f5;padding:8px;margin:5px 0}.comparison-cell p{margin:7px 0 0}.note{background:#fff;border:1px solid var(--line);padding:13px 15px;color:var(--muted)}details{margin-top:8px}summary{cursor:pointer;font-weight:600;color:#28575a}footer{margin-top:24px;color:var(--muted);font-size:12px}
@media(max-width:700px){header h1{font-size:22px}.wrap{max-height:65vh}td{max-width:280px}}
</style></head><body>
<header><h1>Account Savings Field Reconciliation</h1><p>Legacy DWACC/HVR output compared with the developing Account Profile and End-of-Day Account workflow. This is a static evidence comparison, not runtime value validation.</p></header>
<main>
<div class="scope"><strong>How to read this:</strong> “Mapped candidate” means there is a source-backed field to compare, not that the values are proven equal. The new workflow is still in development, so unmatched legacy fields are Pending unless a No match is confirmed.</div>
<section class="workflow-overview" aria-label="Workflow sizes">
<article class="workflow-card"><h2>Legacy: Ultracs / HVR → CDP</h2><p><strong>__TOTAL__ field links</strong> from DWACC across <strong>__OLDTABLESCOUNT__ output models</strong>.</p><p>Source evidence: KWDW_ACC BASIC expression and HVR parameter column.</p></article>
<article class="workflow-card"><h2>New: kb-accounts → tenant CDP</h2><p><strong>__NEWLINKS__ mapped field links</strong> across <strong>__NEWTABLESCOUNT__ final public output views</strong>.</p><p>Source evidence: EF binding or C# event → JSON path → tenant CDP output.</p></article>
</section>
<section class="comparison-summary" aria-label="Comparison summary">
<article><h2>Overlap</h2><p><strong>__EXACTNAMES__ exact target-column name matches.</strong> __MAPPED__ legacy fields have candidate mappings. Of those, <strong>__EQUIVALENT__ business meanings are Equivalent</strong> and <strong>__TBC__ are To be confirmed.</strong> Their derivation paths are <strong>Different</strong>.</p></article>
<article><h2>Remaining</h2><p><strong>__PENDING__ legacy fields are Pending.</strong> __NEWUNMAPPED__ new fields have no identified legacy counterpart. <strong>__NOMATCH__ confirmed No match.</strong></p></article>
</section>
__EXAMPLE__
<p class="count-check">Legacy field count: __MAPPED__ mapped candidates + __PENDING__ Pending + __NOMATCH__ confirmed No match = __TOTAL__ total legacy fields.</p>
<section><h2>Mapped fields across workflows</h2><p class="note">__MAPPED__ legacy fields have candidate mappings. Read the source and public-output columns from left to right; business meaning and derivation are assessed separately.</p>
<div class="wrap"><table><thead><tr><th>Legacy field</th><th>Legacy source</th><th>Legacy CDP output</th><th>New source</th><th>New CDP output</th><th>Business meaning</th><th>Derivation</th></tr></thead><tbody id="mappedRows">__MAPPED_ROWS__</tbody></table></div></section>
<section><h2>Unmapped fields</h2><p class="note">Includes __PENDING__ legacy fields pending new-workflow completion and __NEWUNMAPPED__ new fields without an identified legacy counterpart. No confirmed No match is claimed.</p>
<div class="tools"><input id="unmappedSearch" type="search" placeholder="Search field, source, table, or meaning"><select id="unmappedWorkflow"><option value="">All workflows</option><option value="ultracs">Legacy Ultracs / HVR</option><option value="kb-accounts">New kb-accounts</option></select><span class="count" id="unmappedCount"></span></div>
<div class="wrap"><table><thead><tr><th>Workflow</th><th>Field</th><th>Business meaning</th><th>Data source / source table</th><th>Public CDP output</th><th>Derivation / event evidence</th><th>Status / notes</th></tr></thead><tbody id="unmappedRows">__UNMAPPED_ROWS__</tbody></table></div></section>
<section><h2>Evidence and limitations</h2><div class="note">
Business meaning uses the old DWACC/tenant dictionary descriptions and new Account field catalog descriptions where available. Derivation evidence is the old BASIC expression plus HVR parameter column versus the new C# property assignment, event JSON path, and SQL expression. “Different” derivation means the recorded pipelines differ; it does not prove that runtime values differ. All 16 candidate links require value-level or business-owner validation before they can be treated as approved equivalents. No confirmed No match is assigned because the new workflow is still under development.
<br><br>Legacy mapping confidence: 87 explicit, 5 confirmed, 1 confirmed-calculated, 2 inferred. New Kafka topic continuity is not runtime verified.
</div></section>
<footer>Generated from the accepted workflow artifacts in output/ and CDP_Account_output/Account/. Use the linked source artifacts for full provenance.</footer>
</main>
<script>
const unmappedRows=[...document.querySelectorAll('#unmappedRows tr')];
function filterUnmapped(){const q=document.getElementById('unmappedSearch').value.toLowerCase(),workflow=document.getElementById('unmappedWorkflow').value;let n=0;for(const row of unmappedRows){const visible=(!q||row.dataset.search.toLowerCase().includes(q))&&(!workflow||row.dataset.workflow===workflow);row.hidden=!visible;if(visible)n++}document.getElementById('unmappedCount').textContent=n+' of '+unmappedRows.length+' unmapped fields'}
document.getElementById('unmappedSearch').addEventListener('input',filterUnmapped);document.getElementById('unmappedWorkflow').addEventListener('change',filterUnmapped);filterUnmapped();
</script></body></html>"""

    html_document = (html_document.replace("__TOTAL__", str(len(old_records)))
                     .replace("__MAPPED__", str(legacy_mapped))
                     .replace("__PENDING__", str(legacy_pending))
                     .replace("__NOMATCH__", str(no_match))
                     .replace("__NEWUNMAPPED__", str(len(new_unmapped)))
                     .replace("__NEWLINKS__", str(len(new_mappings)))
                     .replace("__OLDTABLESCOUNT__", str(old_target_table_count))
                     .replace("__NEWTABLESCOUNT__", str(new_table_pair_count))
                     .replace("__EXACTNAMES__", str(exact_target_name_matches))
                     .replace("__EQUIVALENT__", str(meaning_counts.get("Equivalent", 0)))
                     .replace("__TBC__", str(meaning_counts.get("To be confirmed", 0)))
                     .replace("__UNRESOLVED__", str(len(crosswalk.get("unresolved", []))))
                     .replace("__EXAMPLE__", example_html)
                     .replace("__OLD_TABLES__", legacy_tables)
                     .replace("__NEW_TABLES__", new_tables)
                     .replace("__MAPPED_ROWS__", "\n".join(mapped_html))
                     .replace("__UNMAPPED_ROWS__", "\n".join(unmapped_html)))
    DESTINATION.write_text(html_document, encoding="utf-8", newline="\n")
    print(json.dumps({
        "html": str(DESTINATION), "legacy_total": len(old_records),
        "mapped_candidates": legacy_mapped, "pending_legacy": legacy_pending,
        "confirmed_no_match": no_match, "legacy_equation": legacy_mapped + legacy_pending + no_match,
        "new_field_links": len(new_mappings), "old_target_models": old_target_table_count,
        "new_table_pairs": new_table_pair_count, "exact_target_name_overlaps": exact_target_name_matches,
        "equivalent_business_meanings": meaning_counts.get("Equivalent", 0),
        "to_be_confirmed_business_meanings": meaning_counts.get("To be confirmed", 0),
        "unresolved_new_links": len(crosswalk.get("unresolved", [])),
        "unmapped_new_fields": len(new_unmapped), "unique_new_raw_fields": len(raw_fields),
        "unresolved_new_event_fields": len(unresolved_events),
    }, indent=2))


if __name__ == "__main__":
    main()
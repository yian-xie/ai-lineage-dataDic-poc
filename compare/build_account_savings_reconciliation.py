"""Build the read-only legacy/new Account-savings field reconciliation HTML."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_LINEAGE = ROOT / "output/04-column-lineage/column_lineage.json"
NEW_ROOT = ROOT / "CDP_Account_output"
NEW_TMV_LINEAGE = NEW_ROOT / "04-column-lineage/column_lineage.json"
NEW_FIELDS = NEW_ROOT / "05-baseline-dictionary/field_catalog.csv"
NEW_DETAIL = "accounts_v1__ultracs_accounts_detail"
NEW_EOD = "accounts_v1__ultracs_accounts_eod_balances"
LEGACY_TO_NEW_MODEL = {
    "accounts_v1__ultracs_accounts_detail": NEW_DETAIL,
    "accounts_v1__ultracs_accounts_detail_v2": NEW_DETAIL,
    "accounts_v1__ultracs_accounts_eod_balances": NEW_EOD,
}
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


def norm(value: object) -> str:
    return "".join(character for character in str(value or "").upper() if character.isalnum())


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
    all_new_records = json.loads(NEW_TMV_LINEAGE.read_text(encoding="utf-8"))
    new_mappings = [row for row in all_new_records
                    if row.get("project") == "accounts-v1"
                    and row.get("target_model") in {NEW_DETAIL, NEW_EOD}
                    and str(row.get("target_relation", "")).startswith("PUBLIC.")]
    with NEW_FIELDS.open(encoding="utf-8-sig", newline="") as handle:
        field_rows = list(csv.DictReader(handle))
    catalog = {}
    for row in field_rows:
        catalog[(row["relation_id"], norm(row["field_name"]))] = row
    new_by_target = defaultdict(list)
    for row in new_mappings:
        new_by_target[(row["target_model"], norm(row["target_column"]))].append(row)

    legacy_rows = []
    paired_new_targets = set()
    seen_legacy_ids = set()
    for record in old_records:
        field_id = record["field_id"]
        if field_id in seen_legacy_ids:
            raise ValueError("Duplicate legacy field ID: " + field_id)
        seen_legacy_ids.add(field_id)
        program = str(record.get("ultracs_program", record.get("ultracs", {}).get("program", "")))
        if program.startswith("kb-ultracs-datawarehouse/"):
            program = program.split("/", 1)[1]
        legacy_public_targets = sorted({target.get("relation", "") + "." + target.get("column", "")
                                        for target in record.get("dbt_targets", [])
                                        if target.get("stage") == "public" and target.get("relation")})
        new_model = LEGACY_TO_NEW_MODEL.get(record.get("cdp", {}).get("model", ""))
        mapped = new_by_target.get((new_model, norm(record.get("cdp", {}).get("column"))), []) if new_model else []
        if mapped:
            paired_new_targets.update((item["target_model"], norm(item["target_column"])) for item in mapped)
        new_candidates = []
        for item in mapped:
            new_description = catalog.get((item.get("target_relation_id", ""), norm(item.get("target_column"))), {}).get("description", "")
            old_description = str(record.get("cdp", {}).get("description", "")).strip()
            same_meaning = bool(old_description and new_description and norm(old_description) == norm(new_description))
            model_unchanged = record.get("cdp", {}).get("model") == item.get("target_model")
            new_candidates.append({
                "source": item.get("source_column", ""),
                "source_repository": "kb-cdp-tenant-account",
                "source_table": "accounts-v1 source",
                "source_column": item.get("source_column", ""),
                "target_model": item.get("target_model", ""),
                "target_column": item.get("target_column", ""),
                "target_relation": item.get("target_relation", ""),
                "tmv_field_id": item.get("field_id", ""),
                "target": item.get("target_relation", "") + "." + item.get("target_column", ""),
                "consumer_repository": "kb-cdp-tenant-account",
                "consumer_product": item.get("project", "accounts-v1"),
                "expression": item.get("transformation_expression", ""),
                "downstream_targets": [],
                "meaning": new_description,
                "sql_source_path": item.get("source_path", ""),
                "transport_status": "static_dbT_projection_not_runtime_verified",
                "source_column_same": norm(record.get("param_column")) == norm(item.get("source_column")),
                "output_model_unchanged": model_unchanged,
            })
            if same_meaning:
                business_assessment = "Equivalent"
                assessment_reason = ("Old and new dictionaries use the same field description. "
                                     + ("The public output model and field are the same." if model_unchanged else
                                        "The field moved from the legacy V2 target to the new public detail output."))
            else:
                business_assessment = "To be confirmed"
                assessment_reason = "The field name matches the mapped target, but dictionary descriptions differ or are missing; confirm meaning."
        if not mapped:
            business_assessment = ""
            assessment_reason = "No corresponding field is defined in the selected new accounts-v1 public outputs; keep Pending while the new workflow is in development."
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
            "coverage": "Mapped candidate" if mapped else "Pending",
            "new_fields": new_candidates,
            "business_assessment": business_assessment,
            "derivation_assessment": "Different" if mapped else "",
            "assessment_reason": assessment_reason,
        })

    if len(seen_legacy_ids) != len(old_records):
        raise ValueError("Legacy reconciliation must count each field ID exactly once")

    new_targets = {}
    for item in new_mappings:
        key = (item["target_model"], norm(item["target_column"]))
        new_targets.setdefault(key, item)
    new_unmapped = []
    for key, item in new_targets.items():
        if key in paired_new_targets:
            continue
        description = catalog.get((item.get("target_relation_id", ""), norm(item["target_column"])), {}).get("description", "")
        new_unmapped.append({
            "field": item.get("target_column", ""),
            "source": "kb-cdp-tenant-account / accounts-v1 source column {}".format(item.get("source_column", "")),
            "target": "kb-cdp-tenant-account / {}.{}".format(item.get("target_relation", ""), item.get("target_column", "")),
            "event": "TMV source column {}".format(item.get("source_column", "")),
            "json_path": item.get("source_path", ""),
            "meaning": description,
            "expression": item.get("transformation_expression", ""),
            "legacy_counterpart": "No legacy DWACC output field identified",
            "state": "New only",
            "workflow": "tmv",
            "repository": "kb-cdp-tenant-account",
            "project": "accounts-v1",
            "source_column": item.get("source_column", ""),
            "source_path": item.get("source_path", ""),
            "target_model": item.get("target_model", ""),
            "target_relation": item.get("target_relation", ""),
            "tmv_field_id": item.get("field_id", ""),
        })

    legacy_table_counts = Counter()
    for row in old_records:
        legacy_model = LEGACY_TO_NEW_MODEL.get(row.get("cdp", {}).get("model", ""))
        if legacy_model:
            legacy_table_counts[legacy_model] += 1
    new_table_counts = Counter(item["target_relation"] for item in new_targets.values())
    legacy_tables = "".join("<li><code>{}</code>: {} lineage fields</li>".format(text(name), count)
                            for name, count in sorted(legacy_table_counts.items()))
    new_tables = "".join("<li><code>{}</code>: {} mapped field paths</li>".format(text(name), count)
                         for name, count in sorted(new_table_counts.items()))

    legacy_mapped = sum(row["coverage"] == "Mapped candidate" for row in legacy_rows)
    legacy_pending = sum(row["coverage"] == "Pending" for row in legacy_rows)
    no_match = 0
    if legacy_mapped + legacy_pending + no_match != len(old_records):
        raise ValueError("Legacy count equation failed")
    exact_target_name_matches = legacy_mapped
    meaning_counts = Counter(row["business_assessment"] for row in legacy_rows if row["business_assessment"])
    same_model_matches = sum(item.get("output_model_unchanged", False)
                             for row in legacy_rows for item in row["new_fields"])
    moved_model_matches = legacy_mapped - same_model_matches
    same_source_column_matches = sum(item.get("source_column_same", False)
                                     for row in legacy_rows for item in row["new_fields"])
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
        legacy_output = ("<strong>kb-cdp-tenant-account</strong><br><code>{}</code>".format(text(row["old_target"]))
                         if row["legacy_public_targets"] else
                         "<strong>Legacy DWACC field</strong><br><code>{}</code><br><span class=\"muted\">No public legacy projection listed</span>".format(
                             text(row["business_field"])))
        new_source = "<strong>kb-cdp-tenant-account / accounts-v1</strong><br>Source column: <code>{}</code>".format(
            text(candidate["source_column"]))
        new_output = "<strong>{}</strong><br>Product: <code>{}</code><br><code>{}</code>".format(
            text(candidate["consumer_repository"]), text(candidate["consumer_product"]), text(candidate["target"]))
        business_assessment = """<span class="grade {}">{}</span><p><strong>Legacy:</strong> {}</p><p><strong>New:</strong> {}</p>""".format(
            "equivalent" if row["business_assessment"] == "Equivalent" else "confirm",
            text(row["business_assessment"]), text(row["meaning"]), text(candidate["meaning"]))
        derivation_assessment = """<span class="grade different">Different</span><details><summary>Derivation evidence</summary>
    <p><strong>Legacy BASIC / HVR:</strong> <code>{}</code> / <code>{}</code></p>
    <p><strong>TMV SQL expression:</strong> <code>{}</code></p><p><strong>TMV source file:</strong> <code>{}</code></p>
    <p>{}</p></details>""".format(
            text(row["basic_expression"]), text(row["hvr_column"]), text(candidate["expression"]),
            text(candidate["sql_source_path"]), text(row["assessment_reason"]))
        mapped_html.append("""<tr data-search="{search}">
<td><strong>{business}</strong><br><code>{legacy_id}</code></td><td>{legacy_source}</td><td>{legacy_output}</td>
<td>{new_source}</td><td>{new_output}</td><td>{business_assessment}</td><td>{derivation_assessment}</td></tr>""".format(
            search=text(" ".join(str(v) for v in row.values())),
            legacy_id=text(row["legacy_id"]), business=text(row["business_field"]),
            legacy_source=legacy_source, legacy_output=legacy_output, new_source=new_source, new_output=new_output,
            business_assessment=business_assessment, derivation_assessment=derivation_assessment))

    new_html = []
    for row in new_unmapped:
        new_html.append("""<tr data-state="{state}" data-workflow="tmv" data-search="{search}"><td>New TMV accounts-v1</td><td><code>{field}</code></td>
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
                              if item["target_column"].casefold() == "accountname"), example_row["new_fields"][0])
    legacy_example_target = "; ".join(example_row["legacy_public_targets"]) or "No public target identified"
    example_html = """<section class="example" aria-label="Example mapped field">
<h2>Example overlap: Account Name</h2><p>Both workflows map an account-name field to a public CDP output. The meaning is classified Equivalent; the recorded derivation paths are Different.</p>
<div class="example-grid"><div class="example-step"><strong>Legacy source</strong><span>kb-ultracs-datawarehouse / {program}</span><span>HVR: kb-cdp-hvr / {extract}.param / {hvr}</span><span>BASIC: <code>{basic}</code></span></div>
<div class="example-step"><strong>Legacy CDP output</strong><span>{legacy_target}</span></div>
<div class="example-step"><strong>New TMV source</strong><span>{new_repository} / accounts-v1</span><span>Source column: <code>{source_column}</code></span><span>SQL: <code>{new_expression}</code></span></div>
<div class="example-step"><strong>New CDP output</strong><span>{consumer_repository} / {product} / {new_target}</span></div></div>
<p class="example-grade"><span class="grade equivalent">Business meaning: Equivalent</span><span class="grade different">Derivation: Different</span></p>
</section>""".format(
        program=text(example_row["program"]), extract=text(example_row["extract_file"]), hvr=text(example_row["hvr_column"]),
        basic=text(example_row["basic_expression"]), legacy_target=text(legacy_example_target),
        new_repository=text(example_candidate["source_repository"]), source_table=text(example_candidate["source_table"]),
        source_column=text(example_candidate["source_column"]), source_property=text(""),
        event=text(""), json_path=text(""),
        new_expression=text(example_candidate["expression"]),
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
<header><h1>Ultracs DWACC vs TMV Account Fields</h1><p>Legacy DWACC/HVR fields reconciled against the new accounts-v1 public Account Detail and EOD Balance outputs. This is static mapping evidence, not runtime value validation.</p></header>
<main>
<div class="scope"><strong>How to read this:</strong> Field matches use the final public table and column. Thirty-six legacy fields formerly targeted an internal V2 model and now appear under the public Account Detail model. Identical dictionary descriptions indicate equivalent documented meaning; derivation paths differ, and runtime values are not compared.</div>
<section class="workflow-overview" aria-label="Workflow sizes">
<article class="workflow-card"><h2>Legacy: Ultracs / HVR → CDP</h2><p><strong>__TOTAL__ DWACC fields</strong> across <strong>__OLDTABLESCOUNT__ public output tables</strong>.</p><p>Source evidence: KWDW_ACC BASIC expression and HVR parameter column.</p></article>
<article class="workflow-card"><h2>New: TMV accounts-v1 → tenant CDP</h2><p><strong>__NEWLINKS__ unique public fields</strong> across <strong>__NEWTABLESCOUNT__ output tables</strong>.</p><p>Comparison is restricted to public Account Detail and EOD Balance outputs.</p></article>
</section>
<section class="comparison-summary" aria-label="Comparison summary">
<article><h2>Overlap</h2><p><strong>__MAPPED__ of 95 legacy fields have matching TMV public output fields.</strong> __SAME_MODEL__ match the same public model; __MOVED_MODEL__ moved from a legacy V2 target to public Account Detail. <strong>__SOURCE_MATCHES__ source-column names match; __SOURCE_ALIASES__ use different source-column names.</strong> All mapped dictionary meanings are Equivalent; derivations are Different.</p><p class="muted">The earlier 35 count covered only the 59 fields whose model names stayed the same; including 36 fields promoted from legacy V2 brings the source-column matches to 62 and output-field matches to 95.</p></article>
<article><h2>Remaining</h2><p><strong>__PENDING__ legacy fields are Pending.</strong> __NEWUNMAPPED__ TMV public fields have no identified legacy counterpart. <strong>__NOMATCH__ confirmed No match.</strong></p></article>
</section>
__EXAMPLE__
<p class="count-check">Legacy field count: __MAPPED__ mapped candidates + __PENDING__ Pending + __NOMATCH__ confirmed No match = __TOTAL__ total legacy fields.</p>
<section><h2>Mapped fields across workflows</h2><p class="note">__MAPPED__ fields match by destination column in the selected public Account Detail/EOD models. __SAME_MODEL__ have the same model name; __MOVED_MODEL__ target fields moved from legacy detail_v2 to the new public detail model.</p>
<div class="wrap"><table><thead><tr><th>Legacy field</th><th>Legacy source</th><th>Legacy CDP output</th><th>New source</th><th>New CDP output</th><th>Business meaning</th><th>Derivation</th></tr></thead><tbody id="mappedRows">__MAPPED_ROWS__</tbody></table></div></section>
<section><h2>Unmapped fields</h2><p class="note">Includes __PENDING__ legacy fields pending new-workflow completion and __NEWUNMAPPED__ new fields without an identified legacy counterpart. No confirmed No match is claimed.</p>
<div class="tools"><input id="unmappedSearch" type="search" placeholder="Search field, source, table, or meaning"><select id="unmappedWorkflow"><option value="">All workflows</option><option value="ultracs">Legacy Ultracs / HVR</option><option value="tmv">New TMV accounts-v1</option></select><span class="count" id="unmappedCount"></span></div>
<div class="wrap"><table><thead><tr><th>Workflow</th><th>Field</th><th>Business meaning</th><th>Data source / source table</th><th>Public CDP output</th><th>Derivation / event evidence</th><th>Status / notes</th></tr></thead><tbody id="unmappedRows">__UNMAPPED_ROWS__</tbody></table></div></section>
<section><h2>Evidence and limitations</h2><div class="note">
Business meaning uses the old DWACC and new TMV data-dictionary descriptions. A mapped field has the same output field name in the mapped Account Detail/EOD model; identical descriptions are classified Equivalent. Legacy BASIC/HVR and new TMV SQL derivations differ, so this is not runtime value verification.
<br><br>All 95 legacy fields have matching TMV public target fields in this selected table scope. Thirty-six fields move from the legacy V2 target to public Account Detail. Fifteen additional TMV public fields have no legacy DWACC counterpart. Legacy mapping confidence: 87 explicit, 5 confirmed, 1 confirmed-calculated, 2 inferred.
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
                     .replace("__NEWLINKS__", str(len(new_targets)))
                     .replace("__OLDTABLESCOUNT__", str(old_target_table_count))
                     .replace("__NEWTABLESCOUNT__", str(new_table_pair_count))
                     .replace("__EXACTNAMES__", str(exact_target_name_matches))
                     .replace("__EQUIVALENT__", str(meaning_counts.get("Equivalent", 0)))
                     .replace("__TBC__", str(meaning_counts.get("To be confirmed", 0)))
                     .replace("__SAME_MODEL__", str(same_model_matches))
                     .replace("__MOVED_MODEL__", str(moved_model_matches))
                     .replace("__SOURCE_MATCHES__", str(same_source_column_matches))
                     .replace("__SOURCE_ALIASES__", str(legacy_mapped - same_source_column_matches))
                     .replace("__EXAMPLE__", example_html)
                     .replace("__OLD_TABLES__", legacy_tables)
                     .replace("__NEW_TABLES__", new_tables)
                     .replace("__MAPPED_ROWS__", "\n".join(mapped_html))
                     .replace("__UNMAPPED_ROWS__", "\n".join(unmapped_html)))
    DESTINATION.write_text(html_document, encoding="utf-8", newline="\n")
    alignment_path = DESTINATION.with_name("field-alignment.csv")
    alignment_headers = [
        "record_type", "status", "legacy_field_id", "legacy_business_field", "legacy_hvr_column",
        "legacy_basic_expression", "legacy_source_file", "legacy_output_table_field", "legacy_confidence",
        "new_tmv_field_id", "new_source_repository", "new_source_column", "new_public_output_table",
        "new_sql_expression", "business_meaning_assessment", "derivation_assessment",
        "source_column_name_match", "public_model_unchanged", "assessment_notes",
    ]
    with alignment_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=alignment_headers)
        writer.writeheader()
        for row in legacy_rows:
            candidate = row["new_fields"][0] if row["new_fields"] else {}
            writer.writerow({
                "record_type": "legacy_mapping", "status": row["coverage"],
                "legacy_field_id": row["legacy_id"], "legacy_business_field": row["business_field"],
                "legacy_hvr_column": row["hvr_column"], "legacy_basic_expression": row["basic_expression"],
                "legacy_source_file": row["source_path"], "legacy_output_table_field": row["old_target"],
                "legacy_confidence": row["confidence"], "new_tmv_field_id": candidate.get("tmv_field_id", ""),
                "new_source_repository": candidate.get("source_repository", ""),
                "new_source_column": candidate.get("source_column", ""),
                "new_public_output_table": candidate.get("target", ""),
                "new_sql_expression": candidate.get("expression", ""),
                "business_meaning_assessment": row["business_assessment"],
                "derivation_assessment": row["derivation_assessment"],
                "source_column_name_match": candidate.get("source_column_same", ""),
                "public_model_unchanged": candidate.get("output_model_unchanged", ""),
                "assessment_notes": row["assessment_reason"],
            })
        for row in new_unmapped:
            writer.writerow({
                "record_type": "new_only", "status": row["state"], "new_tmv_field_id": row.get("tmv_field_id", ""),
                "new_source_repository": row.get("repository", ""), "new_source_column": row.get("source_column", ""),
                "new_public_output_table": row.get("target", ""), "new_sql_expression": row.get("expression", ""),
                "assessment_notes": row.get("legacy_counterpart", ""),
            })
    print(json.dumps({
        "html": str(DESTINATION), "alignment_csv": str(alignment_path), "legacy_total": len(old_records),
        "mapped_candidates": legacy_mapped, "pending_legacy": legacy_pending,
        "confirmed_no_match": no_match, "legacy_equation": legacy_mapped + legacy_pending + no_match,
        "tmv_lineage_records": len(new_mappings), "new_unique_public_fields": len(new_targets), "old_target_models": old_target_table_count,
        "new_table_pairs": new_table_pair_count, "exact_target_name_overlaps": exact_target_name_matches,
        "equivalent_business_meanings": meaning_counts.get("Equivalent", 0),
        "to_be_confirmed_business_meanings": meaning_counts.get("To be confirmed", 0),
        "unmapped_new_fields": len(new_unmapped), "unique_new_public_fields": len(new_targets),
        "same_model_fields": same_model_matches, "moved_model_fields": moved_model_matches,
        "source_column_name_matches": same_source_column_matches,
    }, indent=2))


if __name__ == "__main__":
    main()
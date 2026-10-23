#!/usr/bin/env python3
"""Create a focused JSON and interactive HTML view for account-number lineage."""

import argparse
import html
import json
import re
from pathlib import Path

from generate_column_lineage import HTML, build_enterprise_overview, confidence_percent
from html_graph_descriptions import describe_graph


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
COLUMN_INPUT = OUTPUT_DIR / "column_lineage.json"
TABLE_INPUT = OUTPUT_DIR / "account_table_lineage.json"
DEFAULT_SELECTOR = "KiwiAcc"

FLOW_STYLE = r'''
body{grid-template-rows:auto auto minmax(0,1fr)}
.lineage-explanation{padding:10px 16px;background:#f7fbf8;border-bottom:1px solid var(--line);overflow:auto}
.flow-heading{display:flex;align-items:center;gap:9px;margin-bottom:8px}.flow-kicker{font-size:9px;letter-spacing:.1em;font-weight:850;color:#557071}.flow-confidence{font-size:9px;font-weight:800;color:#286546;background:#e8f3eb;border-radius:10px;padding:3px 7px}
.flow-chain{display:flex;align-items:stretch;gap:6px;min-width:1050px}.flow-step{display:flex;flex:1;min-width:125px;flex-direction:column;justify-content:center;gap:4px;padding:8px 10px;border:1px solid #d9e5df;border-radius:7px;background:white}.flow-step span{font-size:8px;letter-spacing:.07em;font-weight:850;color:#648076}.flow-step strong{font-size:11px;line-height:1.25;overflow-wrap:anywhere}.flow-step small{font-size:9px;line-height:1.3;color:var(--muted)}.flow-arrow{align-self:center;color:#6b8b7d;font-weight:800}.flow-arrow.inferred{color:#bd7a2a}.branch-note{margin-top:7px;color:#725628;font-size:10px}.branch-note summary{cursor:pointer;font-weight:750}.branch-note p{max-width:1200px;margin:6px 0;line-height:1.45;color:#59696a}.explanation-link{float:right;color:#287566;font-size:10px;font-weight:700;text-decoration:none;margin-top:-16px}.explanation-link:hover{text-decoration:underline}
@media(max-width:700px){.lineage-explanation{padding:8px}.flow-chain{min-width:1000px}.explanation-link{float:none;display:inline-block;margin:5px 0 0}}
'''


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def choose_records(records: list[dict], related_columns: list[dict], selector: str) -> list[dict]:
    selector_key = normalize(selector)
    business_by_param = {}
    for mapping in related_columns:
        business_name = mapping.get("business_field", "")
        for param_name in mapping.get("hvr_param_columns", [mapping.get("hvr_param_column", "")]):
            if param_name:
                business_by_param.setdefault(param_name, set()).add(business_name)

    aliases = {
        "accountnumber": "account_id",
        "kiwibankaccountnumber": "account_id",
        "accountopeneddate": "account_opened_date",
        "accountname": "account_name",
        "signatorycount": "signatory_count",
    }
    selector_keys = {selector_key}
    if selector_key in aliases:
        selector_keys.add(normalize(aliases[selector_key]))

    matches = []
    for record in records:
        candidates = {
            normalize(record.get("param_column", "")),
            normalize(record.get("snowflake_column", "")),
            normalize(record.get("field_id", "")),
        }
        candidates.update(normalize(name) for name in business_by_param.get(record.get("param_column"), set()))
        if selector_keys.intersection(candidates):
            matches.append(record)
    return matches


def flow_section(matches: list[dict], related_columns: list[dict], explanation_name: str) -> str:
    business_names = {name for record in matches for name in business_by_param(related_columns, record["param_column"])}
    field_title = ", ".join(sorted(business_names)) or matches[0]["param_column"]
    source_locators = sorted({
        mapping.get("source_locator", "")
        for mapping in related_columns
        if mapping.get("business_field") in business_names and mapping.get("source_locator")
    })
    source_label = ", ".join(source_locators) or "Ultracs source position"
    positions = ", ".join(str(record["ultracs_position"]) for record in matches)
    param_names = " + ".join(record["param_column"] for record in matches)
    snowflake_targets = sorted({
        f"{record['snowflake_table'].split(':')[-1]} · {record['snowflake_column']}"
        for record in matches
    })
    snowflake_label = "<br>".join(html.escape(value) for value in snowflake_targets)
    datatype_label = "<br>".join(sorted({
        f"{record['snowflake_column']}: {record.get('cdp', {}).get('data_type') or 'not declared'}"
        for record in matches
    }))
    inferred = any(record["confidence"] == "inferred" for record in matches)
    confidence_value = "inferred" if inferred else "confirmed"
    confidence_label = "INFERRED COMPOSITE MAPPING" if inferred else "CONFIRMED COLUMN MAPPING"
    confidence_label += f" · {confidence_percent(confidence_value)}% evidence"
    position_label = f"DWACC · position {positions}"
    notes = " ".join(record["notes"] for record in matches)
    flow = f'''<section class="lineage-explanation" aria-label="{html.escape(field_title)} end-to-end lineage">
    <div class="flow-heading"><span class="flow-kicker">FIELD PATH · {html.escape(field_title)}</span><span class="flow-confidence">{confidence_label}</span></div>
    <div class="flow-chain">
        <article class="flow-step"><span>01 · ULTRACS SOURCE</span><strong>{html.escape(source_label)}</strong><small>KWDW_ACC BASIC source fields</small></article>
        <span class="flow-arrow">→</span>
        <article class="flow-step"><span>02 · EXTRACT</span><strong>{html.escape(position_label)}</strong><small>Pipe-delimited DWACC record</small></article>
        <span class="flow-arrow">→</span>
        <article class="flow-step"><span>03 · HVR PARAM</span><strong>{html.escape(param_names)}</strong><small>DWACC.param column name(s)</small></article>
        <span class="flow-arrow inferred">⇢</span>
        <article class="flow-step"><span>04 · HVR S3 ROUTE</span><strong>ult_s3_acc1 → ult_s3_acc2</strong><small>Text → Parquet → HVR S3 · capture match inferred</small></article>
        <span class="flow-arrow">→</span>
        <article class="flow-step"><span>05 · ACCOUNT RAW</span><strong>ACCOUNTS_V1__ACCOUNTS</strong><small>Airflow: HVR S3 → Datalake S3 → RAW</small></article>
        <span class="flow-arrow">→</span>
        <article class="flow-step"><span>06 · SNOWFLAKE COLUMN</span><strong>{snowflake_label}</strong><small>Column mapping: {html.escape(field_title)}</small><small>Datatype: {datatype_label}</small></article>
    </div>
    <details class="branch-note"><summary>Separate direct-HVR route and evidence notes</summary><p><code>ult_sf_acc</code> lands matching DWACC rows in <code>LOADACCOUNTS_INGEST</code>, whose configured columns are <code>payload</code> and <code>integration_timestamp</code>. It does not define these named business columns, and no repository evidence connects that direct landing table to the accounts-v1 RAW relation. {html.escape(notes)}</p></details>
    <a class="explanation-link" href="{html.escape(explanation_name)}">Read the evidence and source paths</a>
</section>'''
    return flow


def business_by_param(related_columns: list[dict], param_name: str) -> set[str]:
    return {
        mapping.get("business_field", "")
        for mapping in related_columns
        if param_name == mapping.get("hvr_param_column") or param_name in mapping.get("hvr_param_columns", [])
    }


def build_explanation(matches: list[dict], field_title: str, related_columns: list[dict]) -> str:
    mapping_lines = []
    for record in matches:
        source = next((
            mapping.get("source_locator")
            for mapping in related_columns
            if record["param_column"] == mapping.get("hvr_param_column")
            or record["param_column"] in mapping.get("hvr_param_columns", [])
        ), "Not identified")
        mapping_lines.append(
            f"- `{source}` → DWACC position {record['ultracs_position']} `"
            f"{record['param_column']}` → `{record['snowflake_column']}` "
            f"in `{record['snowflake_table']}` (`{record['confidence']}`). {record['notes']}"
        )
    return "\n".join([
        f"# {field_title} Column Lineage",
        "",
        "## Field Mapping",
        "",
        *mapping_lines,
        "",
        "## End-to-End Route",
        "",
        "`KWDW_ACC` reads Ultracs ACCOUNT/TRAN records and writes the pipe-delimited DWACC extract. The HVR S3 route converts DWACC text to Parquet (`ult_s3_acc1`), then delivers it to HVR S3 (`ult_s3_acc2`). The account Airflow DAG copies files to Datalake S3 and loads `RAW.ACCOUNTS_V1__ACCOUNTS`. The dbt source resolves to that RAW relation; account dbt models expose the mapped public Snowflake columns.",
        "",
        "## Separate Branch and Caveats",
        "",
        "The direct `ult_sf_acc` HVR branch ends at `LOADACCOUNTS_INGEST`, which defines row `payload` and `integration_timestamp`, not these named business columns. No checked repository evidence connects that relation to the account RAW route. The filename-pattern association from DWACC to HVR capture is inferred; do not join the routes.",
        "",
        "Evidence is static repository configuration/source, not live HVR, Airflow, or Snowflake runtime state.",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate focused lineage outputs for any mapped DWACC column.")
    parser.add_argument(
        "--column",
        default=DEFAULT_SELECTOR,
        help="Case-insensitive .param name, Snowflake column, field_id, or business field (default: KiwiAcc).",
    )
    parser.add_argument(
        "--output-prefix",
        help="Optional output filename prefix, without extension. Defaults to account_number for KiwiAcc or a slug of --column.",
    )
    args = parser.parse_args()

    records = json.loads(COLUMN_INPUT.read_text(encoding="utf-8"))
    table_graph = describe_graph(json.loads(TABLE_INPUT.read_text(encoding="utf-8")))
    extract = next(
        node for node in table_graph["nodes"]
        if node["type"] == "EXTRACT_FILE" and node["properties"].get("name") == "DWACC"
    )
    related_columns = extract["properties"].get("related_columns", [])
    matches = choose_records(records, related_columns, args.column)
    if not matches:
        available = sorted({
            value
            for record in records
            for value in [record.get("param_column"), record.get("snowflake_column")]
            if value
        } | {mapping.get("business_field", "") for mapping in related_columns if mapping.get("business_field")})
        raise ValueError(f"No mapped column matches {args.column!r}. Available selectors: {', '.join(available)}")

    business_names = {name for record in matches for name in business_by_param(related_columns, record["param_column"])}
    field_title = ", ".join(sorted(business_names)) or args.column
    if normalize(field_title) == "accountid":
        field_title = "Account Number"
    prefix = args.output_prefix
    if not prefix:
        prefix = "account_number" if normalize(args.column) in {"kiwiacc", "accountnumber", "kiwibankaccountnumber", "accountid"} else normalize(field_title)
    if not prefix:
        raise ValueError("Could not create an output filename from the selected column; pass --output-prefix")
    json_output = OUTPUT_DIR / f"{prefix}_lineage.json"
    html_output = OUTPUT_DIR / f"{prefix}_lineage.html"
    explanation_output = OUTPUT_DIR / f"{prefix}_lineage_explanation.md"

    json_output.write_text(json.dumps(matches, indent=2) + "\n", encoding="utf-8")
    for node in table_graph["nodes"]:
        related = node.get("properties", {}).get("related_columns")
        if isinstance(related, list):
            node["properties"]["related_columns"] = [mapping for mapping in related if mapping.get("business_field") in business_names]

    embedded_table = json.dumps(table_graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    embedded_column = json.dumps(matches, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    enterprise_overview = describe_graph(build_enterprise_overview(matches))
    embedded_enterprise = json.dumps(enterprise_overview, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    html_text = HTML.replace("__TABLE_DATA__", embedded_table).replace("__COLUMN_DATA__", embedded_column).replace("__ENTERPRISE_DATA__", embedded_enterprise)
    html_text = html_text.replace("<title>DWACC Column Lineage</title>", f"<title>{html.escape(field_title)} Column Lineage</title>")
    html_text = html_text.replace("DWACC column lineage", f"{html.escape(field_title)} lineage")
    html_text = html_text.replace(
        "Ultracs → HVR Parquet → account Snowflake models",
        f"DWACC position(s) {', '.join(str(record['ultracs_position']) for record in matches)} → {html.escape(', '.join(record['snowflake_column'] for record in matches))}",
    )
    explanation_name = explanation_output.name
    html_text = html_text.replace("</style>", FLOW_STYLE + "\n</style>")
    html_text = html_text.replace("</header>\n<main>", "</header>\n" + flow_section(matches, related_columns, explanation_name) + "\n<main>")
    html_output.write_text(html_text, encoding="utf-8")

    if prefix != "account_number" or not explanation_output.exists():
        explanation_output.write_text(build_explanation(matches, field_title, related_columns), encoding="utf-8")
    print(f"Generated {json_output.relative_to(ROOT)}: {len(matches)} mapping(s) for {args.column}")
    print(f"Generated {html_output.relative_to(ROOT)}")
    if explanation_output.exists():
        print(f"Explanation: {explanation_output.relative_to(ROOT)}")
if __name__ == "__main__":
    main()
"""Create a focused JSON and interactive HTML view for account-number lineage."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT
from lineage_poc.viewers.graph._templates import read_template

import argparse
import html
import json
import re
from pathlib import Path

from lineage_poc.columns.dwacc import build_enterprise_overview, confidence_percent
from lineage_poc.graph.account import with_related_columns
from lineage_poc.viewers.graph.descriptions import describe_graph


ROOT = REPOSITORY_ROOT
OUTPUT_DIR = OUTPUT_ROOT / "lineage"
COLUMN_INPUT = REFERENCE_LINEAGE / "column_lineage.json"
TABLE_INPUT = REFERENCE_LINEAGE / "account_table_lineage.json"
ENTERPRISE_INPUT = REFERENCE_LINEAGE / "account_enterprise_lineage.json"
DEFAULT_SELECTOR = "KiwiAcc"

HTML = read_template("dwacc_html.html")
FLOW_STYLE = read_template('focused_flow_style.css')


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def selection_names(selector: str | list[str] | None) -> list[str]:
    if selector is None:
        return []
    values = [selector] if isinstance(selector, str) else selector
    if not isinstance(values, list) or not values:
        raise ValueError("Provide at least one column selector.")
    names, seen = [], set()
    for value in values:
        if not isinstance(value, str) or not normalize(value):
            raise ValueError("A column selector must contain letters or digits.")
        key = normalize(value)
        if key not in seen:
            names.append(value)
            seen.add(key)
    return names


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


def flow_section(matches: list[dict], related_columns: list[dict],
                 explanation_name: str | None = None) -> str:
    """Present each selected mapping separately; route listings are not serial proof."""
    if not matches:
        raise ValueError("A field path requires at least one selected mapping.")

    def escaped(value) -> str:
        return html.escape(str(value)) if value not in (None, "") else "Not supplied"

    paths = []
    for record in matches:
        source = record.get("ultracs", {})
        route = record.get("ingestion_route", {})
        extract = record["extract_file"]
        names = business_by_param(related_columns, record["param_column"])
        title = record.get("business_field") or ", ".join(sorted(names)) or record["param_column"]
        program = source.get("program") or record.get("ultracs_program")
        level = record.get("confidence")
        percent = confidence_percent(level)
        rating = f"{str(level or 'unspecified').replace('_', ' ').upper()} COLUMN MAPPING"
        rating += f" · {percent}% evidence" if percent is not None else " · Not rated"
        targets = record.get("dbt_targets", [])
        if record.get("snowflake_table") and record.get("snowflake_column"):
            primary = record["snowflake_table"].split(":")[-1] + " · " + record["snowflake_column"]
        else:
            primary = "\n".join(target["relation"].split(":")[-1] + " · " + target["column"]
                                for target in targets) or "No documented target"
        primary_type = record.get("cdp", {}).get("data_type") or "Not declared"
        datatype = (
            f"{record['snowflake_column']}: {primary_type}"
            if record.get("snowflake_column") else primary_type
        )
        channels = route.get("hvr_channels", [])
        steps = [
            ("01 · ULTRACS SOURCE", source.get("source_locator") or source.get("basic_expression"),
             [program, "Recorded BASIC: " + str(source.get("basic_expression") or "Not supplied")]),
            ("02 · EXTRACT", f"{extract} · position {record['ultracs_position']}",
             [f"Reported {extract} output slot"]),
            ("03 · HVR PARAM", record["param_column"], [record.get("source_path")]),
            ("04 · HVR S3 ROUTE", " / ".join(channels),
             ["Reported channels; extract capture association remains inferred"]),
            ("05 · ACCOUNT RAW" if extract == "DWACC" else "05 · RAW RELATION",
             str(route.get("raw_relation") or "Not supplied").split(":")[-1],
             [route.get("airflow_dag"), route.get("dbt_input")]),
            ("06 · SNOWFLAKE COLUMN", primary, [f"Datatype: {datatype}"]),
        ]
        chain = []
        for index, (heading, value, notes) in enumerate(steps):
            if index:
                inferred = index == 3
                chain.append(f'<span class="flow-arrow{" inferred" if inferred else ""}">'
                             + ("⇢" if inferred else "→") + "</span>")
            chain.append(
                '<article class="flow-step"><span>' + escaped(heading) + "</span><strong>"
                + escaped(value).replace("\n", "<br>") + "</strong>"
                + "".join("<small>" + escaped(note) + "</small>" for note in notes if note)
                + "</article>"
            )
        evidence = [
            ("BASIC source", source.get("source_path") or program),
            ("Reported BASIC line", source.get("basic_source_line")),
            ("HVR declaration", record.get("source_path")),
            ("Recorded mapping notes", record.get("notes")),
        ]
        evidence_html = "".join(
            "<li><strong>" + escaped(label) + ":</strong> <code>" + escaped(value)
            + "</code></li>" for label, value in evidence if value not in (None, "")
        )
        target_html = "".join(
            "<li>" + escaped(target.get("stage")) + " · <strong>"
            + escaped(target["relation"].split(":")[-1] + " · " + target["column"])
            + "</strong> · datatype: " + escaped(target.get("data_type"))
            + " · <code>" + escaped(target.get("source_expression") or target.get("projection_expression"))
            + "</code> · reported source: <code>" + escaped(target.get("source_path"))
            + "</code></li>" for target in targets
        )
        paths.append(
            '<section class="field-path" aria-label="' + escaped(title) + " · "
            + escaped(record["param_column"]) + ' end-to-end lineage">'
            + '<div class="flow-heading"><span class="flow-kicker">FIELD PATH · '
            + escaped(title) + ' · ' + escaped(record["param_column"])
            + '</span><span class="flow-confidence">' + escaped(rating) + "</span></div>"
            + '<div class="flow-chain">' + "\n".join(chain) + "</div>"
            + '<details class="branch-note"><summary>Evidence, source paths and all recorded targets'
            + "</summary><ul>" + evidence_html + "</ul><ul>" + target_html + "</ul></details></section>"
        )
    caveats = (
        "Arrows summarize reported stages, not production execution or independently verified "
        "physical source bindings. Channel listings do not establish serial execution. "
        "Mapping confidence is not an end-to-end probability."
    )
    if any(record["extract_file"] == "DWACC" for record in matches):
        caveats += (
            " The separate direct ult_sf_acc branch lands payload and integration_timestamp in "
            "LOADACCOUNTS_INGEST; no recorded evidence joins it to the accounts-v1 RAW route."
        )
    link = (f'<a class="explanation-link" href="{escaped(explanation_name)}">'
            "Read the evidence and source paths</a>") if explanation_name else ""
    return (
        '<section class="lineage-explanation" aria-label="Selected column field paths">'
        + "\n".join(paths)
        + '<details class="branch-note"><summary>Separate direct-HVR route and evidence notes</summary>'
        + "<p>" + escaped(caveats) + "</p></details>" + link + "</section>"
    )


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


def render(
    records: list[dict],
    table_graph: dict,
    enterprise_graph: dict,
    destination: Path,
    selector: str = DEFAULT_SELECTOR,
    output_prefix: str | None = None,
) -> dict:
    destination = Path(destination)
    table_graph = describe_graph(with_related_columns(table_graph, records))
    extract = next(
        node for node in table_graph["nodes"]
        if node["type"] == "EXTRACT_FILE" and node["properties"].get("name") == "DWACC"
    )
    related_columns = extract["properties"].get("related_columns", [])
    matches = choose_records(records, related_columns, selector)
    if not matches:
        available = sorted({
            value
            for record in records
            for value in [record.get("param_column"), record.get("snowflake_column")]
            if value
        } | {mapping.get("business_field", "") for mapping in related_columns if mapping.get("business_field")})
        raise ValueError(f"No mapped column matches {selector!r}. Available selectors: {', '.join(available)}")

    business_names = {name for record in matches for name in business_by_param(related_columns, record["param_column"])}
    field_title = ", ".join(sorted(business_names)) or selector
    if normalize(field_title) == "accountid":
        field_title = "Account Number"
    prefix = output_prefix
    if not prefix:
        prefix = "account_number" if normalize(selector) in {"kiwiacc", "accountnumber", "kiwibankaccountnumber", "accountid"} else normalize(field_title)
    if not prefix:
        raise ValueError("Could not create an output filename from the selected column; pass --output-prefix")
    if Path(prefix).name != prefix or prefix in {".", ".."} or "/" in prefix or "\\" in prefix:
        raise ValueError("Output prefix must be a filename, not a path.")
    destination.mkdir(parents=True, exist_ok=True)
    json_output = destination / f"{prefix}_lineage.json"
    html_output = destination / f"{prefix}_lineage.html"
    explanation_output = destination / f"{prefix}_lineage_explanation.md"

    json_output.write_text(json.dumps(matches, indent=2) + "\n", encoding="utf-8")
    for node in table_graph["nodes"]:
        related = node.get("properties", {}).get("related_columns")
        if isinstance(related, list):
            node["properties"]["related_columns"] = [mapping for mapping in related if mapping.get("business_field") in business_names]

    embedded_table = json.dumps(table_graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    embedded_column = json.dumps(matches, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    enterprise_overview = describe_graph(build_enterprise_overview(matches, graph=enterprise_graph))
    embedded_enterprise = json.dumps(enterprise_overview, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    html_text = HTML.replace("__TABLE_DATA__", embedded_table).replace("__COLUMN_DATA__", embedded_column).replace("__ENTERPRISE_DATA__", embedded_enterprise).replace("__DICTIONARY_DOCUMENT__", '""')
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

    explanation_output.write_text(build_explanation(matches, field_title, related_columns), encoding="utf-8")
    return {"selector": selector, "records": len(matches), "json": str(json_output), "html": str(html_output), "explanation": str(explanation_output)}


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--column", default=DEFAULT_SELECTOR)
    parser.add_argument("--output-prefix")
    parser.add_argument("--columns", type=Path, default=COLUMN_INPUT)
    parser.add_argument("--graph", type=Path, default=TABLE_INPUT)
    parser.add_argument("--enterprise-graph", type=Path, default=ENTERPRISE_INPUT)
    parser.add_argument("--destination", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    return render(
        json.loads(args.columns.read_text(encoding="utf-8")),
        json.loads(args.graph.read_text(encoding="utf-8")),
        json.loads(args.enterprise_graph.read_text(encoding="utf-8")),
        args.destination,
        selector=args.column,
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
"""Create a focused interactive HTML view for one DWREL column from the DWREL lineage JSON."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT
from lineage_poc.viewers.graph._templates import read_template

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from lineage_poc.columns.dwacc import CONFIDENCE_PERCENTAGES, confidence_percent
from lineage_poc.viewers.graph.descriptions import describe_graph

ROOT = REPOSITORY_ROOT
OUTPUT_DIR = OUTPUT_ROOT / "lineage"
COLUMN_INPUT = REFERENCE_LINEAGE / "dwrel_column_lineage.json"
GRAPH_INPUT = REFERENCE_LINEAGE / "dwrel_table_lineage.json"

HTML_TEMPLATE = read_template('dwrel_html_template.html')


def normalize(value: str) -> str:
  return re.sub(r"[^a-z0-9]+", "", value.casefold())


def choose_records(records: List[Dict[str, Any]], selector: str) -> List[Dict[str, Any]]:
  key = normalize(selector)
  matches = []
  for record in records:
    candidates = {normalize(record["param_column"]), normalize(record["field_id"])}
    candidates.update(normalize(target["column"]) for target in record["dbt_targets"])
    if key in candidates:
      matches.append(record)
  return matches


def _label(value: str | None) -> str:
  percent = confidence_percent(value)
  return f"{str(value or 'unspecified').replace('_', ' ')} · {percent}% evidence" if percent is not None else "Not rated"


def _short(relation: str) -> str:
  return relation.split(":")[-1]


def flow_section(records: List[Dict[str, Any]]) -> str:
  record = records[0]
  ultracs, route = record["ultracs"], record["ingestion_route"]
  internal = [t for t in record["dbt_targets"] if t["stage"] == "internal"]
  public = [t for t in record["dbt_targets"] if t["stage"] == "public"]

  def targets(items: List[Dict[str, Any]]) -> str:
    return "<br>".join(html.escape(f"{_short(item['relation'])} · {item['column']}") for item in items) or "No dbt projection found"

  files = ", ".join(sorted({item["file"] for item in ultracs.get("source_files", [])})) or "BASIC variables"
  steps = [
    ("01 · ULTRACS SOURCE", html.escape(ultracs.get("source_locator") or ultracs["basic_expression"]), f"KWDW_ACC line {ultracs['basic_source_line']} · reads {html.escape(files)}", False),
    ("02 · EXTRACT", html.escape(f"DWREL · position {record['ultracs_position']}"), "Pipe-delimited DWREL record, one row per related customer", False),
    ("03 · HVR PARAM", html.escape(record["param_column"]), "DWREL.param column name", False),
    ("04 · HVR S3 ROUTE", html.escape(" → ".join(route["hvr_channels"])), "Text → Parquet → HVR S3 · capture match inferred", True),
    ("05 · RELATIONSHIP RAW", html.escape(_short(route["raw_relation"])), "Airflow: HVR S3 → Datalake S3 → RAW", False),
    ("06 · INTERNAL DBT", targets(internal), "dbt unpacks DATA:" + html.escape(route["dbt_input"].split(":", 1)[1]), False),
    ("07 · PUBLIC DBT", targets(public), "Public projection of the internal column", False),
  ]
  chain = ""
  for index, (title, strong, small, inferred_arrow) in enumerate(steps):
    if index:
      chain += f'<span class="flow-arrow{" inferred" if inferred_arrow else ""}">{"⇢" if inferred_arrow else "→"}</span>\n'
    chain += f'<article class="flow-step"><span>{title}</span><strong>{strong}</strong><small>{small}</small></article>\n'

  hops = [
    ("BASIC field order → DWREL position", f"kb-ultracs-datawarehouse/KWDW_ACC line {ultracs['basic_source_line']}", record["confidence"]),
    ("`.param` column", record["source_path"], record["confidence"]),
    ("DWREL extract → HVR channel (capture pattern)", "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_rel1.json", "inferred"),
    ("Airflow HVR S3 → Datalake S3 → RAW", "kb-cdp-tenant-account/products/account-relationship-v1/airflow/account_relationship_v1/src/dags/account_relationship_v1_ingestion_v1.py", "explicit"),
  ]
  for target in record["dbt_targets"]:
    line = target.get("source_line") or target.get("projection_line")
    hops.append((f"{target['stage']} dbt · {_short(target['relation'])}.{target['column']}", f"{target['source_path']}" + (f" line {line}" if line else ""), "explicit"))
  rows = "".join(
    f"<tr><td>{html.escape(name)}</td><td>{html.escape(path)}</td><td>{html.escape(_label(level))}</td></tr>" for name, path, level in hops
  )
  branch = route["separate_direct_branch"]
  notes = [record["notes"]]
  if record["dbt_key_case_differences"]:
    notes.append("The dbt key spelling differs in case from the .param name; confirm the RAW key.")
  if not record["dbt_targets"]:
    notes.append("No account-relationship-v1 dbt model reads this column, so it has no Snowflake target.")
  notes.append(
    f"The direct {', '.join(branch['hvr_channels'])} branch lands in {', '.join(_short(item) for item in branch['landing_relations'])}; "
    f"its capture pattern {', '.join(branch['capture_patterns'])} does not match the DWREL{{HEAD}} output name, so it is not associated with this extract or joined to the RAW route."
  )
  notes.append("Percentages are heuristic evidence-strength scores, not probabilities. Evidence is static repository configuration and source, not live HVR, Airflow or Snowflake state.")
  notes_html = "".join(f"<li>{html.escape(note)}</li>" for note in notes)
  title = html.escape(", ".join(sorted({r["param_column"] for r in records})))
  return f'''<section class="lineage-explanation" aria-label="{title} end-to-end lineage">
<div class="flow-heading"><span class="flow-kicker">FIELD PATH · {title}</span><span class="flow-confidence">{html.escape(_label(record["confidence"]).upper())}</span></div>
<div class="flow-chain">
{chain}</div>
<details open><summary>Hop evidence and confidence</summary><table class="hops"><thead><tr><th>Hop</th><th>Source path</th><th>Confidence</th></tr></thead><tbody>{rows}</tbody></table></details>
<details><summary>Caveats and open questions</summary><ul class="notes">{notes_html}</ul></details>
</section>'''


def render(records: List[Dict[str, Any]], graph: Dict[str, Any], destination: Path, selector: str, output_prefix: str | None = None) -> dict:
  matches = choose_records(records, selector)
  if not matches:
    available = sorted({record["param_column"] for record in records} | {t["column"] for record in records for t in record["dbt_targets"]})
    raise ValueError(f"No DWREL column matches {selector!r}. Available selectors: {', '.join(available)}")
  graph = describe_graph(graph)
  prefix = output_prefix or "dwrel_" + normalize(matches[0]["param_column"])
  if Path(prefix).name != prefix or prefix in {".", ".."} or "/" in prefix or "\\" in prefix:
    raise ValueError("Output prefix must be a filename, not a path.")
  title = f"{', '.join(record['param_column'] for record in matches)} (DWREL)"
  columns = ", ".join(sorted({t["column"] for record in matches for t in record["dbt_targets"]})) or "no dbt projection"
  subtitle = f"DWREL position {', '.join(str(record['ultracs_position']) for record in matches)} → {columns}"

  def embed(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")

  text = (
    HTML_TEMPLATE.replace("__TITLE__", html.escape(title))
    .replace("__SUBTITLE__", html.escape(subtitle))
    .replace("__FLOW__", flow_section(matches))
    .replace("__GRAPH_DATA__", embed(graph))
    .replace("__COLUMN_DATA__", embed(matches))
    .replace("__PERCENTAGES__", embed(CONFIDENCE_PERCENTAGES))
  )
  destination = Path(destination)
  destination.mkdir(parents=True, exist_ok=True)
  output = destination / f"{prefix}_lineage.html"
  output.write_text(text, encoding="utf-8")
  return {"selector": selector, "records": len(matches), "html": str(output)}


def main(argv: list[str] | None = None) -> dict:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--column", required=True)
  parser.add_argument("--output-prefix")
  parser.add_argument("--columns", type=Path, default=COLUMN_INPUT)
  parser.add_argument("--graph", type=Path, default=GRAPH_INPUT)
  parser.add_argument("--destination", type=Path, default=OUTPUT_DIR)
  args = parser.parse_args(argv)
  return render(
    json.loads(args.columns.read_text(encoding="utf-8")),
    json.loads(args.graph.read_text(encoding="utf-8")),
    args.destination,
    args.column,
    output_prefix=args.output_prefix,
  )


if __name__ == "__main__":
  main()

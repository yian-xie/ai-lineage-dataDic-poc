#!/usr/bin/env python3
"""Generate DWREL column lineage and its table-level slice, separate from the DWACC inventory."""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from lineage.parsers import parse_airflow_dag, parse_dbt_project, parse_schemachange_file
from lineage.parsers.hvr import parse_hvr_param
from generate_column_lineage import _dbt_data_projections, _selected_sql_projections
from generate_full_parser_lineage import GraphAccumulator, scan_instruction_like_content

OUTPUT_DIR = ROOT / "output"
FULL_GRAPH_PATH = OUTPUT_DIR / "table_lineage.json"
COLUMN_OUTPUT = OUTPUT_DIR / "dwrel_column_lineage.json"
GRAPH_OUTPUT = OUTPUT_DIR / "dwrel_table_lineage.json"
PROGRAM_PATH = "kb-ultracs-datawarehouse/KWDW_ACC"
PARAM_SOURCE_PATH = "kb-cdp-hvr/hvr-config/scripts/DWREL.param"
EXTRACT_NAME = "DWREL"
PRODUCT_PATH = "kb-cdp-tenant-account/products/account-relationship-v1"
DAG_PATH = f"{PRODUCT_PATH}/airflow/account_relationship_v1/src/dags/account_relationship_v1_ingestion_v1.py"
RAW_RELATION = "snowflake:relation:RAW.ACCOUNT_RELATIONSHIP_V1__RELATIONSHIPS"
# Internal model -> public model that selects from it.
DBT_MODEL_PAIRS = (
  ("account_relationship_v1__customer_account_relationship_v1", "account_relationship_v1__customer_account_relationship"),
  ("v_account_relationship_v1__accrelationship_v1", "vw_account_relationship_v1__accrelationship_v1"),
)
COMMENT_PATTERN = re.compile(r";\s*\*")


def _split_unquoted(text: str, separator: str) -> List[str]:
  parts, current, quote = [], [], None
  for character in text:
    if quote:
      current.append(character)
      if character == quote:
        quote = None
    elif character in "\"'":
      quote = character
      current.append(character)
    elif character == separator:
      parts.append("".join(current))
      current = []
    else:
      current.append(character)
  parts.append("".join(current))
  return parts


def _basic_dwrel_fields() -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
  lines = (WORKSPACE_ROOT / PROGRAM_PATH).read_text(encoding="utf-8", errors="replace").splitlines()
  start = next((i for i, line in enumerate(lines) if re.match(r"\s*LINE2\s*=\s*CIS\b", line, re.IGNORECASE)), None)
  if start is None:
    raise ValueError(f"{PROGRAM_PATH}: the LINE2=CIS record start was not found")
  end = next((i for i in range(start, len(lines)) if re.search(r"WRITESEQ\s+LINE2\s+ON\s+DWREL", lines[i], re.IGNORECASE)), None)
  if end is None:
    raise ValueError(f"{PROGRAM_PATH}: WRITESEQ LINE2 ON DWREL was not found after the record start")

  fields: List[Dict[str, Any]] = []
  if_condition = None
  in_else = False
  pending_empty_when = None
  for index in range(start, end):
    comment_match = COMMENT_PATTERN.search(lines[index])
    code = (lines[index][:comment_match.start()] if comment_match else lines[index]).strip()
    comment = lines[index][comment_match.end():].strip() if comment_match else ""
    number = index + 1
    if not code or code.startswith("*"):
      continue
    inline_if = re.match(r"IF\s+(.*?)\s+THEN\s+LINE2\s*=\s*LINE2\s*:\s*(.*)$", code, re.IGNORECASE)
    if inline_if:
      if not fields:
        raise ValueError(f"{PROGRAM_PATH}:{number}: conditional append has no preceding field")
      fields[-1]["continuations"].append({
        "condition": inline_if.group(1).strip(),
        "expression": inline_if.group(2).strip(),
        "source_line": number,
      })
      continue
    block_if = re.match(r"IF\s+(.*?)\s+THEN\s*$", code, re.IGNORECASE)
    if block_if:
      if_condition, in_else, pending_empty_when = block_if.group(1).strip(), False, None
      continue
    if re.match(r"END\s+ELSE\s*$", code, re.IGNORECASE):
      in_else = True
      continue
    if re.match(r"END\s*$", code, re.IGNORECASE):
      if_condition, in_else, pending_empty_when = None, False, None
      continue
    assignment = re.match(r"LINE2\s*=\s*(.*)$", code, re.IGNORECASE)
    if not assignment:
      continue
    right_side = assignment.group(1).strip()
    continuation = re.match(r"LINE2\s*:\s*(.*)$", right_side, re.IGNORECASE)
    if continuation:
      right_side = continuation.group(1)
    groups: List[List[str]] = [[]]
    for token in (part.strip() for part in _split_unquoted(right_side, ":")):
      if token.upper() == "SEP":
        groups.append([])
      else:
        groups[-1].append(token)
    if continuation:
      if groups[0]:
        raise ValueError(f"{PROGRAM_PATH}:{number}: continuation does not start with a separator")
      groups = groups[1:]
    for group in groups:
      expression = ":".join(group)
      if not expression and if_condition and not in_else:
        pending_empty_when = if_condition
        continue
      field = {
        "expression": expression,
        "comment": comment if len(groups) == 1 else "",
        "source_line": number,
        "continuations": [],
      }
      if pending_empty_when and in_else:
        field["empty_when"] = pending_empty_when
        pending_empty_when = None
      fields.append(field)

  reads: Dict[str, Dict[str, Any]] = {}
  for index, line in enumerate(lines):
    match = re.match(r"\s*(?:\d+:\s*)?READ\s+(\w+)\s+FROM\s+([A-Za-z0-9_.]+)", line, re.IGNORECASE)
    if match and match.group(1).upper() not in reads:
      reads[match.group(1).upper()] = {"file": match.group(2), "source_line": index + 1}

  definitions: Dict[str, List[Dict[str, Any]]] = {}
  for name in ("CIS", "PID"):
    for index in range(start):
      match = re.match(rf"\s*(?:\d+:\s*)?(?:IF\s+.*?\s+THEN\s+)?{name}\s*=\s*(.+?)\s*(?:;\s*\*.*)?$", lines[index])
      if match:
        definitions.setdefault(name, []).append({"source_line": index + 1, "text": f"{name} = {match.group(1)}"})
  return fields, reads, definitions


def _param_columns() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
  path = WORKSPACE_ROOT / PARAM_SOURCE_PATH
  flags = scan_instruction_like_content([path])
  parsed = parse_hvr_param(path)
  columns = [
    {key: value for key, value in node.properties.items() if key not in {"source_path", "confidence"}}
    for node in parsed.nodes
    if node.label == "HVR_COLUMN"
  ]
  return columns, flags


def _yaml_documents(path: Path) -> Dict[str, Any]:
  text = "\n".join(line.rstrip("\t") for line in path.read_text(encoding="utf-8").splitlines())
  return yaml.safe_load(text) or {}


def _model_paths(model: str, stage: str) -> Tuple[Path, Path]:
  folder = WORKSPACE_ROOT / PRODUCT_PATH / "dbt/models" / stage / model
  return folder / f"{model}.sql", folder / f"{model}.yml"


def _relative(path: Path) -> str:
  return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()


def _column_metadata(model: str, stage: str) -> Dict[str, Dict[str, Any]]:
  _, schema_path = _model_paths(model, stage)
  metadata = {}
  for document_model in _yaml_documents(schema_path).get("models", []) or []:
    if document_model.get("name") != model:
      continue
    for column in document_model.get("columns", []) or []:
      name = str(column.get("name", "")).upper()
      if name:
        metadata[name] = {
          "model_description": document_model.get("description", ""),
          "description": column.get("description", ""),
          "data_type": column.get("data_type", ""),
          "classification": (column.get("meta") or {}).get("CLASSIFICATION", ""),
          "schema_source_path": _relative(schema_path),
        }
  return metadata


def _dbt_context() -> Tuple[Dict[str, str], Dict[str, str]]:
  graph = parse_dbt_project(WORKSPACE_ROOT / PRODUCT_PATH / "dbt")
  model_ids = {node.properties.get("name"): node.id for node in graph.nodes if node.label == "DBT_MODEL"}
  relation_by_model_id = {edge.source: edge.target for edge in graph.edges if edge.type == "MATERIALIZES_AS"}
  relations = {name: relation_by_model_id[model_id] for name, model_id in model_ids.items() if model_id in relation_by_model_id}
  return model_ids, relations


def _route(graph: Dict[str, Any], full_graph: Dict[str, Any]) -> Dict[str, Any]:
  edges = graph["edges"]
  channels = [node for node in graph["nodes"] if node["type"] == "HVR_CHANNEL"]
  s3_channels = sorted(node["properties"].get("name", node["id"]) for node in channels)
  tasks = sorted(
    node["properties"].get("task_id", node["id"].rsplit(":", 1)[-1])
    for node in graph["nodes"]
    if node["type"] == "AIRFLOW_TASK" and "dwrel" in node["id"]
  )
  dag = next((node["properties"].get("name", node["id"]) for node in graph["nodes"] if node["type"] == "AIRFLOW_DAG"), None)
  s3_paths = sorted(node["id"] for node in graph["nodes"] if node["type"] == "S3_PATH")
  carried = {edge["target"] for edge in edges if edge["type"] == "CARRIED_BY"}
  landings = {edge["source"]: edge["target"] for edge in full_graph["edges"] if edge["type"] == "LANDS_IN"}
  direct = [
    node for node in full_graph["nodes"]
    if node["type"] == "HVR_CHANNEL" and node["id"] in landings
    and any(EXTRACT_NAME.casefold() in str(pattern).casefold() for pattern in node["properties"].get("capture_patterns") or [])
  ]
  return {
    "hvr_channels": s3_channels,
    "s3_paths": s3_paths,
    "airflow_dag": dag,
    "airflow_tasks": tasks,
    "raw_relation": RAW_RELATION,
    "separate_direct_branch": {
      "hvr_channels": sorted(node["properties"].get("name", node["id"]) for node in direct),
      "capture_patterns": sorted({pattern for node in direct for pattern in node["properties"].get("capture_patterns", [])}),
      "landing_relations": sorted({landings[node["id"]] for node in direct}),
      "associated_with_extract_by_capture_pattern": any(node["id"] in carried for node in direct),
      "joined_to_raw_relation": False,
    },
  }


def build_graph(full_graph: Dict[str, Any] | None = None) -> Dict[str, Any]:
  if full_graph is None:
    full_graph = json.loads(FULL_GRAPH_PATH.read_text(encoding="utf-8"))
  by_id = {node["id"]: node for node in full_graph["nodes"]}
  extract = next(
    (
      node for node in full_graph["nodes"]
      if node["type"] == "EXTRACT_FILE"
      and node["properties"].get("source_path") == PROGRAM_PATH
      and EXTRACT_NAME in str(node["properties"].get("output_path", node["id"]))
    ),
    None,
  )
  if extract is None:
    raise ValueError(f"{EXTRACT_NAME} extract written by {PROGRAM_PATH} is missing from the full graph")
  _, reads, _ = _basic_dwrel_fields()
  selected = {extract["id"]}
  program_ids = {edge["source"] for edge in full_graph["edges"] if edge["type"] == "WRITES_TO" and edge["target"] == extract["id"]}
  selected |= program_ids
  for variable in ("AREC", "EREC"):
    file_id = f"basic:file:{reads[variable]['file']}" if variable in reads else None
    if file_id and file_id in by_id:
      selected.add(file_id)
  carried = {edge["target"] for edge in full_graph["edges"] if edge["type"] == "CARRIED_BY" and edge["source"] == extract["id"]}
  integrated = {edge["target"] for edge in full_graph["edges"] if edge["type"] == "INTEGRATES_TO" and edge["source"] in carried}
  channels = set(carried) | {
    edge["source"] for edge in full_graph["edges"]
    if edge["type"] == "CAPTURES_FROM" and edge["target"] in integrated
    and any(
      EXTRACT_NAME.casefold() in str(pattern).casefold()
      for pattern in (by_id[edge["source"]]["properties"].get("capture_patterns") or [by_id[edge["source"]]["properties"].get("capture_pattern", "")])
    )
  }
  selected |= channels
  for edge in full_graph["edges"]:
    if edge["source"] in channels and edge["type"] in {"CAPTURES_FROM", "INTEGRATES_TO", "COPIES_TO", "LANDS_IN"}:
      selected.add(edge["target"])

  accumulator = GraphAccumulator()
  for node in full_graph["nodes"]:
    if node["id"] in selected:
      accumulator.nodes[node["id"]] = {"id": node["id"], "type": node["type"], "properties": json.loads(json.dumps(node["properties"]))}
  for edge in full_graph["edges"]:
    if edge["source"] in selected and edge["target"] in selected:
      accumulator.edges[(edge["source"], edge["target"], edge["type"])] = json.loads(json.dumps(edge))

  product = WORKSPACE_ROOT / PRODUCT_PATH
  accumulator.add_graph(parse_airflow_dag(WORKSPACE_ROOT / DAG_PATH))
  accumulator.add_graph(parse_dbt_project(product / "dbt"))
  for key in [key for key, node in accumulator.nodes.items() if node["type"] == "AIRFLOW_TASK" and "dwrel" not in key and "run_dbt_bash" not in key]:
    del accumulator.nodes[key]
  for key in [key for key in accumulator.edges if key[0] not in accumulator.nodes or key[1] not in accumulator.nodes]:
    del accumulator.edges[key]
  for script in sorted((product / "schemachange/scripts").glob("*.sql")):
    migration = parse_schemachange_file(script)
    migration_edges = [edge for edge in migration.edges if edge.type == "MIGRATES"]
    if any(f"{edge.target}" in accumulator.nodes for edge in migration_edges):
      accumulator.add_graph(migration)
  for key in [key for key, node in accumulator.nodes.items() if node["type"] == "SNOWFLAKE_RELATION" and not any(key in edge_key[:2] for edge_key in accumulator.edges)]:
    del accumulator.nodes[key]
  for key in [key for key in accumulator.edges if key[0] not in accumulator.nodes or key[1] not in accumulator.nodes]:
    del accumulator.edges[key]

  scanned = [WORKSPACE_ROOT / PARAM_SOURCE_PATH, WORKSPACE_ROOT / PROGRAM_PATH, WORKSPACE_ROOT / DAG_PATH]
  scanned += sorted(path for pattern in ("*.sql", "*.yml") for path in (product / "dbt/models").rglob(pattern))
  payload = accumulator.payload()
  payload["gap_register"] = [
    {
      "id": "direct-branch-boundary",
      "summary": "The direct ult_sf_rel branch lands in LOADRELATIONSHIPS_INGEST; no checked evidence joins it to the account-relationship RAW route.",
    },
    {
      "id": "direct-branch-not-associated",
      "summary": "ult_sf_rel captures DWREL.TXT, which does not match the DWREL{HEAD} output name (DWREL01A.TXT), so the graph has no CARRIED_BY edge from the KWDW_ACC extract to it and it is excluded from this slice.",
    },
    {
      "id": "dwrel-capture-inferred",
      "summary": "The DWREL extract to ult_s3_rel1 association is inferred from the Capture.Pattern filename match.",
    },
    {
      "id": "hvr-s3-join-by-location",
      "summary": "ult_s3_rel2 is included through the shared HVR location it captures from; the stored edge points from the channel to the location, so a stored-direction walk does not continue past that location.",
    },
  ]
  payload["input_flags"] = scan_instruction_like_content(scanned)
  return payload


def build_records(graph: Dict[str, Any] | None = None, full_graph: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
  if full_graph is None:
    full_graph = json.loads(FULL_GRAPH_PATH.read_text(encoding="utf-8"))
  if graph is None:
    graph = build_graph(full_graph)
  parameters, _ = _param_columns()
  fields, reads, definitions = _basic_dwrel_fields()
  if len(fields) != len(parameters):
    raise ValueError(f"DWREL output count ({len(fields)}) does not match HVR parameters ({len(parameters)})")

  model_ids, relations = _dbt_context()
  route = _route(graph, full_graph)
  metadata: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}
  projections: Dict[str, List[Dict[str, Any]]] = {}
  public_projections: Dict[str, Dict[str, Dict[str, Any]]] = {}
  for internal, public in DBT_MODEL_PAIRS:
    internal_sql, _ = _model_paths(internal, "internal")
    public_sql, _ = _model_paths(public, "public")
    metadata[(internal, "internal")] = _column_metadata(internal, "internal")
    metadata[(public, "public")] = _column_metadata(public, "public")
    projections[internal] = _dbt_data_projections(internal_sql)
    public_projections[public] = _selected_sql_projections(public_sql)

  records = []
  for position, (parameter, basic) in enumerate(zip(parameters, fields), start=1):
    param_name = parameter["name"]
    expressions = [basic["expression"]] + [item["expression"] for item in basic["continuations"]]
    references = list(dict.fromkeys(
      reference for expression in expressions
      for reference in re.findall(r"\b(?:EREC|AREC|REC)\s*<[^>]+>", expression, re.IGNORECASE)
    ))
    variables = [name for name in ("CIS", "PID") if re.fullmatch(name, basic["expression"], re.IGNORECASE)]
    source_files = [
      {"variable": variable, **reads[variable]}
      for variable in dict.fromkeys(re.match(r"[A-Za-z]+", reference).group(0).upper() for reference in references)
      if variable in reads
    ]
    transformation = basic["expression"]
    if basic.get("empty_when"):
      transformation = f"Empty when {basic['empty_when']}; otherwise {basic['expression']}"
    for item in basic["continuations"]:
      transformation += f"; appends {item['expression']} when {item['condition']}"

    dbt_targets: List[Dict[str, Any]] = []
    dbt_keys: List[str] = []
    case_differences = []
    for internal, public in DBT_MODEL_PAIRS:
      internal_sql, _ = _model_paths(internal, "internal")
      public_sql, _ = _model_paths(public, "public")
      for projection in projections[internal]:
        if projection["source_column"].casefold() != param_name.casefold():
          continue
        column = projection["target_column"]
        dbt_keys.append(projection["source_column"])
        if projection["source_column"] != param_name:
          case_differences.append({
            "param_column": param_name,
            "dbt_key": projection["source_column"],
            "model": internal,
            "source_path": _relative(internal_sql),
            "source_line": projection["source_line"],
          })
        dbt_targets.append({
          "stage": "internal",
          "model": internal,
          "model_id": model_ids[internal],
          "relation": relations[internal],
          "column": column,
          "source_expression": projection["source_expression"],
          "source_path": _relative(internal_sql),
          "source_line": projection["source_line"],
          **metadata[(internal, "internal")].get(column, {}),
        })
        if column in public_projections[public]:
          dbt_targets.append({
            "stage": "public",
            "model": public,
            "model_id": model_ids[public],
            "relation": relations[public],
            "column": column,
            "source_model": internal,
            "source_column": column,
            "projection_expression": public_projections[public][column]["source_expression"],
            "projection_line": public_projections[public][column]["source_line"],
            "source_path": _relative(public_sql),
            **metadata[(public, "public")].get(column, {}),
          })

    primary = next((target for target in dbt_targets if target["stage"] == "public"), dbt_targets[0] if dbt_targets else None)
    notes = (
      f"KWDW_ACC writes {basic['expression']} to DWREL position {position} by field order; "
      f"DWREL.param names it {param_name}; "
    )
    if dbt_targets:
      notes += f"dbt reads DATA:{dbt_keys[0]}."
    else:
      notes += "no account-relationship-v1 dbt model reads it."
    if case_differences:
      notes += (
        f" dbt key {case_differences[0]['dbt_key']} differs in case from the .param name; "
        "Snowflake VARIANT key lookup is case-sensitive, so confirm the RAW key."
      )
    ultracs = {
      "program": PROGRAM_PATH,
      "source_path": PROGRAM_PATH,
      "source_locator": " + ".join(references) if references else None,
      "source_references": references,
      "source_files": source_files,
      "variable_definitions": [item for name in variables for item in definitions.get(name, [])],
      "description": basic["comment"],
      "transformation": transformation,
      "basic_expression": basic["expression"],
      "basic_comment": basic["comment"],
      "basic_source_line": basic["source_line"],
      "conditional_continuations": basic["continuations"],
      "extract_file": EXTRACT_NAME,
      "position": position,
      "param_column": param_name,
    }
    cdp = {}
    if primary:
      cdp = {
        "model": primary["model"],
        "model_description": primary.get("model_description", ""),
        "description": primary.get("description", ""),
        "data_type": primary.get("data_type", ""),
        "classification": primary.get("classification", ""),
        "source_path": primary.get("schema_source_path", ""),
        "table": primary["relation"],
        "column": primary["column"],
        "stage": primary["stage"],
      }
    records.append({
      "business_field": param_name,
      "field_id": f"ultracs:ACCOUNT_RELATIONSHIP:{EXTRACT_NAME}:{position}",
      "ultracs_position": position,
      "ultracs_program": PROGRAM_PATH,
      "extract_file": EXTRACT_NAME,
      "param_column": param_name,
      "hvr_parameter": dict(parameter),
      "snowflake_table": primary["relation"] if primary else None,
      "snowflake_column": primary["column"] if primary else None,
      "confidence": "inferred",
      "source_path": PARAM_SOURCE_PATH,
      "notes": notes,
      "dbt_mapping_status": "mapped" if dbt_targets else "no_dbt_projection_found",
      "dbt_key_case_differences": case_differences,
      "ultracs": ultracs,
      "cdp": cdp,
      "dbt_targets": dbt_targets,
      "ingestion_route": {**route, "dbt_input": f"DATA:{case_differences[0]['dbt_key'] if case_differences else param_name}"},
    })
  return records


def main() -> None:
  full_graph = json.loads(FULL_GRAPH_PATH.read_text(encoding="utf-8"))
  graph = build_graph(full_graph)
  records = build_records(graph, full_graph)
  COLUMN_OUTPUT.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
  GRAPH_OUTPUT.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
  unmapped = [record["param_column"] for record in records if not record["dbt_targets"]]
  print(f"Generated {COLUMN_OUTPUT.relative_to(ROOT)}: {len(records)} DWREL column mappings ({len(unmapped)} without a dbt projection)")
  print(f"Generated {GRAPH_OUTPUT.relative_to(ROOT)}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, {len(graph['input_flags'])} input flags")


if __name__ == "__main__":
  main()

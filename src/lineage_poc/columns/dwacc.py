"""Generate evidence-backed DWACC column lineage JSON and an interactive vis.js graph."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT, source_root as default_source_root
from lineage_poc.viewers.graph._templates import read_template

import base64
import gzip
import hashlib
import json
import os
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = REPOSITORY_ROOT
OUTPUT_DIR = OUTPUT_ROOT / "lineage"
PARAM_PATH = REFERENCE_LINEAGE / "hvr_param_metadata.json"
TABLE_GRAPH_PATH = REFERENCE_LINEAGE / "account_table_lineage.json"
ENTERPRISE_GRAPH_PATH = REFERENCE_LINEAGE / "account_enterprise_lineage.json"
JSON_OUTPUT = OUTPUT_DIR / "column_lineage.json"
HTML_OUTPUT = OUTPUT_DIR / "column_lineage.html"
PROGRAM_PATH = "kb-ultracs-datawarehouse/KWDW_ACC"
PARAM_SOURCE_PATH = "kb-cdp-hvr/hvr-config/scripts/DWACC.param"
EXTRACT_NAME = "DWACC"
DETAIL_TABLE = "snowflake:relation:PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL"
BALANCE_TABLE = "snowflake:relation:PUBLIC.ACCOUNTS_V1__ULTRACS_ACCOUNTS_EOD_BALANCES"
CONFIDENCE_PERCENTAGES = {
  "explicit": 95,
  "confirmed": 95,
  "confirmed_calculated": 90,
  "declared_source": 85,
  "inferred": 60,
  "unconfirmed": 50,
}
CDP_SCHEMA_PATHS = {
  "snowflake:relation:INTERNAL.ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL_V2": Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/internal/accounts_v1__ultracs_accounts_detail_v2/accounts_v1__ultracs_accounts_detail_v2.yml"),
  "snowflake:relation:INTERNAL.ACCOUNTS_V1__ULTRACS_ACCOUNTS_EOD_BALANCES_V2": Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/internal/accounts_v1__ultracs_accounts_eod_balances_v2/accounts_v1__ultracs_accounts_eod_balances_v2.yml"),
  DETAIL_TABLE: Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/public/accounts_v1__ultracs_accounts_detail/accounts_v1__ultracs_accounts_detail.yml"),
  BALANCE_TABLE: Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/public/accounts_v1__ultracs_accounts_eod_balances/accounts_v1__ultracs_accounts_eod_balances.yml"),
}
ACCOUNT_MODEL_CONFIGS = (
  {
    "name": "accounts_v1__ultracs_accounts_detail_v2",
    "sql": Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/internal/accounts_v1__ultracs_accounts_detail_v2/accounts_v1__ultracs_accounts_detail_v2.sql"),
    "public_name": "accounts_v1__ultracs_accounts_detail",
    "public_sql": Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/public/accounts_v1__ultracs_accounts_detail/accounts_v1__ultracs_accounts_detail.sql"),
    "public_relation": DETAIL_TABLE,
  },
  {
    "name": "accounts_v1__ultracs_accounts_eod_balances_v2",
    "sql": Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/internal/accounts_v1__ultracs_accounts_eod_balances_v2/accounts_v1__ultracs_accounts_eod_balances_v2.sql"),
    "public_name": "accounts_v1__ultracs_accounts_eod_balances",
    "public_sql": Path("kb-cdp-tenant-account/products/accounts-v1/dbt/models/public/accounts_v1__ultracs_accounts_eod_balances/accounts_v1__ultracs_accounts_eod_balances.sql"),
    "public_relation": BALANCE_TABLE,
  },
)


def confidence_percent(value: str | None) -> int | None:
  return CONFIDENCE_PERCENTAGES.get(str(value or "").lower())


ULTRACS_FIELD_DETAILS = {
  "OpenDate": {"source_locator": "ACCOUNT<1>", "description": "Account record attribute 1 is the account opening date.", "transformation": "OCONV(AREC<1>, 'D4')"},
  "AccountName": {"source_locator": "ACCOUNT<28,2>", "description": "Account name from the ACCOUNT record; the BASIC comment says it includes the suffix.", "transformation": "Direct output from AREC<28,2>."},
  "NumOfSignaturesReq": {"source_locator": "TRAN<4,4>", "description": "Number of signatures required for transactions on the account.", "transformation": "If REC<4,4> is zero, output 1; otherwise output REC<4,4>."},
  "Account": {"source_locator": "ACCOUNT @ID", "description": "CIS component parsed from the account identifier; candidate part of Account_Index_ID.", "transformation": "CIS = FIELD(NID, 'S', 1), with legacy fallbacks."},
  "Prod": {"source_locator": "ACCOUNT @ID", "description": "PID/product component parsed from the account identifier; candidate part of Account_Index_ID.", "transformation": "PID = ID[LEN(CIS)+1,9]."},
  "KiwiAcc": {"source_locator": "TRAN<4,8>", "description": "Kiwibank account ID, as identified by the KWDW_ACC BASIC comment.", "transformation": "Direct output from REC<4,8>."},
  "AltAccountName": {"source_locator": "TRAN<4,2>", "description": "Alternative account name from transaction record attribute 4, subvalue 2.", "transformation": "Direct output from REC<4,2>."},
  "Balance": {"source_locator": "TRAN<1> and transaction detail", "description": "End-of-day account balance after applicable transaction adjustments.", "transformation": "Starts from REC<1> and applies post-run-date transaction adjustments."},
}

HTML = read_template('dwacc_html.html')


def _dwacc_output_fields(source_root: Path | None = None) -> List[Dict[str, str]]:
  workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
  program_path = workspace_root / PROGRAM_PATH
  source = program_path.read_text(encoding="utf-8", errors="replace")
  body = source.split("WRITESEQ LINE ON DWACC", 1)[0]
  fields = []
  separator = re.compile(r"\s*:\s*SEP\s*:\s*", re.IGNORECASE)
  for line_number, line in enumerate(body.splitlines(), start=1):
    code, _, comment = re.split(r";\s*\*", line, maxsplit=1) + [""] if re.search(r";\s*\*", line) else (line, "", "")
    match = re.match(r"^\s*LINE\s*=\s*(.*?)\s*$", code, re.IGNORECASE)
    if not match:
      continue
    expression = match.group(1).strip()
    parts = [part.strip() for part in separator.split(expression) if part.strip()]
    if parts and parts[0].upper() == "LINE":
      parts = parts[1:]
    for part in parts:
      fields.append({
        "expression": part,
        "comment": comment.strip(),
        "source_line": line_number,
      })
  return fields


def _dbt_data_projections(path: Path) -> List[Dict[str, str]]:
  projections = []
  for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
    source = re.search(r"DATA:([A-Za-z_][A-Za-z0-9_]*)", line, re.IGNORECASE)
    target = re.search(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*,?\s*$", line, re.IGNORECASE)
    if source and target:
      projections.append({
        "source_column": source.group(1),
        "target_column": target.group(1).upper(),
        "source_expression": line.strip(),
        "source_line": line_number,
      })
  return projections


def _selected_sql_columns(path: Path) -> set[str]:
  sql = path.read_text(encoding="utf-8")
  select = sql.split("SELECT", 1)[1].split("FROM", 1)[0]
  return {
    token.upper()
    for line in select.splitlines()
    if (token := line.strip().rstrip(","))
    and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token)
  }


def _selected_sql_projections(path: Path) -> Dict[str, Dict[str, Any]]:
  sql = path.read_text(encoding="utf-8")
  select = sql.split("SELECT", 1)[1].split("FROM", 1)[0]
  start_line = sql[:sql.index(select)].count("\n") + 1
  projections = {}
  for offset, line in enumerate(select.splitlines()):
    token = line.strip().rstrip(",")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
      projections[token.upper()] = {
        "source_expression": token,
        "source_line": start_line + offset,
      }
  return projections


def _model_relations(table_graph: Dict[str, Any]) -> Dict[str, str]:
  models = {
    node.get("properties", {}).get("name"): node["id"]
    for node in table_graph.get("nodes", [])
    if node.get("type") == "DBT_MODEL"
  }
  relations = {
    edge["source"]: edge["target"]
    for edge in table_graph.get("edges", [])
    if edge.get("type") == "MATERIALIZES_AS"
  }
  return {
    name: relations[model_id]
    for name, model_id in models.items()
    if name and model_id in relations
  }


def _mapping_overrides() -> Dict[str, Dict[str, str]]:
  return {
    "OpenDate": {"business_field": "Account_Opened_Date", "confidence": "confirmed"},
    "AccountName": {"business_field": "Account_Name", "confidence": "confirmed"},
    "NumOfSignaturesReq": {"business_field": "Signatory_Count", "confidence": "confirmed"},
    "Account": {"business_field": "Account_Index_ID", "confidence": "inferred", "notes": "Candidate composite key part 1 of 2: Account at DWACC position 1 represents CIS. Confirm the consumer key definition."},
    "Prod": {"business_field": "Account_Index_ID", "confidence": "inferred", "notes": "Candidate composite key part 2 of 2: Prod at DWACC position 2 represents PID. Confirm the consumer key definition."},
    "KiwiAcc": {"business_field": "Account_ID", "confidence": "confirmed"},
    "AltAccountName": {"business_field": "Alternative_Account_Name", "confidence": "confirmed"},
    "Balance": {"business_field": "Balance", "confidence": "confirmed_calculated"},
  }


def build_records(
  table_graph: Dict[str, Any] | None = None,
  param_data: Dict[str, Any] | None = None,
  source_root: Path | None = None,
) -> List[Dict[str, Any]]:
  workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
  if param_data is None:
    param_data = json.loads(PARAM_PATH.read_text(encoding="utf-8"))
  if table_graph is None:
    table_graph = json.loads(TABLE_GRAPH_PATH.read_text(encoding="utf-8"))
  parameters = param_data["columns"]
  output_fields = _dwacc_output_fields(source_root=workspace_root)
  if len(output_fields) != len(parameters):
    raise ValueError(
      f"DWACC output count ({len(output_fields)}) does not match HVR parameters ({len(parameters)})"
    )

  relation_by_model = _model_relations(table_graph)
  cdp_columns = load_cdp_column_metadata(source_root=workspace_root)
  models = {
    node.get("properties", {}).get("name"): node
    for node in table_graph.get("nodes", [])
    if node.get("type") == "DBT_MODEL"
  }
  overrides = _mapping_overrides()
  records = []

  for position, (parameter, basic) in enumerate(zip(parameters, output_fields), start=1):
    param_name = parameter["name"]
    basic_expression = basic["expression"]
    source_references = list(dict.fromkeys(re.findall(
      r"\b(?:REC|AREC)\s*<[^>]+>", basic_expression, re.IGNORECASE
    )))
    field_details = ULTRACS_FIELD_DETAILS.get(param_name, {})
    source_locator = field_details.get("source_locator")
    if source_locator is None and source_references:
      source_locator = " + ".join(source_references)
    business_field = overrides.get(param_name, {}).get("business_field", param_name)
    dbt_targets = []

    for model_config in ACCOUNT_MODEL_CONFIGS:
      internal_name = model_config["name"]
      internal_node = models.get(internal_name)
      internal_relation = relation_by_model.get(internal_name)
      if not internal_node or not internal_relation:
        raise ValueError(f"Parser graph is missing dbt model/relation: {internal_name}")
      internal_projections = [
        projection for projection in _dbt_data_projections(workspace_root / model_config["sql"])
        if projection["source_column"].casefold() == param_name.casefold()
      ]
      public_node = models.get(model_config["public_name"])
      public_relation = relation_by_model.get(model_config["public_name"])
      public_projections = _selected_sql_projections(workspace_root / model_config["public_sql"])

      for projection in internal_projections:
        target_column = projection["target_column"]
        internal_metadata = cdp_columns.get((internal_relation, target_column), {})
        dbt_targets.append({
          "stage": "internal",
          "model": internal_name,
          "model_id": internal_node["id"],
          "relation": internal_relation,
          "column": target_column,
          "source_expression": projection["source_expression"],
          "source_path": internal_node.get("properties", {}).get("source_path"),
          "source_line": projection["source_line"],
          **internal_metadata,
        })
        if public_node and public_relation and target_column in public_projections:
          public_metadata = cdp_columns.get((public_relation, target_column), {})
          dbt_targets.append({
            "stage": "public",
            "model": model_config["public_name"],
            "model_id": public_node["id"],
            "relation": public_relation,
            "column": target_column,
            "source_model": internal_name,
            "source_column": target_column,
            "projection_expression": public_projections[target_column]["source_expression"],
            "projection_line": public_projections[target_column]["source_line"],
            "source_path": public_node.get("properties", {}).get("source_path"),
            **public_metadata,
          })

    if not dbt_targets:
      raise ValueError(f"No dbt account-slice projection found for HVR parameter {param_name}")
    primary_target = next((target for target in dbt_targets if target["stage"] == "public"), dbt_targets[0])
    confidence = overrides.get(param_name, {}).get("confidence", "explicit")
    source_description = field_details.get("description") or basic["comment"]
    evidence = overrides.get(param_name, {}).get("notes")
    if not evidence:
      evidence = (
        f"KWDW_ACC writes {basic_expression} to DWACC position {position}; "
        f"DWACC.param names it {param_name}; dbt reads DATA:{param_name}."
      )
    ultracs = {
      "program": PROGRAM_PATH,
      "source_path": PROGRAM_PATH,
      "source_locator": source_locator,
      "source_references": source_references,
      "description": source_description,
      "transformation": field_details.get("transformation", basic_expression),
      "basic_expression": basic_expression,
      "basic_comment": basic["comment"],
      "basic_source_line": basic["source_line"],
      "extract_file": EXTRACT_NAME,
      "position": position,
      "param_column": param_name,
    }
    cdp = {
      "model": primary_target["model"],
      "model_description": primary_target.get("model_description", ""),
      "description": primary_target.get("description", ""),
      "data_type": primary_target.get("data_type", ""),
      "classification": primary_target.get("classification", ""),
      "source_path": primary_target.get("source_path", ""),
      "table": primary_target["relation"],
      "column": primary_target["column"],
      "stage": primary_target["stage"],
    }
    records.append({
      "business_field": business_field,
      "field_id": f"ultracs:SAVINGS_ACCOUNT:{EXTRACT_NAME}:{position}",
      "ultracs_position": position,
      "ultracs_program": PROGRAM_PATH,
      "extract_file": EXTRACT_NAME,
      "param_column": param_name,
      "hvr_parameter": dict(parameter),
      "snowflake_table": primary_target["relation"],
      "snowflake_column": primary_target["column"],
      "confidence": confidence,
      "source_path": PARAM_SOURCE_PATH,
      "notes": evidence,
      "ultracs": ultracs,
      "cdp": cdp,
      "dbt_targets": dbt_targets,
      "ingestion_route": {
        "hvr_channels": ["ult_s3_acc1", "ult_s3_acc2"],
        "s3_paths": ["s3:path:HVR:ultracs:dwacc", "s3:path:DATALAKE:ultracs:dwacc"],
        "airflow_dag": "accounts_v1_ingestion_v1",
        "airflow_tasks": [
          "copy_s3_files_from_hvr_to_datalake_task_for_dwacc",
          "copy_s3_files_to_snowflake_task_for_dwacc",
        ],
        "raw_relation": "snowflake:relation:RAW.ACCOUNTS_V1__ACCOUNTS",
        "dbt_input": f"DATA:{param_name}",
      },
    })
  return records


def build_enterprise_overview(
    records: List[Dict[str, Any]],
    graph: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if graph is None:
        graph = json.loads(ENTERPRISE_GRAPH_PATH.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = graph["edges"]
    input_relations = {
      target["relation"]
      for record in records
      for target in record.get("dbt_targets", [])
    } or {record["snowflake_table"] for record in records}
    source_ids = {
        edge["source"]
        for edge in edges
        if edge["type"] == "RESOLVES_TO"
        and edge["target"] in input_relations
        and nodes.get(edge["source"], {}).get("type") == "DBT_SOURCE"
    }
    downstream: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        if edge["type"] == "DEPENDS_ON":
            downstream[edge["target"]].append(edge["source"])

    levels = {source_id: 0 for source_id in source_ids}
    model_ids = set()
    queue = deque(source_ids)
    while queue:
        dependency_id = queue.popleft()
        for model_id in downstream[dependency_id]:
            if nodes.get(model_id, {}).get("type") != "DBT_MODEL" or model_id in model_ids:
                continue
            model_ids.add(model_id)
            levels[model_id] = levels[dependency_id] + 1
            queue.append(model_id)

    relation_ids = set(input_relations)
    relation_ids.update(
        edge["target"]
        for edge in edges
        if edge["type"] == "MATERIALIZES_AS" and edge["source"] in model_ids
    )
    migration_ids = {
        edge["source"]
        for edge in edges
        if edge["type"] == "MIGRATES" and edge["target"] in relation_ids
    }
    product_ids = {
        edge["source"]
        for edge in edges
        if edge["type"] == "CONTAINS"
        and edge["target"] in model_ids | migration_ids
        and nodes.get(edge["source"], {}).get("type") == "CDP_PRODUCT"
    }
    included_ids = source_ids | model_ids | relation_ids | migration_ids | product_ids
    selected_edges = [
        edge
        for edge in edges
        if (
            edge["type"] == "RESOLVES_TO"
            and edge["source"] in source_ids
            and edge["target"] in relation_ids
        )
        or (
            edge["type"] == "DEPENDS_ON"
            and edge["source"] in model_ids
            and edge["target"] in source_ids | model_ids
        )
        or (
            edge["type"] == "MATERIALIZES_AS"
            and edge["source"] in model_ids
            and edge["target"] in relation_ids
        )
        or (
            edge["type"] == "CONTAINS"
            and edge["source"] in product_ids
            and edge["target"] in model_ids | migration_ids
        )
        or (
            edge["type"] == "MIGRATES"
            and edge["source"] in migration_ids
            and edge["target"] in relation_ids
        )
    ]
    return {
        "nodes": [nodes[node_id] for node_id in sorted(included_ids) if node_id in nodes],
        "edges": selected_edges,
        "input_relations": sorted(input_relations),
        "model_levels": levels,
        "model_count": len(model_ids),
        "migration_count": len(migration_ids),
    }


def load_cdp_column_metadata(source_root: Path | None = None) -> Dict[tuple[str, str], Dict[str, Any]]:
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    metadata = {}
    for relation_id, relative_path in CDP_SCHEMA_PATHS.items():
        schema_path = workspace_root / relative_path
        text = "\n".join(
            line.rstrip("\t")
            for line in schema_path.read_text(encoding="utf-8").splitlines()
        )
        document = yaml.safe_load(text) or {}
        for model in document.get("models", []) or []:
            for column in model.get("columns", []) or []:
                column_name = str(column.get("name", "")).upper()
                if not column_name:
                    continue
                metadata[(relation_id, column_name)] = {
                    "model": model.get("name", ""),
                    "model_description": model.get("description", ""),
                    "description": column.get("description", ""),
                    "data_type": column.get("data_type", ""),
                    "classification": (column.get("meta") or {}).get("CLASSIFICATION", ""),
                    "source_path": schema_path.resolve().relative_to(workspace_root).as_posix(),
                }
    return metadata


def _validate_dictionary_snapshot(
  records: List[Dict[str, Any]],
  dictionary_html: Path,
) -> None:
  template = Path(dictionary_html).read_text(encoding="utf-8")
  bundle_match = re.search(
    r'<script type="application/octet-stream" id="embedded-registry-bundle">([^<]+)</script>',
    template,
  )
  dictionary_match = re.search(
    r'<script type="application/octet-stream" id="embedded-csv">([^<]+)</script>',
    template,
  )
  if not bundle_match or not dictionary_match:
    raise ValueError("The V3 dictionary template is missing its embedded snapshots.")
  try:
    bundle = json.loads(gzip.decompress(base64.b64decode(bundle_match.group(1))).decode("utf-8"))
    dictionary_csv = gzip.decompress(base64.b64decode(dictionary_match.group(1))).decode("utf-8")
  except (ValueError, OSError, json.JSONDecodeError) as error:
    raise ValueError("The V3 dictionary template contains an invalid embedded snapshot.") from error
  expected_hash = bundle.get("manifest", {}).get("input_sha256")
  serialized_records = (json.dumps(records, indent=2) + "\n").replace("\n", os.linesep)
  actual_hash = hashlib.sha256(serialized_records.encode("utf-8")).hexdigest()
  if expected_hash != actual_hash:
    raise ValueError(
      "The V3 dictionary snapshot does not match the current column lineage input. "
      "Refresh the three-file V3 bundle before generating the POC pages."
    )
  if dictionary_csv != bundle.get("files", {}).get("data_dictionary.csv"):
    raise ValueError("The V3 dictionary and registry snapshots do not match each other.")

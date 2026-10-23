#!/usr/bin/env python3
"""Generate separate column inventories for parameterized account output feeds."""

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
OUTPUT_DIR = ROOT / "output"
sys.path.insert(0, str(ROOT / "src"))

from generate_column_lineage import _selected_sql_projections
from lineage.parsers.dbt import parse_dbt_project
from lineage.parsers.hvr import parse_hvr_param

COMMON_AIRFLOW = "kb-cdp-tenant-account/products/accounts-v1/airflow/accounts_v1/src/dags/accounts_v1_ingestion_v1.py"
FEEDS: dict[str, dict[str, Any]] = {
    "DWDBUST": {
        "extract_file": "DWDBUST.TXT",
        "program": "kb-ultracs-datawarehouse/KWDW_ACC",
        "param_file": "DWDBUST.param",
        "product": "accounts-v1",
        "raw_source": "ACCOUNTS_V1__ACCOUNT_OFFSET",
        "output_mode": "debtbuster",
        "route_status": "repository_static_route_found",
        "route_note": "Accounts-v1 Airflow maps dwdbust to ACCOUNTS_V1__ACCOUNT_OFFSET.",
        "route_evidence": [
            "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_dbust.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_dbus1.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_dbus2.json",
            COMMON_AIRFLOW,
        ],
    },
    "DWTDS": {
        "extract_file": "DWTDS.TXT",
        "program": "kb-ultracs-datawarehouse/KWDW_TDS",
        "param_file": "DWTDS.param",
        "product": "accounts-v1",
        "raw_source": "ACCOUNTS_V1__TERM_DEPOSITS_RAW",
        "output_mode": "separator_record",
        "start_pattern": r"LINE4\s*=\s*CIS\s*:\s*SEP\s*:",
        "write_pattern": r"WRITESEQ\s+LINE4\s+ON\s+DWTDS\b",
        "route_status": "repository_static_route_found",
        "route_note": "Accounts-v1 Airflow maps dwtds to ACCOUNTS_V1__TERM_DEPOSITS_RAW.",
        "route_evidence": [
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_actd1.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_actd2.json",
            COMMON_AIRFLOW,
        ],
    },
    "DWACFEE": {
        "extract_file": "DWACFEE.TXT",
        "program": "kb-ultracs-datawarehouse/KWDW_ACC2",
        "param_file": "DWACFEE.param",
        "product": "ult-account-fees-v1",
        "raw_source": "ULT_ACCOUNT_FEES_V1__ACCOUNT_FEE__RAW",
        "output_mode": "account_fee_loop",
        "route_status": "repository_static_route_found",
        "route_note": "ult-account-fees-v1 Airflow maps dwacfee to the account-fee raw source.",
        "route_evidence": [
            "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_afe.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_afe1.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_afe2.json",
            "kb-cdp-tenant-account/products/ult-account-fees-v1/airflow/ult_account_fees_v1/src/dags/ult_account_fees_v1_ingestion_v1.py",
        ],
    },
    "DWSWEEP": {
        "extract_file": "DWSWEEP.TXT",
        "program": "kb-ultracs-datawarehouse/KWDW_SWEEP",
        "param_file": "DWSWEEP.param",
        "product": "ult-account-payment-v1",
        "raw_source": "ULT_ACCOUNT_PAYMENT_V1__SWEEPS_RAW",
        "output_mode": "sweep_record",
        "route_status": "repository_static_route_found",
        "route_note": "ult-account-payment-v1 Airflow maps dwsweep to the sweeps raw source.",
        "route_evidence": [
            "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_swp.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_swp1.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_swp2.json",
            "kb-cdp-tenant-account/products/ult-account-payment-v1/airflow/ult_account_payment_v1/src/dags/ult_account_payment_v1_ingestion_v1.py",
        ],
    },
    "ACCREC_": {
        "extract_file": "ACCREC_{BHEAD}",
        "program": "kb-ultracs-datawarehouse/KWDW_ACCREC",
        "param_file": "ACCREC_.param",
        "product": "accounts-v1",
        "raw_source": "ACCOUNTS_V1__DWACCREC_RAW",
        "output_mode": "separator_record",
        "start_pattern": r"LINE\s*=\s*CIS\s*:\s*SEP\s*:\s*PID\s*:\s*SEP\s*:",
        "write_pattern": r"WRITESEQ\s+LINE\s+ON\s+DWOUT\b",
        "route_status": "landing_handoff_unverified",
        "route_note": "The accounts-v1 DAG comments that dwaccrec moved to Landing Tenancy; no checked-in handoff from that landing route to this raw source was established.",
        "route_evidence": [
            "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_accr.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_accr1.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_accr2.json",
            COMMON_AIRFLOW,
        ],
    },
    "DWNOMACC": {
        "extract_file": "DWNOMACC.TXT",
        "program": "kb-ultracs-datawarehouse/KWDW_NOMACC",
        "param_file": "DWNOMACC.param",
        "product": "accounts-v1",
        "raw_source": "ACCOUNTS_V1__NOMINATED_ACCOUNT",
        "output_mode": "separator_record",
        "start_pattern": r"LINE\s*=\s*CID\s*:\s*SEP\s*:\s*PROD\s*:\s*SEP\s*:",
        "write_pattern": r"WRITESEQ\s+LINE\s+ON\s+DWOUT\b",
        "route_status": "landing_handoff_unverified",
        "route_note": "The accounts-v1 DAG comments that dwnomacc moved to Landing Tenancy; no checked-in handoff from that landing route to this raw source was established.",
        "route_evidence": [
            "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_nmac.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_nmac1.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_nmac2.json",
            COMMON_AIRFLOW,
        ],
    },
    "DWUNCLD": {
        "extract_file": "DWUNCLD.TXT",
        "program": "kb-ultracs-datawarehouse/KWDW_ACC",
        "param_file": "DWUNCLD.param",
        "product": "accounts-v1",
        "raw_source": "ACCOUNTS_V1__UNCLEARED_FUNDS_RAW",
        "output_mode": "separator_record",
        "start_pattern": r"ULINE\s*=\s*CIS\s*:\s*SEP\s*:\s*PID\b",
        "write_pattern": r"WRITESEQ\s+ULINE\s+ON\s+DWUNC\b",
        "route_status": "landing_handoff_unverified",
        "route_note": "The accounts-v1 DAG comments that dwuncld moved to Landing Tenancy; no checked-in handoff from that landing route to this raw source was established.",
        "route_evidence": [
            "kb-cdp-hvr/hvr-config/apps/channels/ult_sf_ucf.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_ucf1.json",
            "kb-cdp-hvr/hvr-config/apps/channels/ult_s3_ucf2.json",
            COMMON_AIRFLOW,
        ],
    },
}


def _relative(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()


def _program_lines(program_path: str) -> list[str]:
    return (WORKSPACE_ROOT / program_path).read_text(encoding="utf-8", errors="replace").splitlines()


def _comment(line: str) -> str:
    match = re.search(r";\s*\*\s*(.*)$", line)
    return match.group(1).strip() if match else ""


def _separator_fields(config: dict[str, Any]) -> list[dict[str, Any]]:
    lines = _program_lines(config["program"])
    start = next((i for i, line in enumerate(lines) if re.search(config["start_pattern"], line, re.I)), None)
    if start is None:
        raise ValueError(f"{config['program']}: output start for {config['param_file']} was not found")
    end = next((i for i in range(start, len(lines)) if re.search(config["write_pattern"], lines[i], re.I)), None)
    if end is None:
        raise ValueError(f"{config['program']}: output write for {config['param_file']} was not found")

    variable = "ULINE" if config["param_file"] == "DWUNCLD.param" else "LINE4" if config["param_file"] == "DWTDS.param" else "LINE"
    fields: list[dict[str, Any]] = []
    separator = re.compile(r"\s*:\s*SEP\s*:\s*", re.I)
    for index in range(start, end):
        raw = lines[index]
        code = re.split(r";\s*\*", raw, maxsplit=1)[0].strip()
        match = re.match(rf"{variable}\s*=\s*(.*)$", code, re.I)
        if not match:
            continue
        parts = [part.strip() for part in separator.split(match.group(1)) if part.strip()]
        if parts and parts[0].casefold() == variable.casefold():
            parts = parts[1:]
        for expression in parts:
            fields.append({
                "expression": expression,
                "source_line": index + 1,
                "comment": _comment(raw),
            })
    return fields


def _debtbuster_fields(config: dict[str, Any]) -> list[dict[str, Any]]:
    lines = _program_lines(config["program"])
    seed = next(i for i, line in enumerate(lines) if re.search(r"LINE\s*=\s*CIS\s*:\s*SEP\s*:\s*PID\b", line, re.I))
    status_line = next(i for i in range(seed, len(lines)) if re.search(r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*ACT\s*:\s*REC<11,7>", lines[i], re.I))
    loop_line = next(i for i in range(status_line, len(lines)) if re.search(r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*ACT\s*:\s*SEP\s*:\s*REC<11,8,TX>", lines[i], re.I))
    fields = [
        {"expression": "CIS", "source_line": seed + 1, "comment": ""},
        {"expression": "PID", "source_line": seed + 1, "comment": ""},
        {"expression": "ACT:REC<11,7>[LEN(ACT)+1,9]", "source_line": status_line + 1, "comment": ""},
    ]
    for _ in range(8):
        fields.extend([
            {"expression": "ACT", "source_line": loop_line + 1, "comment": ""},
            {"expression": "REC<11,8,TX>[LEN(ACT)+1,9]", "source_line": loop_line + 1, "comment": ""},
        ])
    for field in fields[3:]:
        field["loop"] = "TX=1..8; one ACT/record pair per loop iteration"
    return fields


def _account_fee_fields(config: dict[str, Any]) -> list[dict[str, Any]]:
    lines = _program_lines(config["program"])
    seed = next(i for i, line in enumerate(lines) if re.search(r"LINE\s*=\s*CIS\s*:\s*SEP\s*:\s*PID\b", line, re.I))
    loop = next(i for i, line in enumerate(lines) if re.search(r"FOR\s+AA\s*=\s*132\s+TO\s+148", line, re.I))
    write_field = next(i for i in range(loop, len(lines)) if re.search(r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*FLD\b", lines[i], re.I))
    fields = [
        {"expression": "CIS", "source_line": seed + 1, "comment": ""},
        {"expression": "PID", "source_line": seed + 1, "comment": ""},
    ]
    for _ in range(17):
        fields.append({
            "expression": "AREC<AA> (FLD=AREC<AA>; AA=132..148)",
            "source_line": write_field + 1,
            "comment": "",
            "loop": "AA=132..148",
        })
    return fields


def _sweep_fields(config: dict[str, Any]) -> list[dict[str, Any]]:
    lines = _program_lines(config["program"])
    specs = [
        (r"LINE\s*=\s*ID\s*\+\s*0\s*:\s*SEP", "ID + 0", ""),
        (r"LINE\s*=\s*LINE\s*:\s*OCONV\(REC<X,1,1>", "OCONV(REC<X,1,1>,'D4')", ""),
        (r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*REC<X,2>", "REC<X,2>", "BRANCH"),
        (r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*REC<X,3>", "REC<X,3>", "OPERATOR"),
        (r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*REC<X,4>", "REC<X,4>", "SWEEP AUTH NO"),
        (r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*TYPE\b", "TYPE", ""),
        (r"LINE\s*=\s*LINE\s*:\s*SEP\s*:\s*REC<X,6,2>", 'REC<X,6,2>:" ":REC<X,6,1>', "SWEEP DETAILS"),
    ]
    fields = []
    for pattern, expression, fallback_comment in specs:
        number = next((i + 1 for i, line in enumerate(lines) if re.search(pattern, line, re.I)), None)
        if number is None:
            raise ValueError(f"{config['program']}: DWSWEEP field expression not found: {expression}")
        fields.append({"expression": expression, "source_line": number, "comment": fallback_comment})
    type_line = next(i for i, line in enumerate(lines) if re.search(r"TYPE\s*=\s*\"C\"", line, re.I))
    fields[5]["transformation_lines"] = [type_line + 1]
    fields[5]["loop"] = "Sweep history record loop; TYPE is set from REC<X,5,1> conditions"
    return fields


def _basic_fields(config: dict[str, Any]) -> list[dict[str, Any]]:
    mode = config["output_mode"]
    if mode == "separator_record":
        return _separator_fields(config)
    if mode == "debtbuster":
        return _debtbuster_fields(config)
    if mode == "account_fee_loop":
        return _account_fee_fields(config)
    if mode == "sweep_record":
        return _sweep_fields(config)
    raise ValueError(f"Unsupported output mode: {mode}")


def _sql_data_projections(path: Path) -> list[dict[str, Any]]:
    projections = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        code = re.split(r"--", raw, maxsplit=1)[0].strip()
        source = re.search(r"\bDATA\s*:\s*(?:\"([^\"]+)\"|([A-Za-z0-9_]+))", code, re.I)
        target = re.search(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\s*,?\s*$", code, re.I)
        if source and target:
            projections.append({
                "source_column": source.group(1) or source.group(2),
                "target_column": target.group(1).upper(),
                "source_expression": code,
                "source_line": line_number,
            })
    return projections


def _yaml_model_metadata(path: Path, model_name: str) -> dict[str, Any]:
    text = "\n".join(line.rstrip("\t") for line in path.read_text(encoding="utf-8").splitlines())
    document = yaml.safe_load(text) or {}
    model = next((item for item in document.get("models", []) if item.get("name") == model_name), {})
    columns = {
        str(column.get("name", "")).upper(): column
        for column in model.get("columns", []) or []
        if column.get("name")
    }
    return {"description": model.get("description", ""), "columns": columns}


def _build_product_context(product_name: str) -> dict[str, Any]:
    product = WORKSPACE_ROOT / "kb-cdp-tenant-account" / "products" / product_name
    dbt_root = product / "dbt"
    graph = parse_dbt_project(dbt_root)
    nodes = {node.id: node for node in graph.nodes if node.label == "DBT_MODEL"}
    model_ids = {node.properties.get("name"): node.id for node in nodes.values()}
    relations = {
        edge.source: edge.target
        for edge in graph.edges
        if edge.type == "MATERIALIZES_AS"
    }
    downstream = {}
    for edge in graph.edges:
        if edge.type == "DEPENDS_ON" and edge.target.startswith("dbt:model:"):
            downstream.setdefault(edge.target, []).append(edge.source)
    return {
        "product": product,
        "dbt_root": dbt_root,
        "graph": graph,
        "nodes": nodes,
        "model_ids": model_ids,
        "relations": relations,
        "downstream": downstream,
    }


def _model_path(context: dict[str, Any], model_name: str) -> Path:
    matches = list(context["dbt_root"].rglob(f"{model_name}.sql"))
    if len(matches) != 1:
        raise ValueError(f"Expected one SQL file for {model_name}; found {len(matches)}")
    return matches[0]


def _target_metadata(context: dict[str, Any], model_name: str, column_name: str) -> dict[str, Any]:
    sql_path = _model_path(context, model_name)
    yaml_path = sql_path.with_suffix(".yml")
    model_meta = _yaml_model_metadata(yaml_path, model_name)
    column = model_meta["columns"].get(column_name.upper(), {})
    return {
        "model": model_name,
        "relation": context["relations"].get(context["model_ids"].get(model_name, "")),
        "model_description": model_meta["description"],
        "column": column_name.upper(),
        "data_type": column.get("data_type"),
        "description": column.get("description", ""),
        "classification": (column.get("meta") or {}).get("CLASSIFICATION"),
        "schema_path": _relative(yaml_path),
    }


def _internal_models(config: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    models = []
    for sql_path in sorted(context["dbt_root"].rglob("*.sql")):
        if "internal" not in sql_path.parts:
            continue
        sql = sql_path.read_text(encoding="utf-8", errors="ignore")
        if config["raw_source"].casefold() not in sql.casefold():
            continue
        projections = _sql_data_projections(sql_path)
        if projections:
            models.append({
                "name": sql_path.stem,
                "sql_path": sql_path,
                "projections": projections,
            })
    return models


def _public_targets(context: dict[str, Any], internal_model: str, column: str) -> list[dict[str, Any]]:
    internal_id = context["model_ids"].get(internal_model)
    if not internal_id:
        return []
    targets = []
    for public_id in context["downstream"].get(internal_id, []):
        node = context["nodes"].get(public_id)
        if not node:
            continue
        name = node.properties.get("name", "")
        sql_path = _model_path(context, name)
        if "public" not in sql_path.parts:
            continue
        projections = _selected_sql_projections(sql_path)
        if column.upper() not in projections:
            continue
        metadata = _target_metadata(context, name, column)
        projection = projections[column.upper()]
        targets.append({
            "stage": "public",
            **metadata,
            "source_model": internal_model,
            "source_column": column.upper(),
            "projection_expression": projection["source_expression"],
            "projection_line": projection["source_line"],
            "source_path": _relative(sql_path),
        })
    return targets


def _param_columns(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = WORKSPACE_ROOT / "kb-cdp-hvr" / "hvr-config" / "scripts" / config["param_file"]
    graph = parse_hvr_param(path)
    return [dict(node.properties) for node in graph.nodes if node.label == "HVR_COLUMN"]


def build_feed_records(feed: str, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = config or FEEDS[feed]
    param_path = WORKSPACE_ROOT / "kb-cdp-hvr" / "hvr-config" / "scripts" / config["param_file"]
    parameters = _param_columns(config)
    basic_fields = _basic_fields(config)
    if len(parameters) != len(basic_fields):
        raise ValueError(
            f"{feed}: BASIC output has {len(basic_fields)} fields, but {config['param_file']} has {len(parameters)} columns"
        )

    context = _build_product_context(config["product"])
    models = _internal_models(config, context)
    if not models:
        raise ValueError(f"{feed}: no dbt model with projections reads {config['raw_source']}")
    records = []
    for position, (parameter, basic) in enumerate(zip(parameters, basic_fields), start=1):
        name = str(parameter.get("name", ""))
        targets = []
        dbt_keys_seen = []
        for model in models:
            for projection in model["projections"]:
                if projection["source_column"] != name:
                    continue
                dbt_keys_seen.append(projection["source_column"])
                metadata = _target_metadata(context, model["name"], projection["target_column"])
                targets.append({
                    "stage": "internal",
                    **metadata,
                    "source_expression": projection["source_expression"],
                    "source_line": projection["source_line"],
                    "source_path": _relative(model["sql_path"]),
                })
                targets.extend(_public_targets(context, model["name"], projection["target_column"]))

        notes = [
            "BASIC output fields are aligned to HVR .param columns by one-based position; the counts match, but the BASIC record does not declare the .param names. This association is inferred.",
            config["route_note"],
        ]
        if not targets:
            notes.append("No exact, case-sensitive dbt DATA key match was found for this .param name.")
        if feed == "DWNOMACC" and name == "RefDate":
            notes.append("The dbt SQL reads DATA:ReferenceDate; the .param name is RefDate. These keys are not treated as equivalent.")
        if feed == "DWTDS" and name == "Prod":
            notes.append("The dbt SQL reads DATA:Product, which matches the separate .param field Product at position 2; no DATA:Prod projection exists for this position 15 field. These fields are not treated as equivalent.")
        if feed == "DWTDS" and name == "col40":
            notes.append("No dbt DATA projection for col40 was found in the discovered term-deposit model.")
        records.append({
            "business_field": name,
            "field_id": f"ultracs:ACCOUNT:{feed}:{position}",
            "ultracs_position": position,
            "ultracs_program": config["program"],
            "extract_file": config["extract_file"],
            "param_column": name,
            "hvr_parameter": parameter,
            "confidence": "inferred",
            "source_path": f"kb-cdp-hvr/hvr-config/scripts/{config['param_file']}",
            "notes": " ".join(notes),
            "dbt_mapping_status": "mapped" if targets else "no_exact_key_match",
            "route_status": config["route_status"],
            "route_evidence": config["route_evidence"],
            "ultracs": {
                "program": config["program"],
                "source_path": config["program"],
                "source_locator": basic["expression"],
                "source_references": re.findall(r"\b(?:AREC|REC|TDREC|IREC|EREC)\s*<[^>]+>", basic["expression"], re.I),
                "description": basic.get("comment", ""),
                "basic_expression": basic["expression"],
                "basic_source_line": basic["source_line"],
                "basic_transformation_lines": basic.get("transformation_lines", []),
                "loop": basic.get("loop"),
                "extract_file": config["extract_file"],
                "position": position,
                "param_column": name,
            },
            "cdp": targets[0] if targets else {},
            "dbt_targets": targets,
            "ingestion_route": {
                "status": config["route_status"],
                "raw_source": config["raw_source"],
                "dbt_input": f"DATA:{dbt_keys_seen[0]}" if dbt_keys_seen else None,
                "evidence": config["route_evidence"],
            },
        })
    return records


def _existing_feed_summary(path: Path, feed: str) -> dict[str, Any]:
    records = json.loads(path.read_text(encoding="utf-8"))
    return {
        "field_positions": len(records),
        "fields_with_internal_target": sum(any(t.get("stage") == "internal" for t in r.get("dbt_targets", [])) for r in records),
        "fields_with_public_target": sum(any(t.get("stage") == "public" for t in r.get("dbt_targets", [])) for r in records),
        "dbt_target_projections": sum(len(r.get("dbt_targets", [])) for r in records),
        "source": "existing_generated_inventory",
        "route_status": "repository_static_route_found" if feed == "DWACC" else "ordinal_mapping_inferred",
    }


def build_summary(inventories: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    existing_paths = {
        "DWACC": OUTPUT_DIR / "column_lineage.json",
        "DWREL": OUTPUT_DIR / "dwrel_column_lineage.json",
    }
    for feed, path in existing_paths.items():
        summary[feed] = _existing_feed_summary(path, feed)
    for feed, records in inventories.items():
        summary[feed] = {
            "field_positions": len(records),
            "fields_with_internal_target": sum(any(t.get("stage") == "internal" for t in r["dbt_targets"]) for r in records),
            "fields_with_public_target": sum(any(t.get("stage") == "public" for t in r["dbt_targets"]) for r in records),
            "dbt_target_projections": sum(len(r["dbt_targets"]) for r in records),
            "source": "generated_candidate_inventory",
            "route_status": FEEDS[feed]["route_status"],
        }
    field_positions = sum(item["field_positions"] for item in summary.values())
    unique_labels = {
        record.get("param_column", "").casefold()
        for feed, path in existing_paths.items()
        for record in json.loads(path.read_text(encoding="utf-8"))
    }
    unique_labels.update(
        record["param_column"].casefold()
        for records in inventories.values()
        for record in records
    )
    return {
        "scope": "Nine selected account-related Ultracs output families with HVR parameter definitions: DWACC, DWREL, and the seven generated candidate inventories.",
        "scope_note": "Counts are feed-field positions, not unique business concepts. Other account-adjacent outputs without a reviewed ordered HVR .param inventory are not counted. Three candidate feeds retain an unverified Landing Tenancy handoff.",
        "field_positions_across_scoped_feeds": field_positions,
        "distinct_parameter_labels_case_insensitive": len(unique_labels),
        "feed_fields_with_internal_dbt_target": sum(item["fields_with_internal_target"] for item in summary.values()),
        "feed_fields_with_public_dbt_target": sum(item["fields_with_public_target"] for item in summary.values()),
        "dbt_target_projections_across_scoped_feeds": sum(item["dbt_target_projections"] for item in summary.values()),
        "feeds": summary,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inventories = {feed: build_feed_records(feed) for feed in FEEDS}
    for feed, records in inventories.items():
        slug = feed.rstrip("_").lower()
        path = OUTPUT_DIR / f"{slug}_column_lineage.json"
        path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        mapped = sum(bool(record["dbt_targets"]) for record in records)
        print(f"Generated {path.relative_to(ROOT)}: {len(records)} positions; {mapped} with exact dbt key matches")
    summary = build_summary(inventories)
    summary_path = OUTPUT_DIR / "account_column_inventory_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {summary_path.relative_to(ROOT)}: {summary['field_positions_across_scoped_feeds']} account-related feed-field positions across 9 outputs")


if __name__ == "__main__":
    main()
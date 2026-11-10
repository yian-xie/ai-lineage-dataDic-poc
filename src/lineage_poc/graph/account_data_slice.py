"""Build a one-field Account slice with Protect and Landing context and explicit gaps."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from .account import with_related_columns
from .merge import merge_graph_documents

DEFAULT_FIELD_ID = "ultracs:SAVINGS_ACCOUNT:DWACC:54"
PROTECT_PRODUCTS = {"sys-pds-stg-account-v1", "sys_pds_account_v1"}
LANDING_PRODUCT = "ultracs-v1"

PROTECT_EVIDENCE = {
    "staging_projection": (
        "kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/"
        "sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__ultracs_account.sql",
        ("CAST(AD.ACCOUNTOPENDATE AS TIMESTAMP_TZ(9)) AS ACCOUNTOPENDATE",),
    ),
    "combined_ultracs_branch": (
        "kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/"
        "sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__combined_account.sql",
        (
            "CAST(NULL AS TIMESTAMP_TZ(9)) AS ACCOUNT_OPEN_DATE",
            "TMV.ACCOUNTOPENEDDATETIME AS ACCOUNT_OPEN_DATE",
        ),
    ),
    "staging_consumer": (
        "kb-cdp-tenant-protect-downstream/products/sys-pds-stg-account-v1/dbt/models/stage/"
        "sys_pds_stg_account_v1__account_v1/sys_pds_stg_account_v1__account_v1.sql",
        ('sys_pds_stg_account_v1__combined_account',),
    ),
    "downstream_fallback": (
        "kb-cdp-tenant-protect-downstream/products/sys_pds_account_v1/dbt/models/internal/"
        "sys_pds_account_v1__account_v2.sql",
        (
            "IFF(A.ACCOUNT_OPEN_DATE IS NULL, B.ACCOUNTSTATUSDATETIME, A.ACCOUNT_OPEN_DATE)",
            "AS OPENDATE",
        ),
    ),
}
LANDING_EVIDENCE = {
    "raw_payload_projection": (
        "kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/internal/"
        "loadnewaccounts_raw/loadnewaccounts_raw.sql",
        ("SPLIT_PART(PAYLOAD, '|', 6)", "AS COL_004", "loadnewaccounts_ingest"),
    ),
    "source_declaration": (
        "kb-cdp-tenant-landing/products/ultracs-v1/dbt/models/source.yml",
        ("loadnewaccounts_ingest",),
    ),
}


def find_column_record(records: list[dict[str, Any]], field_id: str = DEFAULT_FIELD_ID) -> dict[str, Any]:
    matches = [record for record in records if record.get("field_id") == field_id]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one column record for {field_id!r}, found {len(matches)}")
    return matches[0]


def input_source_paths(source_root: Path, column_record: dict[str, Any]) -> list[Path]:
    """List exact repository files cited by this bounded field slice."""
    root = Path(source_root).resolve()
    relative_paths = {
        column_record.get("source_path"),
        column_record.get("ultracs", {}).get("source_path"),
        *[target.get("source_path") for target in column_record.get("dbt_targets", [])],
    }
    route = column_record.get("ingestion_route", {})
    for channel in route.get("hvr_channels", []):
        relative_paths.add(f"kb-cdp-hvr/hvr-config/apps/channels/{channel}.json")
    if route.get("airflow_dag"):
        relative_paths.add(
            "kb-cdp-tenant-account/products/accounts-v1/airflow/accounts_v1/src/dags/"
            f"{route['airflow_dag']}.py"
        )
    relative_paths.update(path for path, _ in PROTECT_EVIDENCE.values())
    relative_paths.update(path for path, _ in LANDING_EVIDENCE.values())
    paths = sorted({(root / path).resolve() for path in relative_paths if path})
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Account slice evidence files are missing: {', '.join(map(str, missing))}")
    return paths


def _canonical_graph(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [
            {key: copy.deepcopy(node[key]) for key in ("id", "type", "properties")}
            for node in document.get("nodes", [])
        ],
        "edges": [
            {key: copy.deepcopy(edge[key]) for key in ("source", "target", "type", "properties")}
            for edge in document.get("edges", [])
        ],
    }


def _qualify_repo_paths(graph: dict[str, Any], repository: str) -> dict[str, Any]:
    result = copy.deepcopy(graph)
    prefix = repository.rstrip("/") + "/"
    for record in [*result["nodes"], *result["edges"]]:
        properties = record.setdefault("properties", {})
        for key in ("source_path", "source_file"):
            value = properties.get(key)
            if isinstance(value, str) and value and not value.startswith(prefix):
                properties[key] = prefix + value.lstrip("/")
        paths = properties.get("source_paths")
        if isinstance(paths, list):
            properties["source_paths"] = [
                prefix + path.lstrip("/")
                if isinstance(path, str) and path and not path.startswith(prefix)
                else path
                for path in paths
            ]
    return result


def _subgraph(document: dict[str, Any], predicate) -> dict[str, list[dict[str, Any]]]:
    graph = _canonical_graph(document)
    selected_ids = {node["id"] for node in graph["nodes"] if predicate(node)}
    return {
        "nodes": [node for node in graph["nodes"] if node["id"] in selected_ids],
        "edges": [
            edge for edge in graph["edges"]
            if edge["source"] in selected_ids and edge["target"] in selected_ids
        ],
    }


def _protect_account_subgraph(document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    prefixes = tuple(f"products/{product}/" for product in PROTECT_PRODUCTS)
    return _subgraph(
        document,
        lambda node: (
            node["type"] == "CDP_PRODUCT"
            and node["properties"].get("name") in PROTECT_PRODUCTS
        ) or str(node["properties"].get("source_path", "")).startswith(prefixes),
    )


def _landing_newaccounts_subgraph(document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    def selected(node: dict[str, Any]) -> bool:
        properties = node["properties"]
        if node["type"] == "CDP_PRODUCT":
            return properties.get("name") == LANDING_PRODUCT
        if properties.get("project") != LANDING_PRODUCT:
            return False
        name = str(properties.get("name", "")).casefold()
        return name.startswith("loadnewaccounts")

    return _subgraph(document, selected)


def _evidence(source_root: Path, groups: dict[str, tuple[str, tuple[str, ...]]]) -> list[dict[str, Any]]:
    root = Path(source_root).resolve()
    evidence = []
    for role, (relative_path, markers) in groups.items():
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Account slice evidence file is missing: {path}")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        matches = [
            {"line": index, "text": line.strip()}
            for index, line in enumerate(lines, start=1)
            if any(marker.casefold() in line.casefold() for marker in markers)
        ]
        missing_markers = [
            marker for marker in markers
            if not any(marker.casefold() in item["text"].casefold() for item in matches)
        ]
        if missing_markers:
            raise ValueError(f"Expected Account Open Date evidence missing from {relative_path}: {missing_markers}")
        evidence.append({
            "role": role,
            "source_path": relative_path,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "matches": matches,
        })
    return evidence


def build_account_data_slice(
    account_graph: dict[str, Any],
    column_records: list[dict[str, Any]],
    protect_document: dict[str, Any],
    landing_document: dict[str, Any],
    source_root: Path,
    *,
    field_id: str = DEFAULT_FIELD_ID,
    input_snapshots: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compose a bounded Account Open Date graph and retain unresolved boundaries."""
    matches = [record for record in column_records if record.get("field_id") == field_id]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one column record for {field_id!r}, found {len(matches)}")
    column_record = matches[0]
    account = _canonical_graph(account_graph)
    account = with_related_columns(account, [column_record])
    protect = _qualify_repo_paths(
        _protect_account_subgraph(protect_document), "kb-cdp-tenant-protect-downstream",
    )
    landing = _qualify_repo_paths(
        _landing_newaccounts_subgraph(landing_document), "kb-cdp-tenant-landing",
    )
    merged, conflicts = merge_graph_documents(account, protect, "account", "protect-account-products")
    merged, landing_conflicts = merge_graph_documents(merged, landing, "account-plus-protect", "landing-loadnewaccounts")
    conflicts.extend(landing_conflicts)
    if conflicts:
        raise ValueError(f"Account slice has {len(conflicts)} graph identity conflicts; inspect before publication")

    for edge in merged["edges"]:
        properties = edge.setdefault("properties", {})
        if properties.get("confidence") == "inferred" and not properties.get("reason"):
            if edge["type"] == "CARRIED_BY":
                properties["reason"] = (
                    "The sample DWACC filename matches the HVR capture pattern; this filename-pattern "
                    "association does not prove file delivery or runtime processing."
                )
            else:
                properties["reason"] = "The relationship is inferred from repository evidence, not an explicit binding."

    nodes_by_id = {node["id"]: node for node in merged["nodes"]}
    account_relation_id = column_record["cdp"]["table"]
    protect_source = next((
        node for node in protect["nodes"]
        if node["type"] == "DBT_SOURCE"
        and node["properties"].get("source_name") == "account_public_views"
        and node["properties"].get("name") == "ACCOUNTS_V1__ULTRACS_ACCOUNTS_DETAIL"
    ), None)
    protect_relation_id = next((
        edge["target"] for edge in protect["edges"]
        if protect_source is not None and edge["source"] == protect_source["id"]
        and edge["type"] == "RESOLVES_TO"
    ), None)
    candidate_links = []
    if protect_source and protect_relation_id in nodes_by_id and account_relation_id in nodes_by_id:
        candidate_links.append({
            "from": account_relation_id,
            "to": protect_relation_id,
            "relationship_candidate": "SAME_PHYSICAL_RELATION",
            "status": "unresolved_candidate",
            "confidence": "inferred",
            "reason": (
                "The declared schema/table matches the Account public relation and the Protect source YAML "
                "rewrites the domain database from PROTECTDS to ACCOUNT, but the resolved database identity "
                "is not recorded in the payload. This is not a graph edge."
            ),
            "source_paths": [
                column_record["cdp"]["source_path"],
                protect_source["properties"]["source_path"],
            ],
        })

    source_evidence = _evidence(source_root, {**PROTECT_EVIDENCE, **LANDING_EVIDENCE})
    source_snapshots = input_snapshots or {}
    landing_source_exists = any(
        node["type"] == "DBT_SOURCE"
        and node["properties"].get("project") == LANDING_PRODUCT
        and node["properties"].get("name") == "loadaccounts_ingest"
        for node in landing["nodes"]
    )
    gap_register = [
        {
            "id": "ACCOUNT-OPEN-DATE-PROTECT-NULL",
            "title": "Protect Ultracs branch replaces Account Open Date with NULL",
            "status": "explicit_value_boundary",
            "impact": "The staged Account Open Date is not value-lineaged from the DWACC field through the Protect Ultracs branch. The downstream OPENDATE calculation can fall back to ACCOUNTSTATUSDATETIME; that fallback is a different value source.",
            "evidence": [
                {"source_path": item["source_path"], "line": match["line"], "text": match["text"]}
                for item in source_evidence
                if item["role"] in {"combined_ultracs_branch", "downstream_fallback"}
                for match in item["matches"]
            ],
        },
        {
            "id": "ACCOUNT-OPEN-DATE-PROTECT-DATABASE",
            "title": "Protect Account public-source database identity remains templated",
            "status": "unresolved_physical_binding",
            "impact": "Keep the same-name Account public relation association in candidate_links; do not merge the physical relation nodes or create RESOLVES_TO across them without the resolved database identity.",
            "evidence": [protect_source["properties"]["source_path"]] if protect_source else [],
        },
        {
            "id": "ACCOUNT-DWACC-LANDING-HANDOFF",
            "title": "Landing does not declare the DWACC LOADACCOUNTS_INGEST relation",
            "status": "unresolved_route_boundary",
            "impact": "The Landing graph contains the separate loadnewaccounts_ingest feed. Do not equate it with loadaccounts_ingest or connect its position-6 COL_004 to DWACC OpenDate position 54.",
            "landing_loadaccounts_source_declared": landing_source_exists,
            "evidence": [item["source_path"] for item in source_evidence if item["role"] in {"source_declaration", "raw_payload_projection"}],
        },
    ]
    return {
        **merged,
        "slice": {
            "name": "Account Open Date",
            "field_id": field_id,
            "scope": "DWACC field mapping with Account, Protect account-staging, and separate Landing context",
            "runtime_verified": False,
        },
        "field_mappings": [copy.deepcopy(column_record)],
        "candidate_links": candidate_links,
        "field_evidence": source_evidence,
        "gap_register": gap_register,
        "input_snapshots": source_snapshots,
        "merge_conflicts": [],
    }
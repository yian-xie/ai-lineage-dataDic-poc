"""Generate a standalone parser graph and findings report for tenant landing."""

from lineage_poc.paths import PROJECT_ROOT as REPOSITORY_ROOT, REFERENCE_LINEAGE, OUTPUT_ROOT, source_root as default_source_root

import json
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = REPOSITORY_ROOT
WORKSPACE_ROOT = default_source_root()

from lineage_poc.parsers import parse_dbt_project, parse_landing_tenant


LANDING_ROOT = WORKSPACE_ROOT / "kb-cdp-tenant-landing"
OUTPUT_PATH = OUTPUT_ROOT / "lineage" / "landing_tenant_lineage.json"
REPORT_PATH = OUTPUT_ROOT / "lineage" / "LANDING_TENANT_FINDINGS.md"
ACCOUNT_DBT = WORKSPACE_ROOT / "kb-cdp-tenant-account/products/accounts-v1/dbt"
FULL_GRAPH_PATH = REFERENCE_LINEAGE / "table_lineage.json"


def _payload(graph: Any) -> dict[str, list[dict[str, Any]]]:
    return {
        "nodes": [
            {"id": node.id, "type": node.label, "properties": node.properties}
            for node in graph.nodes
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "type": edge.type,
                "properties": edge.properties,
            }
            for edge in graph.edges
        ],
    }


def _qualified_relation_name(node: dict[str, Any]) -> str:
    return str(node.get("properties", {}).get("name", "")).strip(' `"').upper()


def build_report(
    graph: dict[str, list[dict[str, Any]]],
    source_root: Path | None = None,
    full_graph: dict | None = None,
) -> str:
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    landing_root = workspace_root / "kb-cdp-tenant-landing"
    projects_root = landing_root / "products"
    project_counts = []
    for project_path in sorted(projects_root.iterdir()):
        dbt_path = project_path / "dbt"
        if not (dbt_path / "dbt_project.yml").is_file():
            continue
        product_graph = _payload(parse_dbt_project(dbt_path))
        project_counts.append((
            project_path.name,
            sum(node["type"] == "DBT_MODEL" for node in product_graph["nodes"]),
            sum(node["type"] == "DBT_SOURCE" for node in product_graph["nodes"]),
            sum(node["type"] == "SNOWFLAKE_RELATION" for node in product_graph["nodes"]),
            len(product_graph["edges"]),
        ))

    ultracs_stats = next(row for row in project_counts if row[0] == "ultracs-v1")
    landing_raw_sources = [
        node for node in graph["nodes"]
        if node["type"] == "DBT_SOURCE"
        and node["properties"].get("project") == "ultracs-v1"
        and str(node["properties"].get("schema", "")).upper() == "ULTRACS_RAW"
    ]

    account_graph = _payload(parse_dbt_project(workspace_root / "kb-cdp-tenant-account" / "products" / "accounts-v1" / "dbt"))
    ultracs_project_graph = _payload(parse_dbt_project(landing_root / "products" / "ultracs-v1" / "dbt"))
    account_landing_sources = [
        node for node in account_graph["nodes"]
        if node["type"] == "DBT_SOURCE"
        and node["properties"].get("source_name") == "ultracs_landing"
    ]
    landing_public_relations = {
        _qualified_relation_name(node)
        for node in ultracs_project_graph["nodes"]
        if node["type"] == "SNOWFLAKE_RELATION"
        and node["properties"].get("layer") == "public"
    }
    account_landing_matches = [
        source for source in account_landing_sources
        if f"{str(source['properties'].get('schema', '')).upper()}.{str(source['properties'].get('name', '')).upper()}"
        in landing_public_relations
    ]

    if full_graph is None:
        full_graph = json.loads(FULL_GRAPH_PATH.read_text(encoding="utf-8"))
    hvr_relation_leaves = {
        _qualified_relation_name(node).split(".")[-1]
        for node in full_graph["nodes"]
        if node["type"] == "SNOWFLAKE_RELATION"
        and node.get("properties", {}).get("creation_mechanism") == "HVR"
    }
    hvr_name_matches = [
        node for node in landing_raw_sources
        if str(node["properties"].get("name", "")).upper() in hvr_relation_leaves
    ]

    node_counts = Counter(node["type"] for node in graph["nodes"])
    edge_counts = Counter(edge["type"] for edge in graph["edges"])
    products = sorted(row[0] for row in project_counts)

    lines = [
        "# Tenant Landing Lineage Findings",
        "",
        "## Scope",
        "",
        "The parser reads dbt project metadata and SQL from `kb-cdp-tenant-landing/products/*/dbt`. The generated graph is a standalone parser output; it does not modify or merge into `table_lineage.json`.",
        "",
        f"The repository has **{len(project_counts)} dbt product projects**. The parsed graph contains **{len(graph['nodes']):,} nodes** and **{len(graph['edges']):,} relationships**: **{node_counts['CDP_PRODUCT']} products**, **{node_counts['DBT_MODEL']:,} models**, **{node_counts['DBT_SOURCE']:,} source declarations**, and **{node_counts['SNOWFLAKE_RELATION']:,} physical relation identities**.",
        "",
        f"`ultracs-v1` contributes **{ultracs_stats[1]} models**, **{ultracs_stats[2]} sources**, **{ultracs_stats[3]} relation nodes**, and **{ultracs_stats[4]} dbt relationships**. Its `{len(landing_raw_sources)}` `ULTRACS_RAW` source declarations represent the HVR-facing landing layer.",
        "",
        "## Position in the Lineage",
        "",
        "`kb-cdp-tenant-landing` belongs after HVR ingestion and before downstream tenant consumers:",
        "",
        "`Ultracs sources -> HVR -> Snowflake ULTRACS_RAW -> tenant-landing dbt views -> account tenant / selected Enterprise consumers`",
        "",
        f"The account tenant declares `{len(account_landing_sources)}` source(s) named `ultracs_landing`; **{len(account_landing_matches)}** has a matching landing model by declared schema and relation name: `feeexemption` in `ULTRACS_PUBLIC`. The same account project also declares `account_raw_source` tables in `RAW`; those are a distinct ingestion path and should not automatically be routed through tenant landing.",
        "",
        "## Evidence and Limits",
        "",
        f"The current table graph has HVR-created physical relation names matching **{len(hvr_name_matches)} of {len(landing_raw_sources)}** `ultracs-v1` raw-source table names. These are **name-only candidates**, not merged lineage edges: HVR relations are often unqualified, while landing source declarations carry `ULTRACS_RAW` and a database declaration. Canonical database/schema evidence is needed before treating them as the same physical object.",
        "",
        f"The parser emits `{edge_counts['CONTAINS']}` product ownership relationships, `{edge_counts['DEPENDS_ON']}` dbt dependency relationships, `{edge_counts['RESOLVES_TO']}` source-to-relation relationships, and `{edge_counts['MATERIALIZES_AS']}` model-to-relation relationships.",
        "",
        "## Open Questions",
        "",
        "- Confirm which HVR-created relations resolve to the tenant-landing `ULTRACS_RAW` objects using database/schema or runtime evidence.",
        "- Confirm whether account and Enterprise consumers beyond `feeexemption` should source directly from tenant landing or continue through account-tenant `RAW` and public models.",
        "- The repository README is still a placeholder; product ownership, deployment/runtime behavior, and the full intended consumer boundary need owner confirmation.",
        "",
        "## Products",
        "",
        "The parser scanned: " + ", ".join(f"`{product}`" for product in products) + ".",
        "",
        "Generated graph: `../output/landing_tenant_lineage.json`.",
        "",
    ]
    return "\n".join(lines)


def main(source_root: Path | None = None, destination: Path | None = None) -> None:
    workspace_root = Path(source_root).resolve() if source_root is not None else default_source_root()
    destination = Path(destination) if destination is not None else OUTPUT_ROOT / "lineage"
    destination.mkdir(parents=True, exist_ok=True)
    graph = _payload(parse_landing_tenant(workspace_root / "kb-cdp-tenant-landing"))
    (destination / "landing_tenant_lineage.json").write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (destination / "LANDING_TENANT_FINDINGS.md").write_text(build_report(graph, source_root=workspace_root), encoding="utf-8")


if __name__ == "__main__":
    main()
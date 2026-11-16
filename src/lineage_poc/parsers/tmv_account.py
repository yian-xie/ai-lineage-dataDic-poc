"""Explicit Account-domain roots and repository-static dependency closure."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path


LANDING_ACCOUNT_ROOTS = (
    "accounts", "newaccounts", "relationships", "relationships_from_raw",
    "accountsoffset", "accountdirectdebitauthority", "accountfeedetails",
    "accountsaudit", "accountsrvldetails", "brlaccounts", "brlsavingaccounts",
    "dwaccrec", "s4_nominatedaccounts", "unclearedfunds", "termdeposits",
    "sweeps", "loans", "loanrates", "loanapplications", "feedetails",
    "feeexemption", "overdrafttemporarylimits",
)
PROTECT_ACCOUNT_PRODUCTS = (
    "sys-pds-stg-account-v1", "sys_pds_account_v1", "sys-pds-newaccount-v1",
    "sys-pds-accountbal-v1", "sys-pds-accountrel-v1", "sys-pds-accounttransdet-v1",
)


def slice_landing_account(graph: dict) -> dict:
    nodes = {node["id"]: node for node in graph["nodes"]}
    seeds = {
        node["id"] for node in graph["nodes"]
        if node["type"] == "DBT_MODEL"
        and node.get("properties", {}).get("name") in LANDING_ACCOUNT_ROOTS
        and "/public/" in node.get("properties", {}).get("source_path", "").replace("\\", "/")
    }
    if not seeds:
        raise ValueError("No declared Landing Account public roots were found")
    selected = set(seeds)
    queue = list(sorted(seeds))
    outgoing = {}
    for edge in graph["edges"]:
        outgoing.setdefault(edge["source"], []).append(edge)
    for node_id in queue:
        if nodes[node_id].get("properties", {}).get("is_boundary_node") is True:
            continue
        for edge in outgoing.get(node_id, []):
            if edge["type"] not in {"DEPENDS_ON", "MATERIALIZES_AS", "RESOLVES_TO"}:
                continue
            target = edge["target"]
            if target not in selected:
                selected.add(target)
                queue.append(target)
    for edge in graph["edges"]:
        if edge["target"] in selected and edge["type"] in {"CONTAINS", "MIGRATES"}:
            selected.add(edge["source"])
    output = {"nodes": [], "edges": []}
    for node in graph["nodes"]:
        if node["id"] in selected:
            record = deepcopy(node)
            record["properties"]["account_scope_role"] = "account_root" if node["id"] in seeds else "account_dependency_or_context"
            output["nodes"].append(record)
    output["edges"] = [deepcopy(edge) for edge in graph["edges"] if edge["source"] in selected and edge["target"] in selected]
    output["account_scope"] = account_scope()
    output["account_scope"]["matched_landing_seed_ids"] = sorted(seeds)
    return output


def account_scope():
    return {
        "scope": "Account",
        "landing_product": "ultracs-v1",
        "landing_public_roots": list(LANDING_ACCOUNT_ROOTS),
        "protect_products": list(PROTECT_ACCOUNT_PRODUCTS),
        "selection_rule": "Explicit Account public roots plus upstream DEPENDS_ON, MATERIALIZES_AS and RESOLVES_TO closure; ownership/migration context retained without traversing unrelated products.",
        "software_scope": "All kb-accounts project declarations, kept separate from data lineage.",
        "field_scope": "Resolved SQL projections for selected Account models; joined and lookup fields are dependency context, not independent domain roots.",
    }


def domain_scope():
    from .snapshot import ACCOUNT_DOMAIN_PRODUCTS, ENTERPRISE_PRODUCTS, ACCOUNT_DOMAIN_REPOSITORIES
    return {
        "scope": "Account", "profile": "account-domain",
        "repositories": list(ACCOUNT_DOMAIN_REPOSITORIES),
        "account_products": list(ACCOUNT_DOMAIN_PRODUCTS), "enterprise_products": list(ENTERPRISE_PRODUCTS),
        "protect_products": list(PROTECT_ACCOUNT_PRODUCTS),
        "selection_rule": "Account product models and orchestration plus referenced dependency closure; unused source declarations excluded; explicit boundary flags stop traversal.",
        "software_scope": "Captured kb-accounts project declarations, separate from data lineage.",
        "field_scope": "Account SQL projections, explicit EF bindings and supported C# event assignments; every extracted kb-accounts field receives a mapping or unresolved relationship assessment. Joined fields remain dependency context.",
    }


def cdp_account_scope(products):
    from .snapshot import CDP_ACCOUNT_REPOSITORIES
    return {"scope": "Account", "profile": "cdp-account", "repositories": list(CDP_ACCOUNT_REPOSITORIES),
        "account_products": sorted(products),
        "selection_rule": "All product directories in kb-cdp-tenant-account plus all production kb-accounts projects, EF snapshots, and event schemas captured; no source checkout outside the two-repository allowlist.",
        "software_scope": "kb-accounts project references are retained separately from its data/event lineage.",
        "field_scope": "Explicit EF property bindings, C# entity-to-event assignments, and SQL projections; unresolved transformations and transport remain visible."}


def landing_account_graph(repo_path: Path):
    from .landing_parser import parse
    nodes, edges = parse(repo_path, products=("ultracs-v1",))
    return slice_landing_account({"nodes": nodes, "edges": edges})


def slice_protect_account(graph: dict) -> dict:
    nodes = {node["id"]: node for node in graph["nodes"]}
    selected = {
        node["id"] for node in graph["nodes"]
        if (node["type"] == "DBT_MODEL" and node.get("properties", {}).get("confidence") != "declared_reference")
        or node["type"] in {"CDP_PRODUCT", "AIRFLOW_DAG", "AIRFLOW_TASK", "S3_PATH", "SCHEMACHANGE_MIGRATION"}
    }
    queue = list(sorted(selected))
    outgoing = {}
    for edge in graph["edges"]:
        outgoing.setdefault(edge["source"], []).append(edge)
    for node_id in queue:
        if nodes[node_id].get("properties", {}).get("is_boundary_node") is True:
            continue
        for edge in outgoing.get(node_id, []):
            if edge["type"] == "CONTAINS":
                continue
            if edge["target"] not in selected:
                selected.add(edge["target"])
                queue.append(edge["target"])
    output = {"nodes": [], "edges": []}
    for node in graph["nodes"]:
        if node["id"] in selected:
            record = deepcopy(node)
            record["properties"]["account_scope_role"] = "account_product" if node["type"] in {"CDP_PRODUCT", "DBT_MODEL"} else "account_dependency_or_context"
            output["nodes"].append(record)
    output["edges"] = [deepcopy(edge) for edge in graph["edges"] if edge["source"] in selected and edge["target"] in selected]
    output["account_scope"] = account_scope()
    return output


def discover_account_sources(source_root: Path):
    from .protect_downstream_parser import parse

    landing = source_root / "kb-cdp-tenant-landing"
    protect = source_root / "kb-cdp-tenant-protect-downstream"
    graphs = {
        landing: landing_account_graph(landing),
    }
    protect_nodes, protect_edges = parse(protect, products=PROTECT_ACCOUNT_PRODUCTS)
    graphs[protect] = slice_protect_account({"nodes": protect_nodes, "edges": protect_edges})
    paths = set()
    for repository, graph in graphs.items():
        for item in graph["nodes"] + graph["edges"]:
            properties = item.get("properties", {})
            for name in [properties.get("source_path"), *properties.get("source_paths", [])]:
                if not name:
                    continue
                path = repository / name
                if path.is_file():
                    paths.add(path)
                    if path.suffix == ".sql":
                        for suffix in (".yml", ".yaml"):
                            sibling = path.with_suffix(suffix)
                            if sibling.is_file():
                                paths.add(sibling)
        products = ("ultracs-v1",) if repository == landing else PROTECT_ACCOUNT_PRODUCTS
        for product in products:
            root = repository / "products" / product
            for pattern in ("dbt/dbt_project.yml", "dbt/models/*source*.yml", "dbt/models/*source*.yaml", "dbt/macros/*.sql", "pipeline/*.yaml", "config.yaml"):
                paths.update(path for path in root.glob(pattern) if path.is_file())
    paths.update(path for path in (source_root / "kb-accounts").rglob("*.csproj") if ".git" not in path.parts)
    return sorted(paths)